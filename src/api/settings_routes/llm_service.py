"""Shared helpers for the LLM settings routes."""

from typing import Optional
from fastapi import HTTPException

from ...query_processing.gemini_client import GeminiClient
from ...query_processing.openai_client import OpenAICompatibleClient
from ...query_processing.llm_config_models import validate_llm_config, config_to_dict
from ...db.app_settings import save_app_settings


# DB column names for the LLM settings keys.
_LLM_DB_KEYS = (
    "llm_provider",
    "llm_api_key",
    "llm_base_url",
    "llm_model_main",
    "llm_model_lite",
    "llm_model_relevance",
    "llm_organization",
)


def _write_llm_settings(settings: dict) -> None:
    """Write a complete LLM settings dict to the DB, including None values.

    Validates the dict through the discriminated union before persisting so a
    mixed-provider config (e.g. ``provider="gemini"`` + ``base_url="..."``)
    can never be written to the DB. The union structurally drops impossible
    fields (``extra="ignore"``) and clears wrong-provider API keys (field
    validator), replacing the old ``sanitize_llm_settings`` runtime guard.
    """
    if not settings.get("provider"):
        # Unconfigured state — write all keys as None so a rollback can restore
        # the previous configuration exactly.
        save_app_settings({k: None for k in _LLM_DB_KEYS})
        return

    try:
        config = validate_llm_config(settings)
    except Exception as e:
        raise ValueError(f"Invalid LLM config: {e}") from e

    if config is None:
        # provider was None/empty after validation — treat as unconfigured
        save_app_settings({k: None for k in _LLM_DB_KEYS})
        return

    d = config_to_dict(config)
    save_app_settings({
        "llm_provider": d["provider"],
        "llm_api_key": d["api_key"],
        "llm_base_url": d["base_url"],
        "llm_model_main": d["model_main"],
        "llm_model_lite": d["model_lite"],
        "llm_model_relevance": d["model_relevance"],
        "llm_organization": d["organization"],
    })


def _validate_llm_models(provider: str, model_main: Optional[str], model_lite: Optional[str], model_relevance: Optional[str]) -> None:
    """Reject model names that are clearly intended for the other provider."""
    if provider == "gemini":
        validator = GeminiClient._is_valid_model
        display_name = "Gemini"
    else:
        validator = OpenAICompatibleClient._is_valid_model
        display_name = "OpenAI-compatible"

    for field, value in (
        ("model_main", model_main),
        ("model_lite", model_lite),
        ("model_relevance", model_relevance),
    ):
        if value is not None and not validator(value):
            raise HTTPException(
                status_code=400,
                detail=f"{field} '{value}' is not a valid {display_name} model ID",
            )
