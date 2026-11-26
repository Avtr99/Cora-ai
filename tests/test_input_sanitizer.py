"""Tests for the OutputSanitizer env-var redaction pattern.

The bare ``$VAR`` branch must redact secret-shaped env vars without mangling
LaTeX-style math like ``$M_{pu}$`` (a trailing ``*`` once matched ``$M_`` as
an env var).
"""

from src.api.middleware.input_sanitizer import OutputSanitizer


def _sanitize(text: str) -> str:
    sanitizer = OutputSanitizer()
    cleaned, _ = sanitizer.sanitize(text)
    return cleaned


def test_latex_math_fragments_are_not_redacted():
    text = "The grid emission factor $M_{pu}$ and margin $EF_{OM}$ appear in the equation."
    assert _sanitize(text) == text


def test_env_var_shaped_math_still_redacts():
    # "$M_OM" is indistinguishable from an env var — the regex cannot tell it
    # from "$SECRET_KEY". The fix only protects fragments followed by a
    # non-word char (like "{"), which is the common LaTeX subscript shape.
    text = "The operating margin is $M_OM per the methodology."
    cleaned = _sanitize(text)
    assert "[REDACTED]" in cleaned


def test_trailing_underscore_math_is_not_redacted():
    # "$M_" followed by a brace/space is math, not an env var name.
    text = "where $M_ {pu}$ denotes the build margin"
    assert _sanitize(text) == text


def test_env_var_shape_is_still_redacted():
    text = "The key was stored in $SECRET_KEY on the host."
    cleaned = _sanitize(text)
    assert "$SECRET_KEY" not in cleaned
    assert "[REDACTED]" in cleaned


def test_braced_env_var_is_still_redacted():
    text = "Reads ${DATABASE_URL} at startup."
    cleaned = _sanitize(text)
    assert "DATABASE_URL" not in cleaned
    assert "[REDACTED]" in cleaned


def test_plain_dollar_amounts_are_not_redacted():
    text = "Credits traded near $4 and $12 per tonne."
    assert _sanitize(text) == text
