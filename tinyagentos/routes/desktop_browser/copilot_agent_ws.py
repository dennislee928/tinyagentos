"""Copilot agent-side WebSocket — agent runtime sends ops, receives acks.

The agent runtime obtains a ticket via /api/desktop/browser/copilot/ticket
(same endpoint as the iframe side). The ticket is bound to (user, agent, tab),
but the agent connection is keyed only by (user, agent) — an agent has one WS
regardless of how many tabs it's pinned to. The ticket's tab_id determines the
*default* iframe target for op routing.
"""
from __future__ import annotations

import logging

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from tinyagentos.routes.desktop_browser import router

_logger = logging.getLogger(__name__)

_DRIVE_OPS = {"scrollTo", "click", "type", "navigate", "focus"}


@router.websocket("/api/desktop/browser/copilot-agent")
async def copilot_agent_ws(websocket: WebSocket, ticket: str):
    """Agent runtime → server WebSocket."""
    consumed = websocket.app.state.copilot_ticket_store.consume(ticket)
    if consumed is None:
        await websocket.close(code=4401, reason="invalid or expired ticket")
        return

    pinned = await websocket.app.state.browser_store.list_pins_for_tab(
        user_id=consumed.user_id,
        profile_id=consumed.profile_id,
        tab_id=consumed.tab_id,
    )
    if not any(p["agent_id"] == consumed.agent_id for p in pinned):
        await websocket.close(code=4403, reason="agent not pinned")
        return

    await websocket.accept()
    hub = websocket.app.state.copilot_hub
    store = websocket.app.state.browser_store
    hub.add_agent(user_id=consumed.user_id, agent_id=consumed.agent_id, ws=websocket)

    try:
        while True:
            msg = await websocket.receive_json()
            op = msg.get("op")
            if not isinstance(op, str):
                continue

            # Allow the agent to target a specific (profile, tab) per op via msg fields,
            # falling back to the ticket-bound (profile, tab). For PR 7 the typical agent
            # only operates on the ticket's tab; cross-tab ops are out of scope.
            target_profile = msg.get("profile_id", consumed.profile_id)
            target_tab = msg.get("tab_id", consumed.tab_id)

            ok = await hub.route_op_to_iframe(
                user_id=consumed.user_id,
                profile_id=target_profile,
                tab_id=target_tab,
                agent_id=consumed.agent_id,
                op=msg,
            )
            if not ok:
                await websocket.send_json({
                    "event": "error",
                    "op_id": msg.get("op_id"),
                    "reason": "iframe not connected",
                })
                continue

            if op in _DRIVE_OPS:
                bumped = await store.bump_drive_session(
                    user_id=consumed.user_id,
                    profile_id=target_profile,
                    tab_id=target_tab,
                    agent_id=consumed.agent_id,
                )
                if not bumped:
                    await store.start_drive_session(
                        user_id=consumed.user_id,
                        profile_id=target_profile,
                        tab_id=target_tab,
                        agent_id=consumed.agent_id,
                    )
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove_agent(user_id=consumed.user_id, agent_id=consumed.agent_id)
