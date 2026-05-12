import pytest


@pytest.mark.asyncio
async def test_token_with_agents_list_scope_can_list(client, app):
    """A bearer token scoped agents.list authenticates GET /api/agents."""
    store = app.state.agent_tokens_store
    plaintext, _ = await store.issue(agent_id="scope-r", user_id="u", scope=["agents.list"])
    resp = await client.get("/api/agents", headers={"Authorization": f"Bearer {plaintext}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_token_with_narrow_scope_cannot_create(client, app):
    """agents.list scope must NOT cover agents.create — POST /api/agents returns 403."""
    store = app.state.agent_tokens_store
    plaintext, _ = await store.issue(agent_id="scope-narrow", user_id="u", scope=["agents.list"])
    resp = await client.post(
        "/api/agents",
        headers={"Authorization": f"Bearer {plaintext}"},
        json={"name": "scope-target", "host": "192.0.2.10", "qmd_index": "test"},
    )
    assert resp.status_code == 403
    body = resp.json()
    assert body["error"] == "scope_denied"
    assert body["fix"]
    assert body["doc_url"]
    assert "agents.create" in body["detail"]


@pytest.mark.asyncio
async def test_wildcard_scope_covers_everything(client, app):
    """scope=['*'] is full access."""
    store = app.state.agent_tokens_store
    plaintext, _ = await store.issue(agent_id="scope-wide", user_id="u", scope=["*"])
    h = {"Authorization": f"Bearer {plaintext}"}
    assert (await client.get("/api/agents", headers=h)).status_code == 200
    resp = await client.post(
        "/api/agents", headers=h,
        json={"name": "wide-target", "host": "192.0.2.10", "qmd_index": "test"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_session_cookie_user_bypasses_scope(client):
    """The client fixture's session cookie should authenticate WITHOUT any scope gate
    (scope is a delegated-access mechanism for agents only; logged-in humans have full
    access)."""
    resp = await client.post(
        "/api/agents",
        json={"name": "session-target", "host": "192.0.2.10", "qmd_index": "test"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_namespace_glob_covers_subverbs(client, app):
    """scope=['agents.token.*'] should cover agents.token.issue and agents.token.revoke."""
    store = app.state.agent_tokens_store
    plaintext, _ = await store.issue(agent_id="scope-glob", user_id="u", scope=["agents.token.*", "agents.create"])
    h = {"Authorization": f"Bearer {plaintext}"}
    # Need an agent to issue a token for first
    await client.post(
        "/api/agents", headers=h,
        json={"name": "glob-target", "host": "192.0.2.10", "qmd_index": "test"},
    )
    issue_resp = await client.post("/api/agents/glob-target/token/issue", headers=h)
    assert issue_resp.status_code == 200
    revoke_resp = await client.delete("/api/agents/glob-target/token", headers=h)
    assert revoke_resp.status_code == 204
