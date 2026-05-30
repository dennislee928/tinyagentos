import pytest
from tinyagentos.userspace.broker import handle_capability, FREE_CAPS, GATED_CAPS
from tinyagentos.userspace.data_store import UserspaceDataStore


async def _store(tmp_path):
    s = UserspaceDataStore(tmp_path / "d.db"); await s.init(); return s


@pytest.mark.asyncio
async def test_ungranted_gated_capability_denied(tmp_path):
    s = await _store(tmp_path)
    out = await handle_capability("todo", "app.memory.search", {"q": "x"},
                                  granted=[], data_store=s, app_dir=tmp_path / "todo", services={})
    assert out == {"error": "permission_denied", "capability": "app.memory.search"}
    await s.close()


@pytest.mark.asyncio
async def test_free_kv_capability_allowed_and_scoped(tmp_path):
    s = await _store(tmp_path)
    await handle_capability("todo", "app.kv.set", {"key": "k", "value": 1},
                            granted=[], data_store=s, app_dir=tmp_path / "todo", services={})
    out = await handle_capability("todo", "app.kv.get", {"key": "k"},
                                  granted=[], data_store=s, app_dir=tmp_path / "todo", services={})
    assert out["result"] == 1
    other = await handle_capability("evil", "app.kv.get", {"key": "k"},
                                    granted=[], data_store=s, app_dir=tmp_path / "evil", services={})
    assert other["result"] is None   # evil app cannot see todo's data
    await s.close()


@pytest.mark.asyncio
async def test_table_capabilities(tmp_path):
    s = await _store(tmp_path)
    ins = await handle_capability("todo", "app.table.insert", {"table": "t", "row": {"x": 1}},
                                  granted=[], data_store=s, app_dir=tmp_path / "todo", services={})
    assert isinstance(ins["result"], int)
    q = await handle_capability("todo", "app.table.query", {"table": "t"},
                                granted=[], data_store=s, app_dir=tmp_path / "todo", services={})
    assert q["result"][0]["x"] == 1
    await s.close()


@pytest.mark.asyncio
async def test_gated_capability_allowed_when_granted(tmp_path):
    s = await _store(tmp_path)

    class FakeMemory:
        async def search(self, q):
            return [{"text": "hit"}]

    out = await handle_capability("todo", "app.memory.search", {"q": "x"},
                                  granted=["app.memory"], data_store=s,
                                  app_dir=tmp_path / "todo", services={"memory": FakeMemory()})
    assert out["result"] == [{"text": "hit"}]
    await s.close()


@pytest.mark.asyncio
async def test_files_jailed_to_app_dir(tmp_path):
    s = await _store(tmp_path)
    (tmp_path / "todo" / "files").mkdir(parents=True)
    out = await handle_capability("todo", "app.files.read", {"path": "../../etc/passwd"},
                                  granted=[], data_store=s, app_dir=tmp_path / "todo", services={})
    assert out["error"] == "invalid_path"
    # legit write+read within the jail works
    await handle_capability("todo", "app.files.write", {"path": "note.txt", "content": "hi"},
                            granted=[], data_store=s, app_dir=tmp_path / "todo", services={})
    rd = await handle_capability("todo", "app.files.read", {"path": "note.txt"},
                                 granted=[], data_store=s, app_dir=tmp_path / "todo", services={})
    assert rd["result"] == "hi"
    await s.close()


@pytest.mark.asyncio
async def test_unknown_capability_rejected(tmp_path):
    s = await _store(tmp_path)
    out = await handle_capability("todo", "app.evil.hack", {}, granted=["app.evil"],
                                  data_store=s, app_dir=tmp_path / "todo", services={})
    assert out["error"] == "unknown_capability"
    await s.close()


def test_capability_sets():
    assert "app.net" in GATED_CAPS and "app.memory" in GATED_CAPS
    assert "app.kv" in FREE_CAPS and "app.net" not in FREE_CAPS
