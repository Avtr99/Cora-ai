"""Snippet sanitization utilities for citations.

Threat Model:
- Primary concern: Preventing XSS via malicious HTML/JS in citation snippets.
- Secondary concern: Redacting sensitive data (secrets, emails, paths).
- The sanitize() method strips ALL HTML tags (no allowed tags/attributes)
  to produce plain text suitable for display in UI contexts where rich
  formatting is not needed. For contexts requiring HTML, use a different
  sanitization strategy.
"""

from __future__ import annotations

import nh3

from ..utils.pii_patterns import EMAIL_RE as _EMAIL_RE, SECRET_RE as _SECRET_RE

from .config import (
    _ENV_PATH_RE,
    _UNIX_PATH_RE,
    _WINDOWS_PATH_RE,
)


class SnippetSanitizer:
    """Sanitize snippets to avoid leaking sensitive data and markup."""

    def sanitize(self, snippet: str) -> str:
        """Sanitize snippet to avoid leaking sensitive data and markup.

        Process:
        1. Strip ALL HTML tags using nh3 (handles malformed/nested tags safely)
        2. Redact secrets, emails, and file paths using regex patterns
        3. Return cleaned plain text

        Args:
            snippet: Raw snippet text that may contain HTML and sensitive data.

        Returns:
            Sanitized plain text string safe for UI display.
        """
        if not snippet:
            return ""

        # Strip all HTML tags safely (handles malformed/nested/encoded tags)
        sanitized = nh3.clean(snippet, tags=set(), attributes={})

        # Redact sensitive patterns
        sanitized = _SECRET_RE.sub("[REDACTED]", sanitized)
        sanitized = _EMAIL_RE.sub("[EMAIL]", sanitized)
        sanitized = _WINDOWS_PATH_RE.sub("[PATH]", sanitized)
        sanitized = _UNIX_PATH_RE.sub("[PATH]", sanitized)
        sanitized = _ENV_PATH_RE.sub("[ENV]", sanitized)
        return sanitized.strip()
