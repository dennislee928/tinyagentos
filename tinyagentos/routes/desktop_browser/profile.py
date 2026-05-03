"""Profile CRUD + default-profile bootstrap.

Profiles are within-user namespaces ("Personal", "Work", …) that
isolate cookie jars, history, bookmarks, and agent capability grants.
Every taOS user gets the two default profiles on their first visit
to the browser app — `ensure_default_profiles` is idempotent so
calling it on every request is cheap and safe.

The full CRUD surface (rename, delete, custom colour, profile picker
in the chrome) lands in PR 5. PR 3 only needs:

- ensure_default_profiles  — bootstrap
- get_profile_or_404      — used by the proxy endpoint to validate
                            the `profile_id` query param
"""
from __future__ import annotations

import time

from tinyagentos.routes.desktop_browser.store import BrowserStore


# Defaults bootstrapped per user. profile_id is the URL-safe identifier;
# name is the human-facing label. Colour matches the chrome chip in
# PR 4's frontend mockups.
_DEFAULTS = (
    {"profile_id": "personal", "name": "Personal", "color": "#6c8df0"},
    {"profile_id": "work",     "name": "Work",     "color": "#f5b86b"},
)


class ProfileNotFoundError(Exception):
    """Raised when a (user_id, profile_id) lookup fails."""


async def ensure_default_profiles(store: BrowserStore, *, user_id: str) -> None:
    """Idempotent bootstrap: create Personal + Work for the user if absent."""
    if not user_id:
        raise ValueError("user_id is required")

    existing = await store.list_profiles(user_id=user_id)
    have_ids = {p["profile_id"] for p in existing}
    now = int(time.time())

    for default in _DEFAULTS:
        if default["profile_id"] in have_ids:
            continue
        await store.add_profile(
            user_id=user_id,
            profile_id=default["profile_id"],
            name=default["name"],
            color=default["color"],
            created_at=now,
        )


async def get_profile_or_404(
    store: BrowserStore, *, user_id: str, profile_id: str,
) -> dict:
    """Return the profile dict, raise ProfileNotFoundError if missing.

    The lookup is per-user — user A asking for user B's profile_id
    raises just as if the profile did not exist.
    """
    if not user_id:
        raise ValueError("user_id is required")
    if not profile_id:
        raise ValueError("profile_id is required")

    profiles = await store.list_profiles(user_id=user_id)
    for p in profiles:
        if p["profile_id"] == profile_id:
            return p

    raise ProfileNotFoundError(
        f"profile {profile_id!r} not found for user {user_id!r}"
    )
