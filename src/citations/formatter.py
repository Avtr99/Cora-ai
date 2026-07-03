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
            formatted["details"].append(detail)

        return formatted

    @staticmethod
    def generate_citation_text(citations: List[Citation]) -> str:
        if not citations:
            return ""

        citation_lines = ["\n\n**Sources:**"]
        for index, citation in enumerate(citations, 1):
            citation_lines.append(f"{index}. {citation.to_display_format()}")
        return "\n".join(citation_lines)
