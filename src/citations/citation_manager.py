"""
Citation Manager

Manages citations for RAG responses to increase trust and transparency.
Tracks source documents, page numbers, relevance scores, and metadata.
"""

from typing import Any, Dict, List, Optional

from loguru import logger

from ..query_processing.conversational_classifier import is_conversational_query
from .config import (
    CitationConfig,
    _ALL_KB_EXTENSIONS,
    _STOP_WORDS,
    _TRIVIAL_ANSWER_PATTERNS,
)
from .extractor import CitationExtractor
from .filter import CitationFilter
from .formatter import CitationFormatter
from .models import Citation
from .sanitizer import SnippetSanitizer
from .source_name import clean_source_name
from .source_type import SourceTypeResolver


class CitationManager:
    """
    Manages citations for RAG responses.
    
    Extracts, deduplicates, and formats citations from retrieval results.
    """
    
    def __init__(
        self,
        min_relevance_score: float = 0.3,
        config: Optional[CitationConfig] = None,
    ):
        self.config = config or CitationConfig(min_relevance_score=min_relevance_score)
        self.min_relevance_score = self.config.min_relevance_score
        self.safe_metadata_fields = {
            "file_name", "parent_doc", "source", "page_number",
            "section", "registry", "category", "document_id", "version_number", "title",
            "publisher", "registry_document_id", "methodology_codes",
        }

        self._kb_extensions = _ALL_KB_EXTENSIONS
        self._stop_words = _STOP_WORDS

        self._source_type_resolver = SourceTypeResolver(self.config)
        self._snippet_sanitizer = SnippetSanitizer()
        self._extractor = CitationExtractor(
            config=self.config,
            safe_metadata_fields=self.safe_metadata_fields,
            source_type_resolver=self._source_type_resolver,
        )
        self._filter = CitationFilter(self.config)
        self._formatter = CitationFormatter(self._snippet_sanitizer)

    def _extract_extension(self, value: str) -> str:
        return self._source_type_resolver._extract_extension(value)

    def _determine_source_type(self, source: Dict[str, Any], title: str, url: str) -> str:
        return self._source_type_resolver.resolve(source, title, url)

    def extract_citations_from_vector_results(
        self,
        vector_results: Dict[str, Any],
        max_citations: int = 5,
    ) -> List[Citation]:
        return self._extractor.extract_from_vector_results(
            vector_results=vector_results,
            max_citations=max_citations,
        )

    def extract_citations_from_web_results(
        self,
        web_results: Dict[str, Any],
        max_citations: int = 3,
    ) -> List[Citation]:
        return self._extractor.extract_from_web_results(
            web_results=web_results,
            max_citations=max_citations,
        )

    def merge_citations(
        self,
        kb_citations: List[Citation],
        web_citations: List[Citation],
        max_total: int = 5,
    ) -> List[Citation]:
        return self._filter.merge(kb_citations, web_citations, max_total=max_total)

    def _sanitize_snippet(self, snippet: str) -> str:
        return self._snippet_sanitizer.sanitize(snippet)

    @staticmethod
    def clean_source_name(name: str) -> str:
        return clean_source_name(name)

    def _normalize_tokens(self, words: set) -> set:
        return self._filter._normalize_tokens(words)

    def filter_citations_by_answer(
        self,
        citations: List[Citation],
        answer: str,
        query: str = "",
        min_match_threshold: int = 1,
    ) -> List[Citation]:
        return self._filter.filter_by_answer(
            citations=citations,
            answer=answer,
            query=query,
            min_match_threshold=min_match_threshold,
        )

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
