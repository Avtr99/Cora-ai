"""Validation helpers for the settings schema.

These utilities are pure functions that do not depend on the ``Settings``
class, so they live here to keep ``config.py`` focused on the schema itself.
"""

import re

_FILTER_FIELD_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
_FILTER_FIELD_MAX_LENGTH = 64


def normalize_filter_field_name(field: str) -> str:
    """Normalize and validate a filter field name for Qdrant compatibility.

    Replaces spaces, slashes, and hyphens with underscores, then validates
    that the result contains only ``[A-Za-z0-9_]`` and is within the length
    limit enforced by Qdrant payload indexes.

    Args:
        field: Raw field name that may include spaces or disallowed chars.

    Returns:
        Normalized field name using underscores.

    Raises:
        ValueError: If ``field`` is None, empty, too long, or contains
            characters outside ``[A-Za-z0-9_]`` after normalization.
    """
    if field is None:
        raise ValueError("Filter field name cannot be None")

    trimmed = field.strip()
    if not trimmed:
        raise ValueError("Filter field name cannot be empty")

    normalized = (
        trimmed.replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
    )

    if len(normalized) > _FILTER_FIELD_MAX_LENGTH:
        raise ValueError(
            f"Filter field '{field}' exceeds maximum length of {_FILTER_FIELD_MAX_LENGTH} characters"
        )

    if not _FILTER_FIELD_PATTERN.fullmatch(normalized):
        raise ValueError(
            f"Filter field '{field}' contains disallowed characters "
            "(only letters, numbers, and underscores are permitted)"
        )

    return normalized


__all__ = ["normalize_filter_field_name"]
