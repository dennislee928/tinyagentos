"""GET /api/desktop/browser/download — streams upstream file with attachment disposition.

Auth + SSRF gate + cookie jar, matching the proxy/extract security pattern.

Redirect strategy: walk redirects manually (follow_redirects=False) and
re-validate SSRF on every hop, identical to extract.py.  This prevents the
redirect-bypass attack where an initial URL passes the SSRF check but the
redirect target is an internal host.

The redirect walk happens *before* streaming begins so that we can still
return a JSONResponse on SSRF block or redirect-chain-too-long.  Once we
have the final URL, we open a streaming connection and yield bytes directly
to the client.
"""
from __future__ import annotations

import logging
import os
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlparse, urlsplit

import httpx
from fastapi import Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from tinyagentos.auth import get_current_user
from tinyagentos.routes.desktop_browser import router
from tinyagentos.routes.desktop_browser.cookie_jar import (
    load_jar_for_request,
    persist_response_cookies,
)
from tinyagentos.routes.desktop_browser.ssrf import (
    SsrfBlockedError,
    validate_url_or_raise,
)


_logger = logging.getLogger(__name__)

_MAX_HOPS = 5
_FETCH_TIMEOUT = 60.0  # downloads can be larger than HTML pages


def _filename_from_url(url: str) -> str:
    """Infer a filename from the URL path.  Returns "download" as a fallback."""
    try:
        path = urlsplit(url).path
        name = unquote(path.rsplit("/", 1)[-1])
        if name and "." in name:
            return name
    except Exception:
        pass
    return "download"


def _safe_filename(filename: str) -> str:
    """Strip path-traversal components and unsafe chars from a caller-supplied filename."""
    # os.path.basename removes directory components (catches "../../etc/passwd")
    base = os.path.basename(filename)
    # Strip control chars and characters that would break Content-Disposition header parsing
    base = "".join(c for c in base if c.isprintable() and c not in '"\\')
    return base or "download"


async def _resolve_final_url(
    initial_url: str,
    cookies: httpx.Cookies,
) -> tuple[str, httpx.Response] | tuple[None, JSONResponse]:
    """Walk the redirect chain with per-hop SSRF validation.

    Returns (final_url, response) on success, or (None, error_JSONResponse) on failure.
    The returned response on success is the first non-redirect response — it is NOT
    yet read (we hand it back to stream from).  Caller must close it if not streamed.
    """
    fetch_url = initial_url
    async with httpx.AsyncClient(
        follow_redirects=False, timeout=_FETCH_TIMEOUT, cookies=cookies,
    ) as http:
        for _hop in range(_MAX_HOPS):
            try:
                response = await http.get(fetch_url)
            except httpx.HTTPError as e:
                _logger.info("browser download fetch error: err=%s", e)
                return None, JSONResponse({"error": "fetch failed"}, status_code=502)

            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    return None, JSONResponse(
                        {"error": "redirect missing Location"}, status_code=502,
                    )
                fetch_url = urljoin(fetch_url, location)
                try:
                    validate_url_or_raise(fetch_url)
                except SsrfBlockedError as e:
                    parsed = urlsplit(fetch_url)
                    _logger.info(
                        "browser download SSRF block on redirect: scheme=%r host=%r reason=%s",
                        parsed.scheme, parsed.hostname, e,
                    )
                    return None, JSONResponse({"error": "URL blocked"}, status_code=403)
                continue

            # Non-redirect — we have the final response
            return fetch_url, response

        return None, JSONResponse({"error": "redirect chain too long"}, status_code=502)


@router.get("/api/desktop/browser/download")
async def download_endpoint(
    request: Request,
    profile_id: str,
    url: str,
    filename: str | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),  # noqa: B008
):
    """Stream an upstream file through the proxy as a browser download.

    Gates: auth + SSRF (with per-hop redirect re-validation) + cookie jar.
    Sets Content-Disposition: attachment so the browser shows a save dialog.
    """
    user_id = str(current_user.get("id") or "")
    if not user_id:
        return JSONResponse({"error": "session has no user id"}, status_code=401)

    # SSRF gate on initial URL
    try:
        validate_url_or_raise(url)
    except SsrfBlockedError as e:
        parsed = urlsplit(url)
        _logger.info(
            "browser download SSRF block: scheme=%r host=%r reason=%s",
            parsed.scheme, parsed.hostname, e,
        )
        return JSONResponse({"error": "URL blocked"}, status_code=403)

    # Determine output filename before fetching
    final_name = (
        _safe_filename(filename) if filename else _safe_filename(_filename_from_url(url))
    )

    # Load cookies for the initial host; after redirects the host may differ
    # but the jar covers the profile broadly enough for common use cases.
    host = urlparse(url).hostname or ""
    cookies = await load_jar_for_request(
        request.app.state.browser_cookie_store,
        user_id=user_id, profile_id=profile_id, host=host,
    )

    # Walk redirects with per-hop SSRF re-validation, collect final response
    result = await _resolve_final_url(url, cookies)
    final_url, maybe_response = result

    if final_url is None:
        # maybe_response is a JSONResponse carrying the error
        return maybe_response

    final_response: httpx.Response = maybe_response  # type: ignore[assignment]

    # Persist any cookies from the redirect walk
    try:
        await persist_response_cookies(
            request.app.state.browser_cookie_store,
            final_response.cookies,
            user_id=user_id, profile_id=profile_id,
        )
    except Exception:
        pass  # cookie persistence failure is non-fatal

    # Stream body to client
    async def streamer():
        try:
            async for chunk in final_response.aiter_bytes():
                yield chunk
        except httpx.HTTPError as e:
            _logger.info("browser download stream error: err=%s", e)
            # Can't send a new response once streaming has started; just stop.

    # RFC 5987 encoded filename for non-ASCII safety
    safe_quoted = quote(final_name, safe="")

    return StreamingResponse(
        streamer(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{final_name}"; filename*=UTF-8\'\'{safe_quoted}'
            ),
        },
    )
