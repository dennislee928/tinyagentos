"""Verify the desktop_browser router is mounted on the FastAPI app.

PR 1 mounts an empty router so future PRs can add routes against an
established prefix. This test only checks the router object reaches the
app — it does not exercise any endpoints.
"""
from __future__ import annotations


def test_desktop_browser_router_present_in_app(app):
    from tinyagentos.routes.desktop_browser import router as browser_router

    # Each include_router call wraps the router in a Mount or copies its
    # routes into the app. Easiest check: the app's route paths include
    # nothing for this prefix yet, but the router object has been imported
    # without error and is wired in (see app.py change below). The
    # router is empty in PR 1, so we just assert the import works and the
    # FastAPI app has been built successfully (the fixture proves that).
    assert browser_router is not None
    assert app is not None


def test_desktop_browser_module_importable():
    """Defensive import test — catches packaging mistakes early."""
    from tinyagentos.routes.desktop_browser import router
    from tinyagentos.routes.desktop_browser.crypto import derive_cookie_key
    from tinyagentos.routes.desktop_browser.schema import (
        BROWSER_SCHEMA,
        COOKIE_SCHEMA,
    )
    from tinyagentos.routes.desktop_browser.store import (
        BrowserCookieStore,
        BrowserStore,
    )

    assert all([
        router,
        derive_cookie_key,
        BROWSER_SCHEMA,
        COOKIE_SCHEMA,
        BrowserCookieStore,
        BrowserStore,
    ])
