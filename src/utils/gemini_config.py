"""Generation-config helpers for Gemini 3.x+ models.

The gemini-1.x/2.x generations are retired (2.x on 2026-10-20). Current
models reject the legacy sampling parameters
(``temperature``/``top_p``/``top_k``); reasoning effort is controlled through
``ThinkingConfig.thinking_level`` (LOW/MEDIUM/HIGH — MINIMAL is only
supported on the Flash-Lite models, not on 3.8 Flash).
"""

from typing import Optional

from google.genai import types

# Generations retired on the Gemini API (2.x on 2026-10-20). Rejecting the
# retired prefixes — rather than requiring a gemini-3 prefix — keeps the gate
# forward-compatible with future model releases.
_RETIRED_MODEL_PREFIXES = ("gemini-1", "gemini-2")


def _bare_model(model_name: Optional[str]) -> str:
    """Strip a resource path prefix (``models/``) to the bare model ID."""
    return (model_name or "").rsplit("/", 1)[-1]


def is_retired_model(model_name: Optional[str]) -> bool:
    """Return True when the model ID belongs to a retired Gemini generation."""
    return _bare_model(model_name).startswith(_RETIRED_MODEL_PREFIXES)


def build_generate_content_config(
    model_name: str,
    thinking_level: Optional[str] = None,
    **kwargs,
) -> types.GenerateContentConfig:
    """Build a ``GenerateContentConfig`` for a gemini-3.x model.

    Injects ``ThinkingConfig(thinking_level=...)`` when a level is given and
    forwards the remaining fields (``max_output_tokens``,
    ``response_mime_type``, ``tools``, ...) unchanged. Legacy sampling
    parameters (``temperature``/``top_p``/``top_k``) are not accepted by
    gemini-3.x and must not be passed.

    Args:
        model_name: Model ID the config will be sent to.
        thinking_level: Thinking level to send. ``None`` sends no
            ``ThinkingConfig``, so the model's own default applies (always a
            level that model supports). Ignored when the caller passes an
            explicit ``thinking_config`` — that wins.
        **kwargs: Fields forwarded to ``types.GenerateContentConfig``.

    Raises:
        ValueError: If ``model_name`` belongs to a retired generation
            (gemini-1.x/2.x) — fail fast at request build rather than at the
            API with a generic 400.
    """
    if is_retired_model(model_name):
        raise ValueError(
            f"Unsupported model '{model_name}': the gemini-1.x/2.x generations "
            "were retired on 2026-10-20. Configure a gemini-3.x model "
            "(e.g. gemini-3.8-flash or gemini-3.5-flash-lite)."
        )

    if thinking_level is not None and "thinking_config" not in kwargs:
        kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_level=thinking_level
        )
    return types.GenerateContentConfig(**kwargs)
