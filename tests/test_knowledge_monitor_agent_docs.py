import pytest
import pytest_asyncio
from pathlib import Path

from tinyagentos.knowledge_monitor import ingest_agent_docs
from tinyagentos.knowledge_store import KnowledgeStore


@pytest_asyncio.fixture
async def store(tmp_path):
    s = KnowledgeStore(tmp_path / "knowledge.db")
    await s.init()
    yield s
    await s.close()


@pytest.mark.asyncio
async def test_ingest_populates_store(tmp_path, store):
    docs = tmp_path / "docs" / "agents"
    docs.mkdir(parents=True)
    (docs / "getting-started.md").write_text("# Getting Started\n\nFirst content.\n")
    (docs / "recipes").mkdir()
    (docs / "recipes" / "managing.md").write_text("# Managing\n\nRecipe body.\n")

    count = await ingest_agent_docs(docs_dir=docs, knowledge_store=store)
    assert count == 2

    items = await store.list_items(source_type="agent-docs")
    paths = sorted(i["source_url"] for i in items)
    assert paths == ["getting-started.md", "recipes/managing.md"]
    titles = sorted(i["title"] for i in items)
    assert titles == ["Getting Started", "Managing"]
    for i in items:
        assert "agent-docs" in i["categories"]


@pytest.mark.asyncio
async def test_ingest_idempotent_replaces_prior_entries(tmp_path, store):
    docs = tmp_path / "docs" / "agents"
    docs.mkdir(parents=True)
    f = docs / "doc.md"
    f.write_text("# Original\n\nv1 content.\n")
    await ingest_agent_docs(docs_dir=docs, knowledge_store=store)

    # Update content; re-ingest
    f.write_text("# Updated\n\nv2 content.\n")
    count = await ingest_agent_docs(docs_dir=docs, knowledge_store=store)
    assert count == 1

    items = await store.list_items(source_type="agent-docs")
    assert len(items) == 1
    assert items[0]["title"] == "Updated"
    assert "v2 content" in items[0]["content"]
    assert "v1 content" not in items[0]["content"]


@pytest.mark.asyncio
async def test_ingest_missing_dir_returns_zero(tmp_path, store):
    nonexistent = tmp_path / "no" / "such" / "dir"
    count = await ingest_agent_docs(docs_dir=nonexistent, knowledge_store=store)
    assert count == 0
    items = await store.list_items(source_type="agent-docs")
    assert items == []


@pytest.mark.asyncio
async def test_ingest_uses_filename_when_no_h1(tmp_path, store):
    docs = tmp_path / "docs" / "agents"
    docs.mkdir(parents=True)
    (docs / "no-heading.md").write_text("No H1 here, just paragraph text.\n")
    await ingest_agent_docs(docs_dir=docs, knowledge_store=store)
    items = await store.list_items(source_type="agent-docs")
    assert items[0]["title"] == "no-heading.md"
