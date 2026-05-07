"""Drift guard: ensure no other source file in the repo defines its own
provider type list. The canonical list lives in tinyagentos/providers/types.py.

If this test fails, you've added a new hardcoded provider list somewhere —
import from the canonical module instead. This is the bug class that
motivated #351."""
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[1]

# Files that legitimately reference these names (the canonical module + tests)
ALLOWLIST = {
    REPO_ROOT / "tinyagentos" / "providers" / "types.py",
    REPO_ROOT / "tests" / "test_provider_schema_canonical.py",
}

# Patterns that indicate a likely duplicate definition (assignment, not import)
PATTERNS = [
    re.compile(r"^\s*VALID_BACKEND_TYPES\s*=\s*[\{\[\(]"),
    re.compile(r"^\s*CLOUD_BACKEND_TYPES\s*=\s*[\{\[\(]"),
    re.compile(r"^\s*LOCAL_BACKEND_TYPES\s*=\s*[\{\[\(]"),
    re.compile(r"^\s*BACKEND_TYPE_MAP\s*=\s*[\{\[\(]"),
    re.compile(r"^\s*CHAT_BACKEND_TYPE_MAP\s*=\s*[\{\[\(]"),
]


def test_no_duplicate_provider_lists_in_python():
    """Walk every .py file in tinyagentos/ and tests/ — if any redefines
    a canonical name as an assignment (not an import), fail with the path."""
    offenders: list[str] = []
    for src_dir in (REPO_ROOT / "tinyagentos", REPO_ROOT / "tests"):
        for py in src_dir.rglob("*.py"):
            if py in ALLOWLIST:
                continue
            try:
                text = py.read_text(encoding="utf-8")
            except Exception:
                continue
            for line_no, line in enumerate(text.splitlines(), 1):
                for pattern in PATTERNS:
                    if pattern.search(line):
                        offenders.append(f"{py.relative_to(REPO_ROOT)}:{line_no}: {line.strip()}")
    assert not offenders, (
        "Hardcoded provider type lists found outside the canonical module. "
        "Import from tinyagentos.providers.types instead.\n"
        + "\n".join(offenders)
    )


def test_schema_module_exports_expected_types():
    """Sanity-check the canonical module itself exposes all expected types."""
    from tinyagentos.providers.types import (
        VALID_BACKEND_TYPES,
        CLOUD_BACKEND_TYPES,
        LOCAL_BACKEND_TYPES,
        BACKEND_TYPE_MAP,
        to_schema_dict,
    )

    # Spot-check key types are present
    assert "openai" in VALID_BACKEND_TYPES
    assert "ollama" in VALID_BACKEND_TYPES
    assert "sd-cpp" in VALID_BACKEND_TYPES
    assert "rknn-sd" in VALID_BACKEND_TYPES
    assert "openai-compatible" in VALID_BACKEND_TYPES

    # Category partitioning
    assert "openai" in CLOUD_BACKEND_TYPES
    assert "openai-compatible" in CLOUD_BACKEND_TYPES
    assert "ollama" in LOCAL_BACKEND_TYPES
    assert "rkllama" in LOCAL_BACKEND_TYPES

    # Cloud and local are disjoint
    assert CLOUD_BACKEND_TYPES.isdisjoint(LOCAL_BACKEND_TYPES)
    assert CLOUD_BACKEND_TYPES | LOCAL_BACKEND_TYPES == VALID_BACKEND_TYPES

    # LiteLLM prefix preservation from original BACKEND_TYPE_MAP
    assert BACKEND_TYPE_MAP["rkllama"] == "ollama"
    assert BACKEND_TYPE_MAP["anthropic"] == "anthropic"
    assert BACKEND_TYPE_MAP["openrouter"] == "openrouter"
    assert BACKEND_TYPE_MAP["kilocode"] == "openai"
    assert BACKEND_TYPE_MAP["openai-compatible"] == "openai"

    # Schema dict shape
    schema = to_schema_dict()
    assert isinstance(schema, list)
    assert len(schema) > 0
    assert all("id" in e and "category" in e and "litellm_prefix" in e for e in schema)


def test_adapters_built_from_canonical_schema():
    """Every provider type in the canonical schema gets an adapter; no stray
    adapters exist for types not in the schema."""
    from tinyagentos.providers.types import PROVIDERS_BY_ID
    from tinyagentos.backend_adapters import _ADAPTERS
    assert set(_ADAPTERS.keys()) == set(PROVIDERS_BY_ID.keys())


def test_chat_prefix_overrides_for_ollama_compat():
    """ollama and rkllama use the ollama_chat dispatcher prefix; everyone
    else falls back to their default litellm_prefix."""
    from tinyagentos.llm_proxy import CHAT_BACKEND_TYPE_MAP
    assert CHAT_BACKEND_TYPE_MAP.get("ollama") == "ollama_chat"
    assert CHAT_BACKEND_TYPE_MAP.get("rkllama") == "ollama_chat"
    assert CHAT_BACKEND_TYPE_MAP.get("openai") == "openai"  # falls through
