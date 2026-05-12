"""GET /api — discovery index for the taOS REST API.

Returns the list of top-level route prefixes with titles and doc_urls. Agents
use this to discover what's available in one round-trip; the per-endpoint
contract lives in /openapi.json. Auth/scope gating happens on the actual
calls, not here.

Hand-maintained for Pass 1 — Pass 2+ may auto-generate from app.routes once
every app declares its agent-facing surface explicitly.
"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


_INDEX = [
    {
        "prefix": "/api/agents",
        "title": "Agents",
        "doc_url": "/docs/agents/recipes/managing-agents.md",
    },
    {
        "prefix": "/api/ui/notify",
        "title": "UI: notify the user",
        "doc_url": "/docs/agents/recipes/notifying-the-user.md",
    },
    {
        "prefix": "/api/knowledge",
        "title": "Knowledge library",
        "doc_url": "/docs/agents/getting-started.md#knowledge",
    },
]


@router.get("/api", summary="Discover the taOS REST API surface")
async def api_index():
    """Returns the list of top-level route prefixes with titles and relative
    doc URLs. Use this to discover what's available; combine with
    `/openapi.json` for the full per-endpoint contract.

    Pass 2 will land additional rows as each app's audit completes."""
    return {"routes": _INDEX}
