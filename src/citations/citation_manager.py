"""
Citation Manager

Manages citations for RAG responses to increase trust and transparency.
Tracks source documents, page numbers, relevance scores, and metadata.
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from ..query_processing.conversational_classifier import is_conversational_query
from ..query_processing.fallback_answers import has_error_source_marker
from .check import drop_markers, marker_type, select_cited
from .config import (
    CitationConfig,
    _ALL_KB_EXTENSIONS,
    _TRIVIAL_ANSWER_PATTERNS,
)
from .extractor import CitationExtractor
from .formatter import CitationFormatter
from .models import Citation
from .sanitizer import SnippetSanitizer
from .source_name import clean_source_name
from .source_type import SourceTypeResolver


class CitationManager:
    """
    Manages citations for RAG responses.

    Citations carry the prompt's own numbering (``index`` + ``marker_type``);
    ``finalize`` selects the cited subset and never renumbers.
    """

    def __init__(self, config: Optional[CitationConfig] = None):
        self.config = config or CitationConfig()
        self._kb_extensions = _ALL_KB_EXTENSIONS

        self._source_type_resolver = SourceTypeResolver(self.config)
        self._snippet_sanitizer = SnippetSanitizer()
        self._extractor = CitationExtractor(
            config=self.config,
            source_type_resolver=self._source_type_resolver,
        )
        self._formatter = CitationFormatter(self._snippet_sanitizer)

    def extract_citations_from_web_results(
        self,
        web_results: Dict[str, Any],
    ) -> List[Citation]:
        return self._extractor.extract_from_web_results(web_results=web_results)

    def finalize(
        self,
        result: Dict[str, Any],
        query: str,
        coverage_score: float = 1.0,
    ) -> None:
        """Select the displayed citations from the answer's own markers.

        ``result["citations"]`` must hold every citable Citation (KB context
        chunks plus web results, each carrying ``index`` and ``marker_type``).
        Marker numbers map one-to-one onto those indices — nothing is
        renumbered, sorted, or capped here.
        """
        available = result.get("citations") or []
        answer = result.get("answer") or ""

        cited = select_cited(available, answer)
        if self.should_suppress_citations(query, answer, cited, coverage_score):
            cited = []
            answer = drop_markers(answer, lambda _type, _n: False)
        else:
            keep = {
                (marker_type(citation), citation.index)
                for citation in cited
                if citation.index is not None
            }
            answer = drop_markers(answer, lambda t, n: (t, n) in keep)

        result["answer"] = answer
        result["citations"] = cited
        result["_citations_finalized"] = True

        if cited:
            sources = []
            for citation in cited:
                source_name = getattr(citation, "source_name", None)
                if source_name is None:
                    continue
                if citation.source_type == "web":
                    sources.append(source_name)
                else:
                    cleaned_name = clean_source_name(source_name)
                    if cleaned_name and cleaned_name.strip():
                        sources.append(cleaned_name)
            result["sources"] = sources
        elif not has_error_source_marker(result.get("sources")):
            result["sources"] = []

    def _sanitize_snippet(self, snippet: str) -> str:
        return self._snippet_sanitizer.sanitize(snippet)

    @staticmethod
    def clean_source_name(name: str) -> str:
        return clean_source_name(name)

    @staticmethod
    def is_conversational_query(query: str) -> bool:
        return is_conversational_query(query)

    def should_suppress_citations(
        self,
        query: str,
        answer: str,
        citations: List[Citation],
        coverage_score: float = 0.0,
    ) -> bool:
        reason: Optional[str] = None
        if self.is_conversational_query(query):
            reason = "conversational_query"
        elif coverage_score < self.config.coverage_suppression_threshold and not citations:
            reason = "low_coverage_no_matches"
        elif answer and len(answer.strip()) < self.config.short_answer_char_limit:
            answer_stripped = answer.strip().lower()
            for pattern in _TRIVIAL_ANSWER_PATTERNS:
                if pattern.search(answer_stripped):
                    reason = "trivial_short_answer"
                    break

        if reason:
            logger.info(
                "citations_suppressed",
                reason=reason,
                query_length=len(query or ""),
                coverage_score=coverage_score,
                citation_count=len(citations or []),
            )
            return True
        return False

    def format_citations_for_response(
        self,
        citations: List[Citation],
        include_snippets: bool = False,
    ) -> Dict[str, Any]:
        return self._formatter.format_for_response(citations, include_snippets=include_snippets)

    def generate_citation_text(self, citations: List[Citation]) -> str:
        return self._formatter.generate_citation_text(citations)
