"""BrowserApp v2 — proxy endpoint (full fetch pipeline).

PR 3 replaces PR 2's 501 stub with the real orchestrator:

  1. Auth via Depends(get_current_user)
  2. Profile resolution + auto-bootstrap of Personal/Work defaults
  3. SSRF guard on the initial URL
  4. Cookie jar load (per-(user, profile, host))
  5. httpx fetch with cookies, follow_redirects=False
  6. Manual redirect walk (up to MAX_REDIRECTS), SSRF re-check at each step
  7. For text/html: lxml rewriter + injector + strict CSP header
  8. For other content: stream pass-through, content-type preserved
  9. Persist Set-Cookie back to the jar
 10. Strip Set-Cookie from response to client (cookies live server-side)

Also exposes GET /__taos/copilot.js as a static asset.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin, urlparse, urlsplit

import httpx
from fastapi import Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response

from tinyagentos.auth import get_current_user
from tinyagentos.routes.desktop_browser import router
from tinyagentos.routes.desktop_browser.cookie_jar import (
    load_jar_for_request,
    persist_response_cookies,
)
from tinyagentos.routes.desktop_browser.csp import proxied_response_csp
from tinyagentos.routes.desktop_browser.injector import inject_into_head
from tinyagentos.routes.desktop_browser.profile import (
    ProfileNotFoundError,
    ensure_default_profiles,
    get_profile_or_404,
)
from tinyagentos.routes.desktop_browser.rewriter import rewrite_html
from tinyagentos.routes.desktop_browser.ssrf import (
    SsrfBlockedError,
    validate_url_or_raise,
)


_logger = logging.getLogger(__name__)

_MAX_REDIRECTS = 5
_FETCH_TIMEOUT = 15.0  # seconds — total deadline including redirects

# Headers we strip from upstream responses before returning to the client.
_STRIP_RESPONSE_HEADERS = frozenset({
    "set-cookie", "set-cookie2",
    "content-security-policy", "content-security-policy-report-only",
    "x-frame-options",
    "content-length", "transfer-encoding", "content-encoding",
})


@router.get("/api/desktop/browser/proxy")
async def proxy_get(
    profile_id: str,
    url: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Real proxy fetch — replaces PR 2's 501 stub."""
    user_id = str(current_user.get("id") or "")
    if not user_id:
        return JSONResponse({"error": "session has no user id"}, status_code=401)

    # Bootstrap default profiles (idempotent — safe per-request)
    browser_store = request.app.state.browser_store
    cookie_store = request.app.state.browser_cookie_store
    await ensure_default_profiles(browser_store, user_id=user_id)

    # Profile must exist for this user
    try:
        await get_profile_or_404(
            browser_store, user_id=user_id, profile_id=profile_id,
        )
    except ProfileNotFoundError:
        return JSONResponse({"error": "profile not found"}, status_code=404)

    # Initial SSRF check
    try:
        validate_url_or_raise(url)
    except SsrfBlockedError as e:
        parsed = urlsplit(url)
        _logger.info(
            "browser proxy SSRF block: scheme=%r host=%r reason=%s",
            parsed.scheme, parsed.hostname, e,
        )
        return JSONResponse({"error": "URL blocked"}, status_code=403)

    # Walk redirects manually so we can re-check SSRF on each step
    current_url = url
    response: httpx.Response | None = None

    async with httpx.AsyncClient(
        follow_redirects=False, timeout=_FETCH_TIMEOUT,
    ) as http:
        for hop in range(_MAX_REDIRECTS + 1):
            host = urlparse(current_url).hostname or ""

            jar = await load_jar_for_request(
                cookie_store, user_id=user_id, profile_id=profile_id, host=host,
            )

            try:
                response = await http.get(current_url, cookies=jar)
            except httpx.HTTPError as e:
                _logger.info("browser proxy fetch error: err=%s", e)
                return JSONResponse({"error": "fetch failed"}, status_code=502)

            # Persist any cookies set by this hop
            await persist_response_cookies(
                cookie_store, response.cookies,
                user_id=user_id, profile_id=profile_id,
            )

            if response.status_code in (301, 302, 303, 307, 308):
                location = response.headers.get("location")
                if not location:
                    break
                next_url = urljoin(current_url, location)
                try:
                    validate_url_or_raise(next_url)
                except SsrfBlockedError as e:
                    parsed = urlsplit(next_url)
                    _logger.info(
                        "browser proxy SSRF block on redirect: scheme=%r host=%r reason=%s",
                        parsed.scheme, parsed.hostname, e,
                    )
                    return JSONResponse({"error": "URL blocked"}, status_code=403)
                current_url = next_url
                continue

            # Non-redirect — done
            break
        else:
            return JSONResponse({"error": "too many redirects"}, status_code=508)

    if response is None:
        return JSONResponse({"error": "fetch failed"}, status_code=502)

    # Build response headers — strip the dangerous + length-related ones
    out_headers: dict[str, str] = {}
    for k, v in response.headers.items():
        if k.lower() in _STRIP_RESPONSE_HEADERS:
            continue
        out_headers[k] = v

    content_type = response.headers.get("content-type", "")

    if "text/html" in content_type:
        # Rewrite + inject for HTML
        proxy_prefix = (
            f"/api/desktop/browser/proxy?profile_id={quote(profile_id, safe='')}"
            f"&url="
        )

        def _proxy_url(absolute: str) -> str:
            return f"{proxy_prefix}{quote(absolute, safe='')}"

        rewritten = rewrite_html(
            response.content, base_url=str(response.url), proxy=_proxy_url,
        )

        ws_scheme = "wss" if request.url.scheme == "https" else "ws"
        ws_url = (
            f"{ws_scheme}://{request.url.netloc}/api/desktop/browser/copilot"
            f"?profile_id={quote(profile_id, safe='')}"
        )
        injected = inject_into_head(rewritten, ws_url=ws_url)

        out_headers["content-security-policy"] = proxied_response_csp()
        return Response(
            content=injected,
            status_code=response.status_code,
            headers=out_headers,
            media_type="text/html",
        )

    # Non-HTML — pass through bytes verbatim
    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=out_headers,
        media_type=content_type or "application/octet-stream",
    )


# Static asset serve for the copilot script.
_COPILOT_JS = Path(__file__).parent / "copilot.js"


@router.get("/__taos/copilot.js")
async def copilot_js():
    return FileResponse(_COPILOT_JS, media_type="application/javascript")
