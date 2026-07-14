"""Source type resolution for citations."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from urllib.parse import unquote, urlparse

from .config import CitationConfig


class SourceTypeResolver:
    """Determines source type using explicit priority rules."""

    def __init__(self, config: CitationConfig):
        self.config = config

    def resolve(self, source: dict, title: str, url: str) -> str:
        explicit_type = str(source.get("type", "")).strip().lower()
        # Treat the provider-specific "web_search" label the same as "web".
        # An explicit type from the source provider wins over URL-extension heuristics.
        if explicit_type in {"knowledge_base", "web", "web_search"}:
            # Map provider-specific "web_search" to canonical "web".
            return "web" if explicit_type == "web_search" else explicit_type

        for candidate in (
            title,
            url,
            str(source.get("file_name", "")),
            str(source.get("parent_doc", "")),
            str(source.get("source", "")),
        ):
            if self._extract_extension(candidate) in self.config.kb_extensions:
                return "knowledge_base"

        if any(key in source for key in ("file_name", "parent_doc", "page_number", "document_id")):
            return "knowledge_base"

        if url and not url.lower().startswith(("http://", "https://")):
            return "knowledge_base"

        return "web"

    def _extract_extension(self, value: str) -> str:
        if not value:
            return ""

        decoded = value
        for _ in range(2):
            next_decoded = unquote(decoded)
            if next_decoded == decoded:
                break
            decoded = next_decoded

        parsed = urlparse(decoded)
        candidate = parsed.path if parsed.scheme and parsed.netloc else decoded

        for path_cls in (PureWindowsPath, PurePosixPath):
            try:
                ext = path_cls(candidate).suffix.lower()
                if ext:
                    return ext
            except Exception:
                continue

        return ""
