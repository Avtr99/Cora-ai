"""Citation filtering and deduplication logic."""

from __future__ import annotations

from typing import List, Set

from loguru import logger

from .config import CitationConfig, _WORD_RE
from .markers import extract_cited_indices, unique_sources_by_type
from .models import Citation
from .source_name import clean_source_name, normalized_source_key


class CitationFilter:
    """Applies answer-grounding filters and merge/dedup rules."""

    def __init__(self, config: CitationConfig) -> None:
        self.config = config

    def filter_by_answer(
        self,
        citations: List[Citation],
        answer: str,
        query: str = "",
        min_match_threshold: int = 1,
    ) -> List[Citation]:
        if not citations or not answer:
            return []

        answer_lower = answer.lower()
        answer_words = self._extract_signal_tokens(answer_lower)

        if query:
            query_words = self._extract_signal_tokens(query.lower())
            answer_words -= query_words

        explicitly_cited = self._extract_explicitly_cited_sources(citations, answer)
        retained_explicit: Set[tuple[str, str]] = set()
        filtered: List[Citation] = []
        filtered_out = 0

        for citation in citations:
            # Match by (source_type, strip().lower()) — the same key the
            # renumberer uses — so the filter and renumberer never disagree
            # on which citation index N refers to.
            citation_key = (citation.source_type, citation.source_name.strip().lower())
            if citation_key in explicitly_cited:
                if citation_key not in retained_explicit:
                    filtered.append(citation)
                    retained_explicit.add(citation_key)
                continue

            # Web citations from Gemini grounding are inherently answer-grounded:
            # the answer was generated FROM those sources, so they should always
            # be retained regardless of snippet/name overlap heuristics.
            if citation.source_type == "web" and citation.url:
                filtered.append(citation)
                continue

            match_count = 0

            cleaned_name = clean_source_name(citation.source_name)
            name_variants = [
                cleaned_name.lower(),
                citation.source_name.lower(),
                cleaned_name.lower().replace(" ", "_"),
                cleaned_name.lower().replace(" ", "-"),
            ]
            for variant in name_variants:
                if variant and len(variant) >= self.config.min_word_length and variant in answer_lower:
                    match_count += self.config.name_match_bonus
                    break

            if citation.content_snippet:
                snippet_words = self._extract_signal_tokens(citation.content_snippet)
                matching_words = snippet_words & answer_words
                if snippet_words:
                    overlap_ratio = len(matching_words) / len(snippet_words)
                    if (
                        overlap_ratio >= self.config.snippet_overlap_ratio_threshold
                        or len(matching_words) >= self.config.snippet_overlap_absolute_threshold
                    ):
                        match_count += 1

            if match_count >= min_match_threshold:
                filtered.append(citation)
            else:
                filtered_out += 1

        logger.info(
            "citations_filtered",
            total=len(citations),
            kept=len(filtered),
            removed=filtered_out,
        )
        return filtered

    def merge(
        self,
        kb_citations: List[Citation],
        web_citations: List[Citation],
        max_total: int,
    ) -> List[Citation]:
        all_citations = list(kb_citations) + list(web_citations)
        all_citations.sort(key=lambda item: item.relevance_score, reverse=True)

        seen_sources = set()
        seen_urls = set()
        merged: List[Citation] = []

        for citation in all_citations:
            normalized_url = self._normalize_url(citation.url)
            normalized_name = normalized_source_key(citation.source_name)

            if normalized_name and normalized_name in seen_sources:
                continue
            if normalized_url and normalized_url in seen_urls:
                continue

            if not normalized_name and not normalized_url:
                snippet_prefix = (citation.content_snippet or "")[:100]
                fallback_key = citation.source_id or snippet_prefix
                # Guard against empty fallback_key: generate unique non-empty key
                if not fallback_key:
                    fallback_key = f"no_key:{id(citation)}"
                if fallback_key in seen_sources:
                    continue
                seen_sources.add(fallback_key)

            if normalized_name:
                seen_sources.add(normalized_name)
            if normalized_url:
                seen_urls.add(normalized_url)

            merged.append(citation)
            if len(merged) >= max_total:
                break

        return merged

    def _extract_signal_tokens(self, text: str) -> Set[str]:
        tokens = {
            token.lower()
            for token in _WORD_RE.findall(text)
            if len(token) >= self.config.min_word_length and token.lower() not in self.config.stop_words
        }
        return self._normalize_tokens(tokens)

    @staticmethod
    def _normalize_tokens(words: set[str]) -> set[str]:
        expanded: set[str] = set()
        for word in words:
            expanded.add(word)
            if "-" in word:
                expanded.update(part for part in word.split("-") if len(part) >= 3)
                expanded.add(word.replace("-", ""))
        return expanded

    @staticmethod
    def _normalize_url(url: str | None) -> str | None:
        if not url:
            return None
        try:
            return url.split("?")[0].split("#")[0].lower()
        except Exception:
            return url.lower()

    def _extract_explicitly_cited_sources(
        self,
        citations: List[Citation],
        answer: str,
    ) -> Set[tuple[str, str]]:
        """Return the set of ``(source_type, source_name.strip().lower())``
        pairs that the answer explicitly references via ``[cite_kb: N]`` /
        ``[Knowledge Base, cite: N]`` / ``[cite_web: N]`` / ``[Web, cite: N]``
        markers.

        Index ``N`` is mapped via :func:`unique_sources_by_type` — the same
        convention the renumberer uses — so the filter's retain/drop decision
        and the renumberer's marker rewriting always agree on which source
        ``N`` refers to. Explicitly cited sources are retained even when
        snippet/name overlap heuristics would reject them: the LLM grounded a
        claim on that source, so dropping it would hide the evidence behind
        the answer and leave a dangling marker.
        """
        if not citations or not answer:
            return set()

        cited_indices = extract_cited_indices(answer)
        if not any(cited_indices.values()):
            return set()

        explicit: Set[tuple[str, str]] = set()
        for source_type, indices in cited_indices.items():
            if not indices:
                continue
            unique_names = unique_sources_by_type(citations, source_type)
            for n in indices:
                if 1 <= n <= len(unique_names):
                    explicit.add((source_type, unique_names[n - 1].strip().lower()))

        return explicit
