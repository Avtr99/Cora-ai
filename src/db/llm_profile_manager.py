"""LLM provider profile persistence and resolution.

Profiles are keyed by a slug label and stored in the app_settings key-value
table. This module is used by the LLM settings routes and factory to read,
write, discover, and resolve available provider configurations.
"""

import json
from typing import Optional, List, Tuple
from urllib.parse import urlparse

from loguru import logger

from .app_settings import save_app_setting
from .database import get_connection


def _profile_key(label: str) -> str:
    return f"llm_profile_{label}"


def _read_profile(label: str) -> Optional[dict]:
    """Read a saved provider profile by label, or None."""
    try:
        conn = get_connection()
        try:
            row = conn.cursor().execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (_profile_key(label),),
            ).fetchone()
            return json.loads(row["value"]) if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _read_all_profiles() -> dict:
    """Read all saved profiles. Returns {label: profile_dict}."""
    profiles = {}
    try:
        conn = get_connection()
        try:
            for row in conn.cursor().execute(
                "SELECT key, value FROM app_settings WHERE key LIKE 'llm_profile_%'"
            ).fetchall():
                label = row["key"].replace("llm_profile_", "", 1)
                try:
                    profiles[label] = json.loads(row["value"])
                except Exception as e:
                    logger.warning(f"Skipping malformed LLM profile row '{label}': {e}")
                    continue
        finally:
            conn.close()
    except Exception:
        pass
    return profiles


def _save_profile(label: str, provider: str, api_key: Optional[str],
                  base_url: Optional[str], model_main: Optional[str],
                  model_lite: Optional[str], model_relevance: Optional[str] = None,
                  organization: Optional[str] = None) -> None:
    """Save a provider profile by label.

    Validates cross-field consistency through the discriminated union so a
    mixed-provider config (e.g. ``provider="gemini"`` + ``base_url="..."``)
    can never be persisted as a profile — even if the caller passes stale
    fields. The union structurally drops impossible fields (``extra="ignore"``)
    and clears wrong-provider API keys (field validator).
    """
    from ..query_processing.llm_config_models import validate_llm_config
    from pydantic import ValidationError

    raw = {
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model_main": model_main,
        "model_lite": model_lite,
        "model_relevance": model_relevance,
        "organization": organization,
    }
    try:
        config = validate_llm_config(raw)
    except ValidationError:
        # If the raw config is invalid (e.g. unknown provider), store as-is.
        # The union handles sanitization (drops wrong fields) when provider is valid.
        config = None

    if config is not None:
        save_app_setting(_profile_key(label), json.dumps(config.model_dump()))
    else:
        save_app_setting(_profile_key(label), json.dumps(raw))


def _label_for_openai(base_url: str) -> str:
    """Derive a human-friendly label from the base URL.

    Parses the URL hostname rather than substring matching, so a proxy at
    ``openai.com.evil.com`` is labeled "Custom", not "OpenAI".
    """
    try:
        parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
        host = (parsed.hostname or "").lower()
    except Exception:
        return "Custom"
    if host == "openrouter.ai":
        return "OpenRouter"
    if host == "api.openai.com":
        return "OpenAI"
    if host in ("localhost", "127.0.0.1"):
        return "Ollama"
    return "Custom"


def _slug(label: str) -> str:
    """Normalize a label to a slug for profile keys."""
    return label.lower().replace(" ", "_").replace("(", "").replace(")", "")


def get_profile_label(provider: str, base_url: Optional[str]) -> str:
    """Return a human-friendly label for a provider profile."""
    if provider == "gemini":
        return "Gemini"
    return _label_for_openai(base_url or "")


def get_profile_slug(label: str) -> str:
    """Normalize a profile label to a slug."""
    return _slug(label)


def resolve_default_models(provider: str, base_url: Optional[str], env_settings) -> Tuple[Optional[str], Optional[str]]:
    """Resolve (model_main, model_lite) defaults from env settings for a provider.

    For OpenAI-compatible providers, the base URL host is inspected to
    distinguish OpenAI, OpenRouter, and other endpoints.
    """
    if provider == "gemini":
        return (
            getattr(env_settings, "GEMINI_MODEL_MAIN", None),
            getattr(env_settings, "GEMINI_MODEL_LITE", None),
        )

    if provider == "openai_compatible":
        base_url = base_url or ""
        try:
            host = urlparse(base_url if "://" in base_url else f"http://{base_url}").hostname
            host = (host or "").lower()
        except Exception:
            host = ""

        if host == "openrouter.ai":
            main = getattr(env_settings, "OPENROUTER_MODEL", None) or "google/gemini-2.5-flash"
            lite = getattr(env_settings, "OPENROUTER_MODEL_LITE", None) or main
        else:
            main = getattr(env_settings, "OPENAI_MODEL", None) or "gpt-4.1-mini"
            lite = getattr(env_settings, "OPENAI_MODEL_LITE", None) or main
        return main, lite

    return None, None


def detect_env_providers(env_settings) -> List[dict]:
    """Detect providers from .env keys. Returns list of profile dicts.

    Model names fall back to tested recommendations when the user has not set
    the optional ``OPENAI_MODEL`` / ``OPENROUTER_MODEL`` env vars. Users can
    override the recommendation by setting those vars or by editing the model
    in the Settings UI (which writes to the DB profile, taking precedence).
    """
    found = []
    if env_settings.GEMINI_API_KEY:
        main, lite = resolve_default_models("gemini", None, env_settings)
        found.append({
            "label": "Gemini", "slug": "gemini", "provider": "gemini",
            "api_key": env_settings.GEMINI_API_KEY, "base_url": None,
            "model_main": main, "model_lite": lite,
        })
    if getattr(env_settings, "OPENROUTER_API_KEY", None):
        base_url = "https://openrouter.ai/api/v1"
        main, lite = resolve_default_models("openai_compatible", base_url, env_settings)
        found.append({
            "label": "OpenRouter", "slug": "openrouter", "provider": "openai_compatible",
            "api_key": env_settings.OPENROUTER_API_KEY,
            "base_url": base_url,
            "model_main": main, "model_lite": lite,
        })
    if env_settings.OPENAI_API_KEY:
        base_url = "https://api.openai.com/v1"
        main, lite = resolve_default_models("openai_compatible", base_url, env_settings)
        found.append({
            "label": "OpenAI", "slug": "openai", "provider": "openai_compatible",
            "api_key": env_settings.OPENAI_API_KEY,
            "base_url": base_url,
            "model_main": main, "model_lite": lite,
        })
    return found


# Backward-compatible alias for code that still imports the private name.
_detect_env_providers = detect_env_providers


def build_available_providers(current_settings: dict, env_settings) -> Tuple[Optional[str], List[dict]]:
    """Build the full provider list and current slug for GET /v1/settings/llm/providers.

    Returns ``(current_slug, available)`` where ``available`` is a list of dicts
    with keys ``slug``, ``label``, ``provider``, ``model``, ``has_api_key``.
    """
    saved_profiles = _read_all_profiles()
    env_providers = {p["slug"]: p for p in detect_env_providers(env_settings)}

    # Merge: DB profiles take precedence, but backfill missing api_key from env.
    all_profiles = {}
    for slug, p in env_providers.items():
        all_profiles[slug] = p
    for slug, p in saved_profiles.items():
        if not p.get("api_key") and slug in env_providers:
            p = {**p, "api_key": env_providers[slug].get("api_key")}
        all_profiles[slug] = {**p, "slug": slug}

    # Determine current active profile slug by matching DB settings
    cur_slug = None
    if current_settings["provider"] == "gemini":
        cur_slug = "gemini"
    elif current_settings["base_url"]:
        cur_slug = _slug(_label_for_openai(current_settings["base_url"]))

    available = []
    for slug, p in all_profiles.items():
        provider = p.get("provider", "openai_compatible")
        label = p.get("label") or get_profile_label(provider, p.get("base_url"))

        model = p.get("model_main")
        if not model:
            model = resolve_default_models(provider, p.get("base_url"), env_settings)[0]
        if not model:
            model = "unknown"

        available.append({
            "slug": slug,
            "label": label,
            "provider": provider,
            "model": model,
            "has_api_key": bool(p.get("api_key")),
        })

    # Sort: current first, then alphabetical
    available.sort(key=lambda a: (a["slug"] != cur_slug, a["slug"]))

    return cur_slug, available


def resolve_profile_for_switch(label: str, env_settings) -> Optional[dict]:
    """Find a provider profile by slug for quick-switching.

    Searches saved DB profiles first, then env-detected providers. If the
    profile is missing an API key — which happens when the union's field
    validator cleared a wrong-provider key on a previous save — it is
    backfilled from the env-detected key so the switch uses the correct key.

    Returns ``None`` when no matching profile exists.
    """
    env_providers = detect_env_providers(env_settings)

    profile = _read_profile(label)
    if not profile:
        for p in env_providers:
            if p["slug"] == label:
                profile = p
                break

    if not profile:
        return None

    # If the DB profile lost its api_key (cleared by the union's field
    # validator on a previous save due to cross-provider contamination),
    # backfill from the env-detected key so the switch uses the correct key.
    if not profile.get("api_key"):
        for p in env_providers:
            if p["slug"] == label and p.get("api_key"):
                profile["api_key"] = p["api_key"]
                break

    return profile
