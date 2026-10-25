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
from ipaddress import ip_address
from urllib.parse import urlparse
from loguru import logger
from pydantic import ValidationError

from ..config import get_settings
from ..db.database import get_connection
from ..db.llm_profile_manager import resolve_default_models
from .gemini_client import GeminiClient
from .openai_client import OpenAICompatibleClient
from .fallback_llm_client import FallbackLLMClient
from .llm_provider import LLMClient
from .llm_config_models import validate_llm_config, config_to_dict, GeminiConfig
from ..utils.gemini_config import is_retired_model


# Keys stored in the app_settings table
SETTING_KEY_PROVIDER = "llm_provider"          # "gemini" | "openai_compatible"
SETTING_KEY_API_KEY = "llm_api_key"            # encrypted at rest in future
SETTING_KEY_BASE_URL = "llm_base_url"          # e.g. "https://api.openai.com/v1"
SETTING_KEY_MODEL_MAIN = "llm_model_main"      # e.g. "gpt-6-luna"
SETTING_KEY_MODEL_LITE = "llm_model_lite"      # e.g. "gpt-6-luna" (or None)
SETTING_KEY_MODEL_RELEVANCE = "llm_model_relevance"  # e.g. "gpt-6-luna" (defaults to model_lite or model_main)
SETTING_KEY_ORG = "llm_organization"           # OpenAI org ID (optional)

_LLM_DB_KEY_MAP: Dict[str, str] = {
    SETTING_KEY_PROVIDER: "provider",
    SETTING_KEY_API_KEY: "api_key",
    SETTING_KEY_BASE_URL: "base_url",
    SETTING_KEY_MODEL_MAIN: "model_main",
    SETTING_KEY_MODEL_LITE: "model_lite",
    SETTING_KEY_MODEL_RELEVANCE: "model_relevance",
    SETTING_KEY_ORG: "organization",
}


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
                if key in _LLM_DB_KEY_MAP:
                    result[_LLM_DB_KEY_MAP[key]] = value
        finally:
            conn.close()
    except Exception as e:
        logger.debug(f"Could not read LLM settings from DB: {e}")

    return result


def _substitute_retired_gemini_models(
    resolved: Dict[str, Optional[str]], env_settings
) -> Dict[str, Optional[str]]:
    """Replace retired gemini-1.x/2.x IDs from older stored profiles with env
    defaults. Done once at the single read point so every consumer (chat
    client, llm_api converter, test endpoint) sees a runnable model instead
    of failing differently per path."""
    if resolved.get("provider") != "gemini":
        return resolved
    retired = [
        f for f in ("model_main", "model_lite", "model_relevance")
        if is_retired_model(resolved.get(f))
    ]
    if not retired:
        return resolved
    defaults = {
        "model_main": getattr(env_settings, "GEMINI_MODEL_MAIN", "gemini-3.8-flash"),
        "model_lite": getattr(env_settings, "GEMINI_MODEL_LITE", "gemini-3.5-flash-lite"),
        "model_relevance": getattr(env_settings, "GEMINI_MODEL_LITE", "gemini-3.5-flash-lite"),
    }
    logger.warning(
        "Stored Gemini model IDs are retired ({}); substituting env defaults",
        ", ".join(f"{f}={resolved.get(f)}" for f in retired),
    )
    return {**resolved, **{f: defaults[f] for f in retired}}


def get_llm_settings() -> Dict[str, Optional[str]]:
    """Get current LLM settings (from DB with .env fallback).

    DB reads are validated through the discriminated union so a corrupt record
    (e.g. ``provider="gemini"`` + ``base_url="..."`` from a previous bug) is
    caught and falls back to .env defaults instead of returning a mixed config.

    Returns:
        Dict with provider, api_key, base_url, model_main, model_lite,
        model_relevance, organization. Always has all 7 keys (filled with
        None for provider-specific fields that don't apply).
    """
    db_settings = _read_settings_from_db()
    env_settings = get_settings()

    # If DB has a provider configured, validate it through the union before
    # returning. A corrupt DB record (e.g. from a previous bug) falls back to
    # .env defaults instead of returning a mixed-provider config.
    if db_settings["provider"]:
        try:
            config = validate_llm_config(db_settings)
            if config is not None:
                return _substitute_retired_gemini_models(
                    config_to_dict(config), env_settings
                )
        except ValidationError:
            logger.warning(
                "Corrupt LLM settings in DB (failed union validation); "
                "falling back to .env defaults."
            )
        # Fall through to .env fallback

    # Fall back to .env: if GEMINI_API_KEY is set, use Gemini
    if env_settings.GEMINI_API_KEY:
        return config_to_dict(GeminiConfig(
            provider="gemini",
            api_key=env_settings.GEMINI_API_KEY,
        ))

    # Fall back to .env: if OPENAI_API_KEY is set, use OpenAI-compatible
    if env_settings.OPENAI_API_KEY:
        base_url = getattr(env_settings, "OPENAI_BASE_URL", None) or "https://api.openai.com/v1"
        model_main, model_lite = resolve_default_models("openai_compatible", base_url, env_settings)
        return {
            "provider": "openai_compatible",
            "api_key": env_settings.OPENAI_API_KEY,
            "base_url": base_url,
            "model_main": model_main,
            "model_lite": model_lite,
            "model_relevance": None,  # Defaults to model_lite (which falls back to model_main)
            "organization": None,
        }

    # No provider configured
    return config_to_dict(None)


def is_llm_configured() -> bool:
    """Check if an LLM provider is configured (either in DB or .env)."""
    settings = get_llm_settings()
    return settings["provider"] is not None and settings["api_key"] is not None


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
        # ponytail: model_main/model_lite fall back to env defaults inside
        # GeminiClient, so a None DB value still uses the right model.
        return GeminiClient(
            api_key=api_key,
            model_main=settings.get("model_main"),
            model_lite=settings.get("model_lite"),
            model_relevance=settings.get("model_relevance"),
        )

    if provider == "openai_compatible":
        # Fall back to .env if the persisted key was deleted (api_key="").
        # Mirrors GeminiClient's internal fallback to GEMINI_API_KEY.
        settings_base_url = settings.get("base_url")
        env_base_url = get_settings().OPENAI_BASE_URL
        base_url = settings_base_url or env_base_url or "https://api.openai.com/v1"
        if not api_key and (not settings_base_url or settings_base_url == env_base_url):
            # The .env credential only pairs with the env-resolved endpoint --
            # never forward it to a stored/caller-written base_url.
            api_key = get_settings().OPENAI_API_KEY
        if not api_key:
            raise ValueError("OpenAI-compatible provider requires an API key")
        model_main = settings.get("model_main")
        model_lite = settings.get("model_lite")
        model_relevance = settings.get("model_relevance")
        organization = settings.get("organization")

        return OpenAICompatibleClient(
            api_key=api_key,
            base_url=base_url,
            model_main=model_main,
            model_lite=model_lite,
            model_relevance=model_relevance,
            organization=organization,
        )

    raise ValueError(f"Unknown LLM provider: {provider}")


def _is_private_base_url(base_url: Optional[str]) -> bool:
    """True when base_url points at loopback or a private address."""
    if not base_url:
        return False
    try:
        host = urlparse(base_url).hostname or ""
    except ValueError:
        return False
    host = host.lower()
    if host in ("localhost", "localhost.localdomain") or host.endswith(".localhost"):
        return True
    try:
        addr = ip_address(host)
    except ValueError:
        return False  # a hostname we can't parse as an IP: treat as public
    return addr.is_loopback or addr.is_private or addr.is_link_local


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
        model_main, model_lite = resolve_default_models("openai_compatible", base_url, env_settings)
        return OpenAICompatibleClient(
            api_key=env_settings.OPENAI_API_KEY,
            base_url=base_url,
            model_main=model_main,
            model_lite=model_lite,
            model_relevance=getattr(env_settings, "OPENAI_MODEL_RELEVANCE", None),
            organization=getattr(env_settings, "OPENAI_ORGANIZATION", None),
        )

    if primary == "openai_compatible" and env_settings.GEMINI_API_KEY:
        # A private/loopback primary (local vLLM, Ollama) means the operator
        # deliberately chose private inference. Silently failing over to a
        # cloud provider would leak private corpus to a third party.
        if _is_private_base_url(settings.get("base_url")):
            logger.info("LLM fallback suppressed: primary base_url is private")
            return None
        return GeminiClient(
            api_key=env_settings.GEMINI_API_KEY,
            model_main=getattr(env_settings, "GEMINI_MODEL_MAIN", None),
            model_lite=getattr(env_settings, "GEMINI_MODEL_LITE", None),
        )

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
