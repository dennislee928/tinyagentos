import pytest


@pytest.mark.asyncio
async def test_same_idempotency_key_returns_same_response(client):
    """Same key + same body → second request returns cached response, no duplicate side effects."""
    headers = {"Idempotency-Key": "key-A"}
    body = {"name": "idem-same", "host": "192.0.2.10", "qmd_index": "test"}
    resp_a = await client.post("/api/agents", headers=headers, json=body)
    resp_b = await client.post("/api/agents", headers=headers, json=body)
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json() == resp_b.json()
    listing = (await client.get("/api/agents")).json()
    matching = [a for a in listing if a["name"].startswith("idem-same")]
    assert len(matching) == 1, f"expected one agent, got {matching}"


@pytest.mark.asyncio
async def test_different_idempotency_key_processes_normally(client):
    """Different keys with same body → two real requests; second auto-suffixes."""
    body = {"name": "idem-diff", "host": "192.0.2.10", "qmd_index": "test"}
    resp_a = await client.post("/api/agents", headers={"Idempotency-Key": "k1"}, json=body)
    resp_b = await client.post("/api/agents", headers={"Idempotency-Key": "k2"}, json=body)
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()["name"] == "idem-diff"
    assert resp_b.json()["name"] == "idem-diff-2"


@pytest.mark.asyncio
async def test_no_idempotency_key_processes_normally(client):
    """Without an Idempotency-Key header, requests are NOT cached."""
    body = {"name": "idem-nokey", "host": "192.0.2.10", "qmd_index": "test"}
    resp_a = await client.post("/api/agents", json=body)
    resp_b = await client.post("/api/agents", json=body)
    assert resp_a.json()["name"] == "idem-nokey"
    assert resp_b.json()["name"] == "idem-nokey-2"
