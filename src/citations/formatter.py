"""Citation formatting for API and text responses."""

from __future__ import annotations

from typing import Any, Dict, List

from .models import Citation
from .sanitizer import SnippetSanitizer
from .source_name import clean_source_name


class CitationFormatter:
    """Converts citation objects into API/text response payloads."""

    def __init__(self, sanitizer: SnippetSanitizer) -> None:
        self.sanitizer = sanitizer

    def format_for_response(
        self,
        citations: List[Citation],
        include_snippets: bool = False,
    ) -> Dict[str, Any]:
        cleaned_names: List[str] = []
        for citation in citations:
            if citation.source_type == "web":
                cleaned_names.append(citation.source_name)
            else:
                cleaned_names.append(clean_source_name(citation.source_name))

        formatted: Dict[str, Any] = {
            "count": len(citations),
            "sources": cleaned_names,
            "details": [],
        }

        for citation, cleaned_name in zip(citations, cleaned_names):
            detail: Dict[str, Any] = {
                "source_name": cleaned_name,
                "source_type": citation.source_type,
                "relevance_score": citation.relevance_score,
            }
            if citation.page_number is not None:
                detail["page_number"] = citation.page_number
            if citation.section is not None:
                detail["section"] = citation.section
            if citation.url:
                detail["url"] = citation.url
            if include_snippets and citation.content_snippet:
                detail["snippet"] = self.sanitizer.sanitize(citation.content_snippet)
            # Surface curated VCM metadata from the source document.
            # Trim redundant fields: methodology_codes and registry_document_id
            # are always duplicates of document_id; title is ~source_name (already
            # shown). Drop publisher when it equals registry (avoids "Verra ·
            # Verra"). Only emit non-None values so non-methodology docs (market
            # reports, policy docs) don't get noise from fields they don't have.
            # Web citations carry no VCM metadata and stay unchanged.
            curated = self._curate_metadata(citation.metadata)
            if curated:
                detail["metadata"] = curated
            formatted["details"].append(detail)

        return formatted

    @staticmethod
    def _curate_metadata(metadata: Any) -> Dict[str, Any]:
        """Filter citation.metadata to non-redundant VCM fields for the API payload.

        Drops:
            - methodology_codes, registry_document_id (always == document_id)
            - title (≈ source_name, already displayed)
            - publisher when it equals registry or category (avoids "Verra · Verra")
            - None/empty values (so docs without a field don't emit noise)

        Keeps:
            - registry: only real credit-issuing registries (Verra, Gold Standard, ...)
            - category: non-registry classifications (Market Intelligence, VCM Policy,
              ICVCM, SBTi, ...) — mutually exclusive with registry at the source
            - document_id, version_number: when present
            - publisher: when it differs from both registry and category
        """
        if not metadata or not isinstance(metadata, dict):
            return {}
        curated: Dict[str, Any] = {}
        registry = metadata.get("registry")
        category = metadata.get("category")
        publisher = metadata.get("publisher")
        for key in ("registry", "category", "document_id", "version_number"):
            value = metadata.get(key)
            if value is not None and value != "":
                curated[key] = value
        # Only surface publisher when it adds info beyond registry and category
        if publisher and publisher != registry and publisher != category:
            curated["publisher"] = publisher
        return curated

    @staticmethod
    def generate_citation_text(citations: List[Citation]) -> str:
        if not citations:
            return ""

        citation_lines = ["\n\n**Sources:**"]
        for index, citation in enumerate(citations, 1):
            citation_lines.append(f"{index}. {citation.to_display_format()}")
        return "\n".join(citation_lines)
