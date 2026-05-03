"""BrowserApp v2 stores.

- BrowserStore  — regular SQLite, holds profiles/history/bookmarks/caps/push/windows
- BrowserCookieStore — SQLCipher-encrypted, holds cookies; per-user key

Both stores key every row on user_id for OS-grade multi-user isolation.
The query helpers refuse to operate without a user_id argument.
"""
from __future__ import annotations

from pathlib import Path

import aiosqlite

from tinyagentos.base_store import BaseStore
from tinyagentos.routes.desktop_browser.schema import BROWSER_SCHEMA


class BrowserStore(BaseStore):
    """Regular SQLite store: profiles, history, bookmarks, capabilities,
    push subscriptions, persisted browser-window state.

    Every accessor takes a user_id and refuses to operate without one.
    """
    SCHEMA = BROWSER_SCHEMA

    # Profile helpers (just enough for the multi-user tenancy tests in
    # Task 8 — the rest of the CRUD lands in PR 3 alongside profile.py).

    async def add_profile(
        self,
        *,
        user_id: str,
        profile_id: str,
        name: str,
        color: str | None = None,
        created_at: int,
    ) -> None:
        if not user_id:
            raise ValueError("user_id is required")
        if not profile_id:
            raise ValueError("profile_id is required")
        assert self._db is not None
        await self._db.execute(
            "INSERT INTO profiles (user_id, profile_id, name, color, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, profile_id, name, color, created_at),
        )
        await self._db.commit()

    async def list_profiles(self, *, user_id: str) -> list[dict]:
        if not user_id:
            raise ValueError("user_id is required")
        assert self._db is not None
        cursor = await self._db.execute(
            "SELECT profile_id, name, color, created_at "
            "FROM profiles WHERE user_id = ? ORDER BY created_at",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [
            {
                "profile_id": r[0],
                "name": r[1],
                "color": r[2],
                "created_at": r[3],
            }
            for r in rows
        ]
