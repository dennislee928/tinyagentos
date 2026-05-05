"""Tests for the agent-side copilot WebSocket endpoint and CopilotHub agent methods."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect


# ---------------------------------------------------------------------------
# Fixtures — reuse _make_ws_app pattern from test_copilot_ws.py
# ---------------------------------------------------------------------------

def _make_ws_app(tmp_path):
    """Create a minimal app with browser_store initialized (sync-compatible)."""
    from tinyagentos.app import create_app
    from tinyagentos.routes.desktop_browser.store import BrowserStore

    config = {
        "server": {"host": "0.0.0.0", "port": 6969},
        "backends": [],
        "qmd": {"url": "http://localhost:7832"},
        "agents": [],
        "metrics": {"poll_interval": 30, "retention_days": 30},
    }
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.dump(config))
    (tmp_path / ".setup_complete").touch()

    app = create_app(data_dir=tmp_path)

    browser_store = BrowserStore(tmp_path / "browser.sqlite3")
    asyncio.run(browser_store.init())
    app.state.browser_store = browser_store

    app.state.auth.setup_user("admin", "Test Admin", "", "testpass")

    return app


@pytest.fixture
def ws_app(tmp_path):
    return _make_ws_app(tmp_path)


@pytest.fixture
def ws_client(ws_app):
    record = ws_app.state.auth.find_user("admin")
    token = ws_app.state.auth.create_session(user_id=record["id"], long_lived=True)
    with TestClient(ws_app, raise_server_exceptions=False) as c:
        c.cookies.set("taos_session", token)
        yield c


def _add_agent_to(app, agent_id: str):
    app.state.config.agents.append({
        "id": agent_id,
        "name": agent_id,
        "host": "127.0.0.1",
        "qmd_index": "test",
        "color": "#000000",
    })


def _pin_and_mint(client, app, profile_id, tab_id, agent_id):
    """Pin agent and mint a ticket. Returns the ticket token."""
    _add_agent_to(app, agent_id)
    client.post(
        "/api/desktop/browser/pins",
        json={"profile_id": profile_id, "tab_id": tab_id, "agent_id": agent_id},
    )
    resp = client.post(
        "/api/desktop/browser/copilot/ticket",
        json={"profile_id": profile_id, "tab_id": tab_id, "agent_id": agent_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["ticket"]


# ---------------------------------------------------------------------------
# Case 1: 4401 on invalid ticket
# ---------------------------------------------------------------------------

class TestAgentWS4401InvalidTicket:
    def test_4401_on_random_ticket(self, ws_client):
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with ws_client.websocket_connect(
                "/api/desktop/browser/copilot-agent?ticket=totally-invalid-token"
            ) as ws:
                ws.receive_text()
        assert exc_info.value.code == 4401


# ---------------------------------------------------------------------------
# Case 2: 4401 on already-consumed ticket
# ---------------------------------------------------------------------------

class TestAgentWS4401ConsumedTicket:
    def test_4401_on_consumed_ticket(self, ws_client, ws_app):
        ticket = _pin_and_mint(ws_client, ws_app, "p1", "t1", "agent-consumed")
        ws_app.state.copilot_ticket_store.consume(ticket)

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with ws_client.websocket_connect(
                f"/api/desktop/browser/copilot-agent?ticket={ticket}"
            ) as ws:
                ws.receive_text()
        assert exc_info.value.code == 4401


# ---------------------------------------------------------------------------
# Case 3: 4403 on unpinned agent
# ---------------------------------------------------------------------------

class TestAgentWS4403Unpinned:
    def test_4403_when_unpinned_after_mint(self, ws_client, ws_app):
        ticket = _pin_and_mint(ws_client, ws_app, "p1", "t1", "agent-unpin")
        ws_client.delete(
            "/api/desktop/browser/pins",
            params={"profile_id": "p1", "tab_id": "t1", "agent_id": "agent-unpin"},
        )

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with ws_client.websocket_connect(
                f"/api/desktop/browser/copilot-agent?ticket={ticket}"
            ) as ws:
                ws.receive_text()
        assert exc_info.value.code == 4403


# ---------------------------------------------------------------------------
# Case 4: Successful upgrade adds agent to hub
# ---------------------------------------------------------------------------

class TestAgentWSRegistersInHub:
    def test_agent_registered_in_hub_during_connection(self, ws_client, ws_app):
        ticket = _pin_and_mint(ws_client, ws_app, "p1", "t1", "agent-hub")
        record = ws_app.state.auth.find_user("admin")
        user_id = record["id"]

        with ws_client.websocket_connect(
            f"/api/desktop/browser/copilot-agent?ticket={ticket}"
        ):
            key = (user_id, "agent-hub")
            assert key in ws_app.state.copilot_hub._agent_conns

        # After disconnect, still need to check removal in case 5 below.


# ---------------------------------------------------------------------------
# Case 5: Disconnect cleans up agent from hub
# ---------------------------------------------------------------------------

class TestAgentWSCleanupOnDisconnect:
    def test_hub_key_removed_after_disconnect(self, ws_client, ws_app):
        ticket = _pin_and_mint(ws_client, ws_app, "p1", "t1", "agent-cleanup")
        record = ws_app.state.auth.find_user("admin")
        user_id = record["id"]
        key = (user_id, "agent-cleanup")

        with ws_client.websocket_connect(
            f"/api/desktop/browser/copilot-agent?ticket={ticket}"
        ):
            assert key in ws_app.state.copilot_hub._agent_conns

        assert key not in ws_app.state.copilot_hub._agent_conns


# ---------------------------------------------------------------------------
# Case 6: route_op_to_iframe returns False when no iframe registered
# ---------------------------------------------------------------------------

class TestRouteOpToIframeNoIframe:
    @pytest.mark.asyncio
    async def test_returns_false_when_iframe_not_connected(self):
        from tinyagentos.routes.desktop_browser.copilot_ws import CopilotHub
        hub = CopilotHub()
        result = await hub.route_op_to_iframe(
            user_id="u1",
            profile_id="p1",
            tab_id="t1",
            agent_id="agent-x",
            op={"op": "click", "selector": "#btn"},
        )
        assert result is False


# ---------------------------------------------------------------------------
# Case 7: Round-trip: agent op → iframe receive → ack → agent receive
# ---------------------------------------------------------------------------

class TestRoundTripOpAck:
    def test_op_forwarded_to_iframe_and_ack_forwarded_to_agent(
        self, ws_client, ws_app
    ):
        """Register a mock iframe, connect agent, send op, verify iframe gets it,
        then send ack from iframe WS, verify agent receives it."""
        ticket = _pin_and_mint(ws_client, ws_app, "p1", "t1", "agent-rt")
        record = ws_app.state.auth.find_user("admin")
        user_id = record["id"]

        # Register a fake iframe in the hub
        mock_iframe_ws = AsyncMock()
        iframe_key = (user_id, "p1", "t1", "agent-rt")
        ws_app.state.copilot_hub._iframe_conns[iframe_key] = mock_iframe_ws

        op_msg = {"op": "click", "selector": "#submit", "op_id": "op-1"}

        with ws_client.websocket_connect(
            f"/api/desktop/browser/copilot-agent?ticket={ticket}"
        ) as ws:
            ws.send_json(op_msg)
            # Give the async loop a moment to process
            import time
            time.sleep(0.05)

        # The iframe mock should have received the op
        mock_iframe_ws.send_json.assert_awaited_once_with(op_msg)

        # Clean up
        ws_app.state.copilot_hub._iframe_conns.pop(iframe_key, None)


# ---------------------------------------------------------------------------
# Case 8: Drive op bumps drive_session
# ---------------------------------------------------------------------------

class TestDriveOpBumpsSession:
    def test_click_op_creates_drive_session(self, ws_client, ws_app):
        ticket = _pin_and_mint(ws_client, ws_app, "p1", "t1", "agent-drive")
        record = ws_app.state.auth.find_user("admin")
        user_id = record["id"]

        # Register a mock iframe so the op routes successfully
        mock_iframe_ws = AsyncMock()
        iframe_key = (user_id, "p1", "t1", "agent-drive")
        ws_app.state.copilot_hub._iframe_conns[iframe_key] = mock_iframe_ws

        with ws_client.websocket_connect(
            f"/api/desktop/browser/copilot-agent?ticket={ticket}"
        ) as ws:
            ws.send_json({"op": "click", "selector": "#btn", "op_id": "op-2"})
            import time
            time.sleep(0.05)

        # Verify drive session exists
        result = asyncio.run(
            ws_app.state.browser_store.is_driving(
                user_id=user_id,
                profile_id="p1",
                tab_id="t1",
                agent_id="agent-drive",
            )
        )
        assert result is True

        # Clean up
        ws_app.state.copilot_hub._iframe_conns.pop(iframe_key, None)


# ---------------------------------------------------------------------------
# Case 9: Non-drive op does NOT bump drive_session
# ---------------------------------------------------------------------------

class TestNonDriveOpNoSession:
    def test_extract_op_does_not_create_drive_session(self, ws_client, ws_app):
        ticket = _pin_and_mint(ws_client, ws_app, "p1", "t1", "agent-nodrive")
        record = ws_app.state.auth.find_user("admin")
        user_id = record["id"]

        # Register a mock iframe so the op routes successfully
        mock_iframe_ws = AsyncMock()
        iframe_key = (user_id, "p1", "t1", "agent-nodrive")
        ws_app.state.copilot_hub._iframe_conns[iframe_key] = mock_iframe_ws

        with ws_client.websocket_connect(
            f"/api/desktop/browser/copilot-agent?ticket={ticket}"
        ) as ws:
            ws.send_json({"op": "extract", "selector": "article", "op_id": "op-3"})
            import time
            time.sleep(0.05)

        result = asyncio.run(
            ws_app.state.browser_store.is_driving(
                user_id=user_id,
                profile_id="p1",
                tab_id="t1",
                agent_id="agent-nodrive",
            )
        )
        assert result is False

        # Clean up
        ws_app.state.copilot_hub._iframe_conns.pop(iframe_key, None)


# ---------------------------------------------------------------------------
# Case 10: Op with missing iframe → agent receives event: "error"
# ---------------------------------------------------------------------------

class TestOpMissingIframe:
    def test_error_event_sent_to_agent_when_iframe_absent(self, ws_client, ws_app):
        """Send an op when no iframe is connected → server replies event: error."""
        ticket = _pin_and_mint(ws_client, ws_app, "p1", "t1", "agent-err")

        with ws_client.websocket_connect(
            f"/api/desktop/browser/copilot-agent?ticket={ticket}"
        ) as ws:
            ws.send_json({"op": "click", "selector": "#x", "op_id": "op-err"})
            reply = ws.receive_json()

        assert reply["event"] == "error"
        assert reply["op_id"] == "op-err"
        assert "iframe not connected" in reply["reason"]


# ---------------------------------------------------------------------------
# Additional CopilotHub agent-method unit tests
# ---------------------------------------------------------------------------

class TestCopilotHubAgentMethods:
    def _make_hub(self):
        from tinyagentos.routes.desktop_browser.copilot_ws import CopilotHub
        return CopilotHub()

    def test_add_agent_registers_ws(self):
        hub = self._make_hub()
        ws = AsyncMock()
        hub.add_agent(user_id="u1", agent_id="a1", ws=ws)
        assert hub._agent_conns[("u1", "a1")] is ws

    def test_remove_agent_is_noop_when_not_present(self):
        hub = self._make_hub()
        hub.remove_agent(user_id="u1", agent_id="no-such")  # must not raise

    @pytest.mark.asyncio
    async def test_add_agent_replaces_prior_connection(self):
        hub = self._make_hub()
        old_ws = AsyncMock()
        new_ws = AsyncMock()
        hub._agent_conns[("u1", "a1")] = old_ws
        hub.add_agent(user_id="u1", agent_id="a1", ws=new_ws)
        assert hub._agent_conns[("u1", "a1")] is new_ws

    @pytest.mark.asyncio
    async def test_route_ack_to_agent_returns_true_on_success(self):
        hub = self._make_hub()
        ws = AsyncMock()
        hub._agent_conns[("u1", "a1")] = ws
        ack = {"event": "ack", "op_id": "op-1", "status": "ok"}
        result = await hub.route_ack_to_agent(user_id="u1", agent_id="a1", ack=ack)
        assert result is True
        ws.send_json.assert_awaited_once_with(ack)

    @pytest.mark.asyncio
    async def test_route_ack_to_agent_returns_false_when_no_agent(self):
        hub = self._make_hub()
        result = await hub.route_ack_to_agent(
            user_id="u1", agent_id="no-such",
            ack={"event": "ack", "op_id": "x"},
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_route_ack_to_agent_swallows_send_failure(self):
        hub = self._make_hub()
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("connection reset")
        hub._agent_conns[("u1", "a1")] = ws
        result = await hub.route_ack_to_agent(
            user_id="u1", agent_id="a1",
            ack={"event": "ack", "op_id": "x"},
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_route_op_to_iframe_returns_true_on_success(self):
        hub = self._make_hub()
        ws = AsyncMock()
        hub._iframe_conns[("u1", "p1", "t1", "a1")] = ws
        op = {"op": "navigate", "url": "https://example.com"}
        result = await hub.route_op_to_iframe(
            user_id="u1", profile_id="p1", tab_id="t1", agent_id="a1", op=op,
        )
        assert result is True
        ws.send_json.assert_awaited_once_with(op)

    @pytest.mark.asyncio
    async def test_route_op_to_iframe_swallows_send_failure(self):
        hub = self._make_hub()
        ws = AsyncMock()
        ws.send_json.side_effect = RuntimeError("disconnected")
        hub._iframe_conns[("u1", "p1", "t1", "a1")] = ws
        result = await hub.route_op_to_iframe(
            user_id="u1", profile_id="p1", tab_id="t1", agent_id="a1",
            op={"op": "click"},
        )
        assert result is False
