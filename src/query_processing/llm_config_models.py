"""Pydantic discriminated union for LLM provider configuration.

Replaces the loose ``Dict[str, Optional[str]]`` that was passed between write
paths with no cross-field consistency enforcement. The union makes invalid
provider configs structurally unrepresentable:

- ``GeminiConfig`` has no ``base_url`` / ``organization`` fields, so a Gemini
  config can never carry an OpenRouter/OpenAI URL.
- ``OpenAICompatibleConfig`` carries ``base_url`` / ``organization``.
- A field validator on ``api_key`` clears keys that clearly belong to a
  different provider (e.g. an ``sk-or-`` key under a Gemini config) so the
  env-detection fallback can backfill the correct key on the next switch.

The union is the request body type for ``PUT /v1/settings/llm`` (FastAPI
validates at the boundary and returns 422 for unknown providers) and is also
used internally to validate DB reads and profile writes via
``validate_llm_config``.
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

# Provider-specific key prefixes for cross-contamination detection.
# Mirrors the previous ``_api_key_matches_provider`` heuristic but lives on the
# config model so a wrong-provider key is cleared at parse time, before it can
# be persisted or returned to a caller.
_OPENROUTER_KEY_PREFIX = "sk-or-"
_OPENAI_KEY_PREFIX = "sk-"
_GEMINI_KEY_PREFIX = "AIza"


class GeminiConfig(BaseModel):
    """LLM config for Google Gemini (native API, no base_url)."""

    model_config = ConfigDict(extra="ignore")

    provider: Literal["gemini"]
    api_key: Optional[str] = None
    model_main: Optional[str] = None
    model_lite: Optional[str] = None
    model_relevance: Optional[str] = None
    # NO base_url, NO organization — structurally impossible on Gemini.

    @field_validator("api_key")
    @classmethod
    def _clear_cross_provider_key(cls, v: Optional[str]) -> Optional[str]:
        """Clear keys that clearly belong to an OpenAI-compatible provider.

        A Gemini key starts with ``AIza``; OpenAI/OpenRouter keys start with
        ``sk-``. If a wrong-provider key leaked in (e.g. from a stale profile),
        clear it so the env-detection fallback can backfill the correct key on
        the next switch.
        """
        if v and (v.startswith(_OPENROUTER_KEY_PREFIX) or v.startswith(_OPENAI_KEY_PREFIX)):
            return None
        return v


class OpenAICompatibleConfig(BaseModel):
    """LLM config for any OpenAI-compatible endpoint.

    Covers OpenAI (api.openai.com), Ollama (localhost:11434), OpenRouter
    (openrouter.ai), Groq, Together, vLLM, LM Studio, etc.
    """

    model_config = ConfigDict(extra="ignore")

    provider: Literal["openai_compatible"]
    api_key: Optional[str] = None
    base_url: Optional[str] = None  # defaulted in the route handler, not here
    model_main: Optional[str] = None
    model_lite: Optional[str] = None
    model_relevance: Optional[str] = None
    organization: Optional[str] = None

    @field_validator("api_key")
    @classmethod
    def _clear_cross_provider_key(cls, v: Optional[str]) -> Optional[str]:
        """Clear keys that clearly belong to Gemini (``AIza`` prefix)."""
        if v and v.startswith(_GEMINI_KEY_PREFIX):
            return None
        return v


# Discriminated union — FastAPI uses this directly as a request body type.
# For internal validation (DB reads, profile validation), use
# ``validate_llm_config`` (backed by a module-level TypeAdapter).
LLMConfig = Annotated[
    Union[GeminiConfig, OpenAICompatibleConfig],
    Field(discriminator="provider"),
]

# TypeAdapter for validating raw dicts against the union outside of FastAPI.
# Annotated types don't have ``.model_validate``; TypeAdapter is the
# Pydantic v2 way to validate against a type alias.
_llm_config_adapter = TypeAdapter(LLMConfig)


def validate_llm_config(raw: dict):
    """Validate a raw dict through the discriminated union.

    Returns the validated config model (``GeminiConfig`` or
    ``OpenAICompatibleConfig``), or ``None`` when no provider is set
    (unconfigured state).

    Raises:
        pydantic.ValidationError: on invalid configs (e.g. unknown provider, or
            a required field missing for the discriminated member).
    """
    if not raw or not raw.get("provider"):
        return None
    return _llm_config_adapter.validate_python(raw)


# All keys that ``get_llm_settings()`` must return, for backward compatibility
# with dict-access callers (``settings["provider"]``, ``settings["base_url"]``).
_ALL_LLM_KEYS = (
    "provider",
    "api_key",
    "base_url",
    "model_main",
    "model_lite",
    "model_relevance",
    "organization",
)


def config_to_dict(config) -> dict:
    """Convert a validated LLMConfig model to a full dict with all 7 keys.

    Fields that don't exist on the provider-specific model (e.g. ``base_url``
    on ``GeminiConfig``) are filled with ``None`` so dict-access callers keep
    working without ``KeyError``.
    """
    result = {k: None for k in _ALL_LLM_KEYS}
    if config is not None:
        result.update(config.model_dump())
    return result


__all__ = [
    "GeminiConfig",
    "OpenAICompatibleConfig",
    "LLMConfig",
    "validate_llm_config",
    "config_to_dict",
]
