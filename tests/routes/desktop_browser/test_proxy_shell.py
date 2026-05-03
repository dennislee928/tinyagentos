"""Tests for the /api/desktop/browser/proxy endpoint shell.

PR 2 lands the security gate (auth + SSRF check). The endpoint
returns 501 Not Implemented for valid URLs because the actual fetch +
rewriter + cookie jar logic lands in PR 3.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
class TestAuth:
    async def test_unauthenticated_request_rejected(self, app):
        # Build a fresh client with no session cookie — auth middleware must
        # reject the request before it reaches the route handler.
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as c:
            resp = await c.get(
                "/api/desktop/browser/proxy",
                params={"profile_id": "personal", "url": "http://example.com/"},
            )
        assert resp.status_code == 401

    async def test_authenticated_request_passes_auth_gate(self, client):
        # `client` already carries a valid taos_session cookie — proves
        # auth gate passes. Response will be SSRF check or 501, never 401.
        resp = await client.get(
            "/api/desktop/browser/proxy",
            params={"profile_id": "personal", "url": "http://example.com/"},
        )
        assert resp.status_code != 401


@pytest.mark.asyncio
class TestSsrfGate:
    async def test_url_failing_ssrf_returns_403(self, client):
        resp = await client.get(
            "/api/desktop/browser/proxy",
            params={"profile_id": "personal", "url": "http://127.0.0.1/admin"},
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "error" in body

    async def test_invalid_scheme_returns_403(self, client):
        resp = await client.get(
            "/api/desktop/browser/proxy",
            params={"profile_id": "personal", "url": "file:///etc/passwd"},
        )
        assert resp.status_code == 403
        body = resp.json()
        assert "error" in body


@pytest.mark.asyncio
class TestParameterValidation:
    async def test_missing_url_returns_422(self, client):
        resp = await client.get(
            "/api/desktop/browser/proxy",
            params={"profile_id": "personal"},
        )
        # FastAPI returns 422 for missing required query params
        assert resp.status_code == 422

    async def test_missing_profile_returns_422(self, client):
        resp = await client.get(
            "/api/desktop/browser/proxy",
            params={"url": "http://example.com/"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestNotImplementedStub:
    async def test_valid_request_returns_501(self, client):
        # example.com is real and public so SSRF passes, but PR 2
        # stubs the actual fetch to keep the deliverable focused.
        with patch(
            "tinyagentos.routes.desktop_browser.ssrf.socket.gethostbyname_ex",
            return_value=("example.com", [], ["93.184.216.34"]),
        ):
            resp = await client.get(
                "/api/desktop/browser/proxy",
                params={"profile_id": "personal", "url": "http://example.com/"},
            )
        assert resp.status_code == 501
        body = resp.json()
        assert "error" in body
        # Body must mention PR 3 so anyone hitting this in early dev
        # knows where the fetch logic actually lands.
        assert "PR 3" in body["error"] or "not yet implemented" in body["error"].lower()
