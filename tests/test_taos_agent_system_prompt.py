import pytest
import pytest_asyncio
from pathlib import Path

from tinyagentos.knowledge_store import KnowledgeStore
from tinyagentos.routes.taos_agent import build_system_prompt


@pytest_asyncio.fixture
async def store(tmp_path):
    s = KnowledgeStore(tmp_path / "knowledge.db")
    await s.init()
    yield s
    await s.close()


async def _seed(store, *, title: str, content: str, source_id: str = "taos-core"):
    await store.add_item(
        source_type="agent-docs",
        source_url=title.lower().replace(" ", "-") + ".md",
        title=title,
        author="taOS docs",
        content=content,
        summary=content[:80],
        categories=["agent-docs"],
        tags=[],
        metadata={"source": "docs/agents", "origin": source_id},
        source_id=source_id,
        status="ready",
    )


@pytest.mark.asyncio
async def test_build_system_prompt_concatenates_agent_docs(store):
    await _seed(store, title="README", content="taOS agent documentation overview.")
    await _seed(store, title="Getting Started", content="First call instructions here.")

    prompt = await build_system_prompt(store)

    assert "taOS agent documentation overview" in prompt
    assert "First call instructions here" in prompt
    # Section headings derived from titles so the LLM can navigate
    assert "README" in prompt
    assert "Getting Started" in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_includes_app_guides(store):
    """Per-app guides also live in agent-docs and should be in the prompt."""
    await _seed(store, title="Core README", content="canonical taOS docs.")
    await _seed(store, title="My App Guide", content="how to use my app.", source_id="app:my-app")

    prompt = await build_system_prompt(store)

    assert "canonical taOS docs" in prompt
    assert "how to use my app" in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_empty_store_returns_empty(store, tmp_path, monkeypatch):
    from tinyagentos.routes import taos_agent
    # Patch _MANUAL_PATH to a non-existent path so no fallback fires.
    monkeypatch.setattr(taos_agent, "_MANUAL_PATH", tmp_path / "no-manual.md")
    prompt = await build_system_prompt(store)
    assert prompt == ""


@pytest.mark.asyncio
async def test_build_system_prompt_falls_back_to_legacy_manual(store, tmp_path, monkeypatch):
    """When the store has no agent-docs items, fall back to the legacy
    docs/taos-agent-manual.md file so existing deployments keep working
    until the first successful ingest."""
    from tinyagentos.routes import taos_agent
    fake_manual = tmp_path / "taos-agent-manual.md"
    fake_manual.write_text("legacy manual content from file.")
    monkeypatch.setattr(taos_agent, "_MANUAL_PATH", fake_manual)
    prompt = await build_system_prompt(store)
    assert "legacy manual content from file" in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_no_store_returns_empty():
    """If knowledge_store is None (lifespan not run), return empty string
    rather than crashing."""
    prompt = await build_system_prompt(None)
    assert prompt == ""
