"""
Shared utilities for retrieval implementations.

Common functionality for multi-round retrieval and result filtering
used across different retriever implementations.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass

from ..config import get_settings
from .result_processor import empty_result

logger = logging.getLogger(__name__)

# Minimal English stop-word set for lexical overlap. Kept inline to avoid a
# dependency on nltk or similar. Filters out function words so overlap reflects
# content-word sharing. Set lookup is O(1) so ordering is cosmetic.
_STOP_WORDS: Set[str] = {
    # Articles
    "a", "an", "the",
    # Pronouns
    "i", "you", "he", "she", "it", "we", "they",
    "me", "him", "her", "us", "them",
    "my", "your", "his", "its", "our", "their",
    "mine", "yours", "hers", "ours", "theirs",
    "what", "which", "who", "whom", "whose",
    "this", "that", "these", "those",
    # Be verbs
    "am", "is", "are", "was", "were", "be", "been", "being",
    # Auxiliaries
    "have", "has", "had", "having",
    "do", "does", "did", "doing",
    "will", "would", "shall", "should",
    "can", "could", "may", "might", "must", "ought",
    "need", "dare", "used",
    # Prepositions
    "to", "of", "in", "for", "on", "with", "at", "by", "from", "as",
    "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "further", "across", "against", "along", "among",
    "around", "behind", "beneath", "beside", "besides", "beyond", "down",
    "except", "inside", "like", "near", "off", "onto", "out", "outside",
    "over", "past", "since", "throughout", "toward", "underneath", "until",
    "up", "upon", "within", "without",
    # Conjunctions
    "and", "or", "but", "nor", "not", "so", "yet",
    "both", "either", "neither", "if", "then", "else",
    # Determiners / quantifiers
    "each", "every", "all", "any", "few", "more", "most", "other",
    "some", "such", "no", "only", "own", "same", "than", "too", "very",
    "just", "about",
    # Adverbs
    "how", "when", "where", "why", "also",
    "there", "here", "now", "still", "again", "once", "twice",
}

_WORD_RE = re.compile(r'[A-Za-z][A-Za-z0-9\-]*')


def _extract_content_words(text: str) -> Set[str]:
    """Extract lower-cased content words (non stop-words) from text."""
    tokens = _WORD_RE.findall(text.lower())
    return {t for t in tokens if t not in _STOP_WORDS and len(t) > 1}


def compute_lexical_overlap(query: str, doc_text: str) -> float:
    """Compute the fraction of query content words found in the doc.

    Returns 0.0 when the query has no content words (e.g. pure stop-words).
    This is a cheap lexical signal used as a complement to the reranker's
    semantic score — it catches topically-adjacent-but-off-topic docs that
    the reranker might score above the relevance floor.

    Args:
        query: User query string.
        doc_text: Retrieved document text.

    Returns:
        Overlap fraction in [0, 1].
    """
    query_words = _extract_content_words(query)
    if not query_words:
        return 0.0
    doc_words = _extract_content_words(doc_text)
    if not doc_words:
        return 0.0
    return len(query_words & doc_words) / len(query_words)


@dataclass
class RetrievalRoundConfig:
    """Configuration for a single retrieval round.

    For round 1, ``k`` is the final top-K after reranking and ``threshold`` is
    the score floor used in the non-rerank fallback path. For round 2
    (expansion), only ``k`` is used — it's the fetch size for additional
    candidates; there is no per-round threshold because the merged pool is
    reranked as a whole.
    """
    k: int  # Number of documents to retrieve
    threshold: Optional[float] = None  # Minimum score threshold (round 1 only)


class MultiRoundRetrievalMixin:
    """Mixin providing multi-round retrieval logic.

    Uses an expansion-pool design: round 1 fetches candidates with the user's
    filters. If the pool is sparse (fewer candidates than needed), round 2
    fetches more candidates from the same dense index. The merged pool is
    then reranked in a single pass to ``ROUND1_K`` — one coherent ranking on
    one score scale. Round 2 is NOT a separate refinement pass; it only
    expands the candidate pool before the single rerank.
    """

    def __init__(self, retrieval_rounds: int = 1):
        """Initialize multi-round retrieval configuration.

        Args:
            retrieval_rounds: 1 = single pass, 2 = expand pool if sparse.
                Values > 2 are capped at 2 (no round 3 in the expansion-pool
                design — a third fetch from the same index adds no new signal).
        """
        self.retrieval_rounds = min(retrieval_rounds, 2)
        self._round_configs = self._load_round_configs()

    def _load_round_configs(self) -> List[RetrievalRoundConfig]:
        """Load round configurations from settings."""
        settings = get_settings()

        configs = [
            RetrievalRoundConfig(
                k=getattr(settings, 'ROUND1_K', 15),
                threshold=getattr(settings, 'ROUND1_THRESHOLD', 0.3)
            )
        ]

        if self.retrieval_rounds > 1:
            # Round 2 is an expansion fetch — no threshold, just a fetch size.
            configs.append(RetrievalRoundConfig(
                k=getattr(settings, 'ROUND2_CANDIDATES', 30),
            ))

        return configs

    def should_expand_candidates(self, candidate_count: int, min_needed: int) -> bool:
        """Check if round 2 should be triggered to expand the candidate pool.

        Args:
            candidate_count: Number of raw candidates returned by round 1.
            min_needed: Minimum candidates needed for good results (typically
                round1_config.k).

        Returns:
            True if round 2 should fetch more candidates.
        """
        if self.retrieval_rounds <= 1:
            return False
        if candidate_count < min_needed:
            logger.info(
                "Round 1 returned %d candidates (below minimum %d), "
                "expanding pool with round 2",
                candidate_count, min_needed,
            )
            return True
        return False


class ResultFilter:
    """Utilities for filtering retrieval results by score threshold."""

    @staticmethod
    def filter_by_threshold_dict(
        results: Dict[str, Any],
        threshold: float
    ) -> Dict[str, Any]:
        """Filter dictionary results by score threshold.

        Used in the non-reranking path where dense scores are the final scores.

        Args:
            results: Dict with 'scores' key
            threshold: Minimum score threshold

        Returns:
            Filtered results dict (original if nothing passes threshold)
        """
        if not results or "scores" not in results:
            return results

        filtered_indices = [
            i for i, score in enumerate(results["scores"])
            if score >= threshold
        ]

        if not filtered_indices:
            return results  # Return original if nothing passes threshold

        return {
            "ids": [results["ids"][i] for i in filtered_indices],
            "documents": [results["documents"][i] for i in filtered_indices],
            "metadatas": [results["metadatas"][i] for i in filtered_indices],
            "distances": [results["distances"][i] for i in filtered_indices],
            "scores": [results["scores"][i] for i in filtered_indices],
        }

    @staticmethod
    def apply_relevance_floor(
        results: Dict[str, Any],
        threshold: float
    ) -> Dict[str, Any]:
        """Drop reranked results scoring below ``threshold``.

        Unlike :meth:`filter_by_threshold_dict` (which returns the original
        results when nothing passes), this returns an *empty* result when no
        document clears the floor. That signals to the orchestrator that the
        knowledge base has no relevant match, triggering the web-search
        fallback instead of answering from off-topic chunks.

        Args:
            results: Dict with 'scores' key (post-rerank, scores in [0, 1])
            threshold: Minimum rerank score to keep a document. <= 0 disables.

        Returns:
            Filtered results dict (possibly empty if nothing clears the floor)
        """
        if not results or "scores" not in results or threshold <= 0:
            return results

        keep = [i for i, score in enumerate(results["scores"]) if score >= threshold]

        if len(keep) == len(results["scores"]):
            return results  # nothing filtered

        dropped = len(results["scores"]) - len(keep)
        logger.info(
            "Relevance floor %.2f dropped %d/%d reranked docs (%d remain)",
            threshold, dropped, len(results["scores"]), len(keep),
        )

        return {
            "ids": [results["ids"][i] for i in keep],
            "documents": [results["documents"][i] for i in keep],
            "metadatas": [results["metadatas"][i] for i in keep],
            "distances": [results["distances"][i] for i in keep],
            "scores": [results["scores"][i] for i in keep],
        }

    @staticmethod
    def filter_by_threshold_list(
        results: List[Any],
        threshold: float,
        score_attr: str = "score"
    ) -> List[Any]:
        """Filter list results by score threshold.

        Args:
            results: List of objects with score attribute
            threshold: Minimum score threshold
            score_attr: Name of score attribute (default: "score")

        Returns:
            Filtered results list
        """
        return [r for r in results if getattr(r, score_attr, 0) >= threshold]

    @staticmethod
    def apply_overlap_guard(
        results: Dict[str, Any],
        query: str,
        threshold: float,
        alternate_query: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Drop the entire result set if lexical overlap is too low.

        This is a zero-cost pre-LLM guard that complements the rerank score
        floor. It catches the case where the reranker gives borderline-passing
        scores to topically-adjacent-but-off-topic docs (e.g. query "just
        transition mechanism" retrieves VCM docs mentioning "transition" in
        a different context). If the BEST doc's overlap is below ``threshold``,
        ALL docs are collectively off-topic and retrieval returns empty so
        the orchestrator falls back to web search.

        Uses MAX (not MEAN) overlap because in a normal top-K result set some
        docs are less relevant than others. Mean would let a few borderline
        docs drag the average below threshold even when the top doc is highly
        relevant. Max is conservative: it only drops the result set when even
        the best doc shares too few content words with the query.

        When ``alternate_query`` is provided (e.g. the original user query
        alongside the rewritten one), per-doc overlap is computed against BOTH
        queries and the higher value is used. This prevents false drops when
        the rewriter expands acronyms: a doc saying "VCS" matches the original
        query "VCS" while a doc saying "Verified Carbon Standard" matches the
        rewrite — using only one form would unfairly drop the other.

        Args:
            results: Dict with 'documents' key (post-rerank).
            query: Primary query string (typically the rewritten query).
            threshold: Minimum best-doc overlap to keep results. <= 0 disables.
            alternate_query: Optional second query form (typically the
                original un-rewritten query). Per-doc overlap is the MAX
                across both query forms.

        Returns:
            Original results if overlap is sufficient, empty result if not.
        """
        if not results or "documents" not in results or threshold <= 0:
            return results

        documents = results.get("documents", [])
        if not documents:
            return results

        # Extract content words from both query forms. If neither has content
        # words, overlap is meaningless — skip the guard.
        query_words = _extract_content_words(query)
        alt_words = (
            _extract_content_words(alternate_query)
            if alternate_query and alternate_query != query
            else None
        )
        if not query_words and not alt_words:
            return results

        best_overlap = 0.0
        for doc in documents:
            doc_words = _extract_content_words(doc)
            if not doc_words:
                continue
            # MAX overlap across both query forms — a doc that matches either
            # the original or the rewritten phrasing is on-topic.
            overlap = 0.0
            if query_words:
                overlap = len(query_words & doc_words) / len(query_words)
            if alt_words:
                alt_overlap = len(alt_words & doc_words) / len(alt_words)
                if alt_overlap > overlap:
                    overlap = alt_overlap
            if overlap > best_overlap:
                best_overlap = overlap

        if best_overlap >= threshold:
            return results

        logger.info(
            "Lexical overlap guard: best overlap %.2f < %.2f for query '%s' — "
            "dropping %d docs (off-topic retrieval)",
            best_overlap, threshold, query[:60], len(documents),
        )
        return empty_result()
