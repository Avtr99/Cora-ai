"""LLM provider profile persistence.

Profiles are keyed by a slug label and stored in the app_settings key-value
table. This module is used by the LLM settings routes and factory to read,
write, and discover available provider configurations.
"""

import json
from typing import Optional, List
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
    """Save a provider profile by label."""
    save_app_setting(_profile_key(label), json.dumps({
        "provider": provider,
        "api_key": api_key,
        "base_url": base_url,
        "model_main": model_main,
        "model_lite": model_lite,
        "model_relevance": model_relevance,
        "organization": organization,
    }))


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


def _detect_env_providers(env_settings) -> List[dict]:
    """Detect providers from .env keys. Returns list of profile dicts."""
    found = []
    if env_settings.GEMINI_API_KEY:
        found.append({
            "label": "Gemini", "slug": "gemini", "provider": "gemini",
            "api_key": env_settings.GEMINI_API_KEY, "base_url": None,
            "model_main": env_settings.GEMINI_MODEL_MAIN,
            "model_lite": env_settings.GEMINI_MODEL_LITE,
        })
    if getattr(env_settings, "OPENROUTER_API_KEY", None):
        found.append({
            "label": "OpenRouter", "slug": "openrouter", "provider": "openai_compatible",
            "api_key": env_settings.OPENROUTER_API_KEY,
            "base_url": "https://openrouter.ai/api/v1",
            "model_main": "google/gemini-2.5-flash",
            "model_lite": "google/gemini-2.5-flash",
        })
    if env_settings.OPENAI_API_KEY:
        found.append({
            "label": "OpenAI", "slug": "openai", "provider": "openai_compatible",
            "api_key": env_settings.OPENAI_API_KEY,
            "base_url": "https://api.openai.com/v1",
            "model_main": "gpt-4.1-mini",
            "model_lite": "gpt-4.1-mini",
        })
    return found
