"""LLM client factory.

Reads provider configuration from SQLite (app_settings table) with .env fallback,
and instantiates the appropriate LLMClient implementation.

Resolution order:
1. SQLite app_settings table (set via /v1/settings/llm endpoint)
2. .env environment variables (GEMINI_API_KEY, OPENAI_API_KEY, etc.)
3. Raise error if no provider is configured

If the opposite provider is also configured in the environment, a
FallbackLLMClient is returned so that 429 / quota errors automatically switch
providers without user intervention.
"""

from typing import Optional, Dict
from loguru import logger

from ..config import get_settings
from ..db.database import get_connection
from ..db.app_settings import save_app_settings
from .gemini_client import GeminiClient
from .openai_client import OpenAICompatibleClient
from .fallback_llm_client import FallbackLLMClient
from .llm_provider import LLMClient


# Keys stored in the app_settings table
SETTING_KEY_PROVIDER = "llm_provider"          # "gemini" | "openai_compatible"
SETTING_KEY_API_KEY = "llm_api_key"            # encrypted at rest in future
SETTING_KEY_BASE_URL = "llm_base_url"          # e.g. "https://api.openai.com/v1"
SETTING_KEY_MODEL_MAIN = "llm_model_main"      # e.g. "gpt-4.1-mini"
SETTING_KEY_MODEL_LITE = "llm_model_lite"      # e.g. "gpt-4.1-mini" (or None)
SETTING_KEY_MODEL_RELEVANCE = "llm_model_relevance"  # e.g. "gpt-4.1-mini" (defaults to model_lite or model_main)
SETTING_KEY_ORG = "llm_organization"           # OpenAI org ID (optional)


def _read_settings_from_db() -> Dict[str, Optional[str]]:
    """Read LLM settings from the app_settings SQLite table.

    Returns:
        Dict with keys: provider, api_key, base_url, model_main, model_lite, organization.
        Values are None if not set.
    """
    result: Dict[str, Optional[str]] = {
        "provider": None,
        "api_key": None,
        "base_url": None,
        "model_main": None,
        "model_lite": None,
        "model_relevance": None,
        "organization": None,
    }

    try:
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, value FROM app_settings WHERE key LIKE 'llm_%'"
            )
            for row in cursor.fetchall():
                key = row["key"]
                value = row["value"]
                if key == SETTING_KEY_PROVIDER:
                    result["provider"] = value
                elif key == SETTING_KEY_API_KEY:
                    result["api_key"] = value
                elif key == SETTING_KEY_BASE_URL:
                    result["base_url"] = value
                elif key == SETTING_KEY_MODEL_MAIN:
                    result["model_main"] = value
                elif key == SETTING_KEY_MODEL_LITE:
                    result["model_lite"] = value
                elif key == SETTING_KEY_MODEL_RELEVANCE:
                    result["model_relevance"] = value
                elif key == SETTING_KEY_ORG:
                    result["organization"] = value
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"Could not read LLM settings from DB: {e}")

    return result


def _write_settings_to_db(settings_dict: Dict[str, Optional[str]]) -> None:
    """Write LLM settings to the app_settings SQLite table.

    Thin wrapper around the shared save_app_settings helper.
    """
    save_app_settings(settings_dict)


def get_llm_settings() -> Dict[str, Optional[str]]:
    """Get current LLM settings (from DB with .env fallback).

    Returns:
        Dict with provider, api_key, base_url, model_main, model_lite,
        model_relevance, organization.
    """
    db_settings = _read_settings_from_db()
    env_settings = get_settings()

    # If DB has a provider configured, use it
    if db_settings["provider"]:
        return db_settings

    # Fall back to .env: if GEMINI_API_KEY is set, use Gemini
    if env_settings.GEMINI_API_KEY:
        return {
            "provider": "gemini",
            "api_key": env_settings.GEMINI_API_KEY,
            "base_url": None,
            "model_main": None,  # Use settings defaults
            "model_lite": None,
            "model_relevance": None,  # Defaults to GEMINI_MODEL_LITE
            "organization": None,
        }

    # Fall back to .env: if OPENAI_API_KEY is set, use OpenAI-compatible
    if env_settings.OPENAI_API_KEY:
        return {
            "provider": "openai_compatible",
            "api_key": env_settings.OPENAI_API_KEY,
            "base_url": "https://api.openai.com/v1",
            "model_main": "gpt-4.1-mini",
            "model_lite": "gpt-4.1-mini",
            "model_relevance": None,  # Defaults to model_lite (which falls back to model_main)
            "organization": None,
        }

    # No provider configured
    return {
        "provider": None,
        "api_key": None,
        "base_url": None,
        "model_main": None,
        "model_lite": None,
        "model_relevance": None,
        "organization": None,
    }


def is_llm_configured() -> bool:
    """Check if an LLM provider is configured (either in DB or .env)."""
    settings = get_llm_settings()
    return settings["provider"] is not None and settings["api_key"] is not None


def save_llm_settings(
    provider: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model_main: Optional[str] = None,
    model_lite: Optional[str] = None,
    model_relevance: Optional[str] = None,
    organization: Optional[str] = None,
) -> None:
    """Save LLM settings to the app_settings table.

    If api_key is None, the existing key is preserved (not overwritten).

    Args:
        provider: "gemini" or "openai_compatible"
        api_key: API key (None to preserve existing)
        base_url: Base URL for OpenAI-compatible providers
        model_main: Primary model name
        model_lite: Lite model name (optional)
        model_relevance: Model for post-generation relevance check (optional;
            defaults to model_lite, or model_main if no lite is configured)
        organization: OpenAI organization ID (optional)
    """
    settings_to_write: Dict[str, Optional[str]] = {
        SETTING_KEY_PROVIDER: provider,
    }

    # Only write api_key if provided (None means "keep existing")
    if api_key is not None:
        settings_to_write[SETTING_KEY_API_KEY] = api_key
    if base_url is not None:
        settings_to_write[SETTING_KEY_BASE_URL] = base_url
    if model_main is not None:
        settings_to_write[SETTING_KEY_MODEL_MAIN] = model_main
    if model_lite is not None:
        settings_to_write[SETTING_KEY_MODEL_LITE] = model_lite
    if model_relevance is not None:
        settings_to_write[SETTING_KEY_MODEL_RELEVANCE] = model_relevance
    if organization is not None:
        settings_to_write[SETTING_KEY_ORG] = organization

    _write_settings_to_db(settings_to_write)


def _create_single_client(settings: Dict[str, Optional[str]]):
    """Create a single provider client from a settings dict.

    Args:
        settings: Dict with keys provider, api_key, base_url, model_main,
            model_lite, model_relevance, organization.

    Returns:
        GeminiClient or OpenAICompatibleClient instance.

    Raises:
        ValueError: If the provider is unknown or missing required fields.
    """
    provider = settings["provider"]
    api_key = settings["api_key"]

    if provider == "gemini":
        # ponytail: relevance model defaults to GEMINI_MODEL_LITE inside GeminiClient.
        return GeminiClient(
            api_key=api_key,
            model_relevance=settings.get("model_relevance"),
        )

    if provider == "openai_compatible":
        if not api_key:
            raise ValueError("OpenAI-compatible provider requires an API key")
        base_url = settings["base_url"] or "https://api.openai.com/v1"
        model_main = settings["model_main"] or "gpt-4.1-mini"
        model_lite = settings["model_lite"] or model_main
        model_relevance = settings.get("model_relevance") or model_lite
        organization = settings["organization"]

        return OpenAICompatibleClient(
            api_key=api_key,
            base_url=base_url,
            model_main=model_main,
            model_lite=model_lite,
            model_relevance=model_relevance,
            organization=organization,
        )

    raise ValueError(f"Unknown LLM provider: {provider}")


def _build_fallback_client(settings: Dict[str, Optional[str]]) -> Optional[LLMClient]:
    """Build a fallback client from the opposite provider if its API key is configured.

    The fallback reads from environment variables, so the primary provider can be
    switched via the UI while the fallback remains available as long as the other
    API key is set in .env.
    """
    env_settings = get_settings()
    primary = settings["provider"]

    if primary == "gemini" and env_settings.OPENAI_API_KEY:
        base_url = getattr(env_settings, "OPENAI_BASE_URL", None) or "https://api.openai.com/v1"
        model_main = getattr(env_settings, "OPENAI_MODEL", None) or "gpt-4.1-mini"
        model_lite = getattr(env_settings, "OPENAI_MODEL_LITE", None) or model_main
        model_relevance = getattr(env_settings, "OPENAI_MODEL_RELEVANCE", None) or model_lite
        organization = getattr(env_settings, "OPENAI_ORGANIZATION", None)
        return OpenAICompatibleClient(
            api_key=env_settings.OPENAI_API_KEY,
            base_url=base_url,
            model_main=model_main,
            model_lite=model_lite,
            model_relevance=model_relevance,
            organization=organization,
        )

    if primary == "openai_compatible" and env_settings.GEMINI_API_KEY:
        return GeminiClient(api_key=env_settings.GEMINI_API_KEY)

    return None


def create_llm_client():
    """Create and return the appropriate LLMClient based on configured settings.

    Resolution order:
    1. SQLite app_settings table (set via /v1/settings/llm endpoint)
    2. .env environment variables

    If the opposite provider is also configured in .env, the returned client is a
    FallbackLLMClient that will automatically switch providers on quota errors.

    Returns:
        GeminiClient, OpenAICompatibleClient, or FallbackLLMClient instance.

    Raises:
        ValueError: If no provider is configured.
    """
    settings = get_llm_settings()
    if settings["provider"] is None:
        raise ValueError(
            "No LLM provider configured. "
            "Set up via the /v1/settings/llm endpoint or configure GEMINI_API_KEY / "
            "OPENAI_API_KEY in your .env file."
        )

    primary = _create_single_client(settings)
    fallback = _build_fallback_client(settings)
    if fallback is None:
        return primary

    logger.info(
        f"Primary LLM provider: {settings['provider']} ({primary.model_main}), "
        f"fallback provider: {fallback.model_main}"
    )
    return FallbackLLMClient(primary, fallback)
