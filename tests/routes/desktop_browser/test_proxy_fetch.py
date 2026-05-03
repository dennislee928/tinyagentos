"""Integration tests for the real proxy fetch pipeline (PR 3).

These exercise the orchestrator in tinyagentos/routes/desktop_browser/proxy.py
after it has been upgraded from PR 2's 501 stub. Network is mocked
via respx (already in dev deps).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
import respx
from httpx import Response


@pytest.mark.asyncio
class TestProxyFetchHtml:
    @respx.mock
    async def test_fetches_html_and_rewrites_links(self, client):
        respx.get("http://example.com/page").mock(
            return_value=Response(
                200,
                content=b'<html><head></head><body><a href="/next">next</a></body></html>',
                headers={"content-type": "text/html"},
            )
        )

        with patch(
            "tinyagentos.routes.desktop_browser.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            resp = await client.get(
                "/api/desktop/browser/proxy",
                params={"profile_id": "personal", "url": "http://example.com/page"},
            )

        assert resp.status_code == 200
        assert b"/api/desktop/browser/proxy" in resp.content
        assert b"example.com%2Fnext" in resp.content

    @respx.mock
    async def test_injects_copilot_script(self, client):
        respx.get("http://example.com/").mock(
            return_value=Response(
                200,
                content=b'<html><head></head><body></body></html>',
                headers={"content-type": "text/html"},
            )
        )

        with patch(
            "tinyagentos.routes.desktop_browser.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            resp = await client.get(
                "/api/desktop/browser/proxy",
                params={"profile_id": "personal", "url": "http://example.com/"},
            )

        assert resp.status_code == 200
        assert b'<script src="/__taos/copilot.js"' in resp.content

    @respx.mock
    async def test_applies_strict_csp_to_html(self, client):
        respx.get("http://example.com/").mock(
            return_value=Response(
                200,
                content=b'<html><body>x</body></html>',
                headers={"content-type": "text/html"},
            )
        )

        with patch(
            "tinyagentos.routes.desktop_browser.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            resp = await client.get(
                "/api/desktop/browser/proxy",
                params={"profile_id": "personal", "url": "http://example.com/"},
            )

        assert "content-security-policy" in {k.lower() for k in resp.headers}
        csp = next(v for k, v in resp.headers.items() if k.lower() == "content-security-policy")
        assert "default-src 'self'" in csp


@pytest.mark.asyncio
class TestProxyFetchNonHtml:
    @respx.mock
    async def test_passes_through_image_unchanged(self, client):
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"X" * 100
        respx.get("http://example.com/img.png").mock(
            return_value=Response(
                200,
                content=png_bytes,
                headers={"content-type": "image/png"},
            )
        )

        with patch(
            "tinyagentos.routes.desktop_browser.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            resp = await client.get(
                "/api/desktop/browser/proxy",
                params={"profile_id": "personal", "url": "http://example.com/img.png"},
            )

        assert resp.status_code == 200
        assert resp.content == png_bytes
        assert resp.headers["content-type"] == "image/png"


@pytest.mark.asyncio
class TestProxyFetchCookies:
    @respx.mock
    async def test_persists_set_cookie_to_jar(self, client):
        respx.get("http://example.com/login").mock(
            return_value=Response(
                200,
                content=b'<html><body>logged in</body></html>',
                headers={
                    "content-type": "text/html",
                    "set-cookie": "session=abc123; Path=/",
                },
            )
        )

        with patch(
            "tinyagentos.routes.desktop_browser.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            resp = await client.get(
                "/api/desktop/browser/proxy",
                params={"profile_id": "personal", "url": "http://example.com/login"},
            )

        assert resp.status_code == 200

        # Set-Cookie from upstream MUST NOT appear in our response (cookies
        # live in the jar, not the user's browser)
        assert "set-cookie" not in {k.lower() for k in resp.headers}


@pytest.mark.asyncio
class TestProxyRedirects:
    @respx.mock
    async def test_redirect_target_revalidated_against_ssrf(self, client):
        # First response is a 302 to an internal IP — must be rejected by
        # SSRF guard on the redirect step
        respx.get("http://example.com/redirect").mock(
            return_value=Response(
                302,
                headers={"location": "http://127.0.0.1/admin"},
            )
        )

        with patch(
            "tinyagentos.routes.desktop_browser.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            resp = await client.get(
                "/api/desktop/browser/proxy",
                params={"profile_id": "personal", "url": "http://example.com/redirect"},
            )

        assert resp.status_code == 403


@pytest.mark.asyncio
class TestStaticAssets:
    async def test_copilot_js_static_serve(self, client):
        resp = await client.get("/__taos/copilot.js")

        assert resp.status_code == 200
        assert "javascript" in resp.headers.get("content-type", "").lower()
        assert b"taos-copilot" in resp.content


@pytest.mark.asyncio
class TestResponseSizeCap:
    @respx.mock
    async def test_oversized_response_returns_502(self, client):
        oversized = b"X" * (11 * 1024 * 1024)  # 11 MB > 10 MB cap
        respx.get("http://example.com/big").mock(
            return_value=Response(
                200,
                content=oversized,
                headers={"content-type": "application/octet-stream"},
            )
        )

        with patch(
            "tinyagentos.routes.desktop_browser.ssrf.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ):
            resp = await client.get(
                "/api/desktop/browser/proxy",
                params={"profile_id": "personal", "url": "http://example.com/big"},
            )

        assert resp.status_code == 502
        body = resp.json()
        assert "too large" in body.get("error", "").lower()
