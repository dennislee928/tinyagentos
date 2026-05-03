"""BrowserApp v2 — proxy endpoint shell.

PR 2 lands the security gate: authentication required, SSRF guard
runs on every URL, parameter validation, and a 501 response for
valid requests so the route is real and discoverable in the OpenAPI
schema. PR 3 will replace the 501 stub with the actual fetch +
rewriter + cookie jar pipeline.

Endpoint: GET /api/desktop/browser/proxy
Query:    profile_id (required) — which profile's cookie jar to use
          url        (required) — target URL to fetch
Auth:     taos_session cookie required (same as the rest of the desktop)

Responses:
  200  — (PR 3 only) proxied HTML/asset response with strict CSP
  401  — no valid session cookie
  403  — URL failed SSRF guard (private IP, local TLD, etc.)
  422  — required query param missing
  501  — temporary: PR 2 ships the gate without the fetch pipeline
"""
from __future__ import annotations

from typing import Any

from fastapi import Depends, Request
from fastapi.responses import JSONResponse

from tinyagentos.auth import get_current_user
from tinyagentos.routes.desktop_browser import router
from tinyagentos.routes.desktop_browser.ssrf import (
    SsrfBlockedError,
    validate_url_or_raise,
)


@router.get("/api/desktop/browser/proxy")
async def proxy_get(
    profile_id: str,
    url: str,
    request: Request,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    """Auth + SSRF gate for the BrowserApp v2 proxy.

    PR 3 replaces the 501 stub with the real fetch pipeline.
    """
    # SSRF guard — rejects private IPs, .local/.onion/.internal hosts,
    # decimal/octal IP encodings, IPv6 alts.
    try:
        validate_url_or_raise(url)
    except SsrfBlockedError as e:
        # Log the detailed reason server-side for debugging, but DO NOT
        # echo it to the client — the message can include resolved IPs
        # that would help a remote attacker enumerate the user's LAN.
        import logging
        from urllib.parse import urlsplit
        parsed = urlsplit(url)
        logging.getLogger(__name__).info(
            "browser proxy SSRF block: scheme=%r host=%r reason=%s",
            parsed.scheme,
            parsed.hostname,
            e,
        )
        return JSONResponse(
            {"error": "URL blocked"},
            status_code=403,
        )

    # PR 2 stops here. Future-PR-3 code will:
    #   1. Look up cookies from BrowserCookieStore for (current_user["id"], profile_id, host)
    #   2. httpx fetch with cookies attached, follow_redirects=False, re-validating each redirect
    #   3. Run the lxml rewriter on text/html responses
    #   4. Inject /__taos/copilot.js
    #   5. Apply the strict CSP from csp.proxied_response_csp()
    #   6. Persist Set-Cookie back to the jar
    return JSONResponse(
        {
            "error": (
                "Proxy fetch not yet implemented — gate passed (auth + SSRF). "
                "Fetch pipeline lands in PR 3."
            ),
        },
        status_code=501,
    )
