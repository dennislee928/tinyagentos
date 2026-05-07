"""Single source of truth for provider type definitions.

Adding a new provider type means adding ONE entry here. All three backend
consumers (config validation, route classification, LiteLLM routing) and
the frontend schema endpoint read from this module. Do not duplicate
these lists elsewhere — that's exactly the failure mode that motivated
issue #351."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal


ProviderCategory = Literal["cloud", "local"]


@dataclass(frozen=True)
class ProviderTypeSpec:
    """One row of the provider catalog."""
    id: str                         # e.g. "openai", "openai-compatible", "ollama"
    category: ProviderCategory      # "cloud" or "local"
    label: str                      # human-friendly display name
    description: str                # short marketing line for the picker
    default_url: str = ""           # prefilled URL; empty for cloud types with hardcoded chips
    key_placeholder: str = ""       # placeholder for the API key field (cloud only typically)
    litellm_prefix: str = "openai"  # LiteLLM model-prefix this routes through


_PROVIDERS: tuple[ProviderTypeSpec, ...] = (
    # Cloud
    ProviderTypeSpec(id="openai", category="cloud", label="OpenAI",
        description="GPT-4o, o1, and more",
        default_url="https://api.openai.com/v1", key_placeholder="sk-...",
        litellm_prefix="openai"),
    ProviderTypeSpec(id="anthropic", category="cloud", label="Anthropic",
        description="Claude Sonnet, Opus, Haiku",
        default_url="https://api.anthropic.com/v1", key_placeholder="sk-ant-...",
        litellm_prefix="anthropic"),
    ProviderTypeSpec(id="openrouter", category="cloud", label="OpenRouter",
        description="300+ models via one API",
        default_url="https://openrouter.ai/api/v1", key_placeholder="sk-or-...",
        litellm_prefix="openrouter"),
    ProviderTypeSpec(id="kilocode", category="cloud", label="Kilo",
        description="500+ models, smart routing",
        default_url="https://api.kilo.ai/api/gateway", key_placeholder="kilo-...",
        litellm_prefix="openai"),
    ProviderTypeSpec(id="openai-compatible", category="cloud", label="OpenAI-Compatible",
        description="LiteLLM, llama.cpp server, vLLM, or any service exposing the OpenAI API",
        default_url="", key_placeholder="your-api-key",
        litellm_prefix="openai"),
    # Local
    ProviderTypeSpec(id="rkllama", category="local", label="rkllama",
        description="Rockchip RK35xx NPU runtime",
        default_url="http://localhost:8080",
        litellm_prefix="ollama"),
    ProviderTypeSpec(id="ollama", category="local", label="Ollama",
        description="Local LLM runtime",
        default_url="http://localhost:11434",
        litellm_prefix="ollama"),
    ProviderTypeSpec(id="llama-cpp", category="local", label="llama.cpp",
        description="C++ inference server for GGUF models",
        default_url="http://localhost:8080",
        litellm_prefix="openai"),
    ProviderTypeSpec(id="vllm", category="local", label="vLLM",
        description="High-throughput inference server",
        default_url="http://localhost:8000",
        litellm_prefix="openai"),
    ProviderTypeSpec(id="exo", category="local", label="EXO",
        description="Distributed inference cluster",
        litellm_prefix="openai"),
    ProviderTypeSpec(id="mlx", category="local", label="MLX",
        description="Apple Silicon native runtime",
        litellm_prefix="openai"),
    # NOTE: sd-cpp and rknn-sd were in VALID_BACKEND_TYPES — keep them so we don't regress
    ProviderTypeSpec(id="sd-cpp", category="local", label="stable-diffusion.cpp",
        description="C++ stable-diffusion runtime",
        litellm_prefix="openai"),
    ProviderTypeSpec(id="rknn-sd", category="local", label="rknn-sd",
        description="Rockchip NPU stable-diffusion",
        litellm_prefix="openai"),
)


PROVIDERS_BY_ID: dict[str, ProviderTypeSpec] = {p.id: p for p in _PROVIDERS}

VALID_BACKEND_TYPES: frozenset[str] = frozenset(p.id for p in _PROVIDERS)
CLOUD_BACKEND_TYPES: frozenset[str] = frozenset(p.id for p in _PROVIDERS if p.category == "cloud")
LOCAL_BACKEND_TYPES: frozenset[str] = frozenset(p.id for p in _PROVIDERS if p.category == "local")

# LiteLLM model-prefix routing — note rkllama maps to "ollama" (ollama-compat API)
# and kilocode maps to "openai" (OpenAI-compatible; api_base set explicitly).
# This matches the previously hardcoded BACKEND_TYPE_MAP in llm_proxy.py exactly.
BACKEND_TYPE_MAP: dict[str, str] = {p.id: p.litellm_prefix for p in _PROVIDERS}


def to_schema_dict() -> list[dict]:
    """Return the schema as a JSON-serialisable list (used by the API endpoint)."""
    return [asdict(p) for p in _PROVIDERS]
