import pytest


CANONICAL_KEYS = {"error", "detail", "fix", "doc_url"}


@pytest.mark.asyncio
async def test_404_uses_canonical_error_shape(client):
    resp = await client.get("/api/agents/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body.keys()) == CANONICAL_KEYS
    assert body["error"] == "agent_not_found"
    assert "does-not-exist" in body["detail"]
    assert body["fix"]
    assert body["doc_url"]


@pytest.mark.asyncio
async def test_404_update_unknown_agent_uses_canonical_shape(client):
    resp = await client.put("/api/agents/does-not-exist", json={"host": "1.2.3.4"})
    assert resp.status_code == 404
    body = resp.json()
    assert set(body.keys()) == CANONICAL_KEYS
    assert body["error"] == "agent_not_found"


@pytest.mark.asyncio
async def test_422_validation_uses_canonical_error_shape(client):
    """Pydantic validation errors are 422 (not 400) and use canonical shape."""
    resp = await client.post("/api/agents", json={})  # missing required fields
    assert resp.status_code == 422
    body = resp.json()
    assert set(body.keys()) == CANONICAL_KEYS
    assert body["error"] == "validation_error"
    assert body["fix"]
    assert body["doc_url"]


@pytest.mark.asyncio
async def test_400_invalid_agent_name_uses_canonical_shape(client):
    """400 from validate_agent_name (application-level validation)."""
    resp = await client.post("/api/agents", json={"name": "", "host": "1.2.3.4", "qmd_index": "test"})
    assert resp.status_code == 400
    body = resp.json()
    assert set(body.keys()) == CANONICAL_KEYS
    assert body["fix"]
