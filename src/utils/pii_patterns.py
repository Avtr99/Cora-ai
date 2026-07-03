"""Shared PII detection patterns.

These compiled regexes are used by both citation sanitization and memory
redaction. Centralising them avoids duplication and keeps the two subsystems
consistent.
"""

import re

# Email: safe regex with mutually exclusive domain tokens to avoid
# catastrophic backtracking.
EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}\b"
)

# IPv4 address
IP_ADDRESS_RE = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

# UUID (may contain user identifiers)
UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# API keys / secrets / bearer tokens
SECRET_RE = re.compile(
    r"\b(?:sk|pk|api|key|token|secret|bearer)[_-]?[A-Za-z0-9_-]{20,}\b",
    re.IGNORECASE,
)
