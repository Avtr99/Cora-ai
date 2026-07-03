"""
Cheap, no-LLM grounding metrics for RAG answer quality.

These heuristics compute token-level overlap between answer text and
retrieved source text.  They are useful as:
  - A fast pre-filter before expensive LLM validation
  - A CI/CD quality gate
  - A lightweight metric in the eval pipeline

Adapted from GuidelineCopilot's grounding_overlap_score with enhancements
for the VCM domain (methodology code awareness, n-gram overlap).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Sequence

# Minimum keyword length to consider for overlap (filters out "a", "is", etc.)
_MIN_KEYWORD_LEN = 4

# Regex for extracting simple alphabetic keywords
_KEYWORD_RE = re.compile(r"[a-zA-Z]{%d,}" % _MIN_KEYWORD_LEN)

# Regex for VCM methodology codes (VM0007, VMD0049, ACM0003, etc.)
_METHODOLOGY_CODE_RE = re.compile(
    r"\b(VM\d{4}|VMD\d{4}|ACM\d{4}|AMS-[IVX]+\.[A-Z]|CDM-[A-Z]+|AR-\d+|GS-\d+)\b",
    re.IGNORECASE,
)

# Common English stop words to exclude from keyword matching
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "about", "above", "after", "again", "also", "been", "before", "below",
        "between", "both", "could", "each", "every", "from", "have", "here",
        "into", "just", "more", "most", "must", "need", "other", "over",
        "same", "should", "some", "such", "than", "that", "these", "this",
        "those", "through", "under", "very", "what", "when", "where", "which",
        "while", "will", "with", "would", "your",
    }
)


def grounding_overlap_score(
    answer: str,
    citations: Sequence[Dict[str, Any]],
    snippet_key: str = "snippet",
) -> float:
    """
    Cheap faithfulness heuristic: compute token-overlap ratio between
    answer keywords and concatenated citation snippets.

    Returns a float in [0.0, 1.0].  Higher means more answer content
    is traceable to retrieved evidence.

    Args:
        answer: Generated answer text.
        citations: Sequence of citation dicts, each containing a snippet.
        snippet_key: Key in each citation dict holding the text snippet.

    Example:
        >>> grounding_overlap_score(
        ...     "VM0007 is a REDD+ methodology framework.",
        ...     [{"snippet": "VM0007 REDD+ Methodology Framework for jurisdictional programs"}]
        ... )
        0.8  # 4 of 5 meaningful keywords found in evidence
    """
    if not answer or not citations:
        return 0.0

    evidence_text = " ".join(
        (c.get(snippet_key) or "") for c in citations
    ).lower()

    if not evidence_text.strip():
        return 0.0

    # Extract unique keywords from answer (preserve order, deduplicate)
    answer_lower = answer.lower()
    answer_terms = list(dict.fromkeys(_KEYWORD_RE.findall(answer_lower)))
    # Filter stop words
    answer_terms = [t for t in answer_terms if t not in _STOP_WORDS]

    if not answer_terms:
        return 0.0

    evidence_tokens = set(re.findall(r'\b[a-zA-Z]+\b', evidence_text))
    hits = sum(1 for t in answer_terms if t in evidence_tokens)
    return hits / len(answer_terms)


def methodology_grounding_score(
    answer: str,
    citations: Sequence[Dict[str, Any]],
    snippet_key: str = "snippet",
) -> float:
    """
    Check whether methodology codes mentioned in the answer appear in
    the retrieved evidence.  This is a stricter, domain-specific check
    because methodology codes are high-stakes factual claims.

    Returns 1.0 if all codes are grounded, 0.0 if none, or a ratio.
    Returns 1.0 trivially if the answer mentions no methodology codes
    (nothing to validate).
    """
    if not answer:
        return 0.0

    answer_codes = set(m.upper() for m in _METHODOLOGY_CODE_RE.findall(answer))
    if not answer_codes:
        return 1.0  # no codes to validate → pass

    if not citations:
        return 0.0

    evidence_text = " ".join(
        (c.get(snippet_key) or "") for c in citations
    ).upper()

    if not evidence_text.strip():
        return 0.0

    found = sum(1 for code in answer_codes if code in evidence_text)
    return found / len(answer_codes)


def ngram_overlap_score(
    answer: str,
    citations: Sequence[Dict[str, Any]],
    snippet_key: str = "snippet",
    n: int = 2,
) -> float:
    """
    Compute n-gram overlap between answer and evidence.  More robust
    than single-keyword overlap because it captures phrase-level grounding.

    Returns a float in [0.0, 1.0].
    """
    if not answer or not citations:
        return 0.0

    evidence_text = " ".join(
        (c.get(snippet_key) or "") for c in citations
    ).lower()

    if not evidence_text.strip():
        return 0.0

    def _ngrams(text: str, n: int) -> set[str]:
        words = re.findall(r'[a-zA-Z]+', text.lower())
        if len(words) < n:
            return set()
        return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}

    answer_ngrams = _ngrams(answer, n)
    if not answer_ngrams:
        return 0.0

    evidence_ngrams = _ngrams(evidence_text, n)
    hits = sum(1 for ng in answer_ngrams if ng in evidence_ngrams)
    return hits / len(answer_ngrams)


def composite_grounding_score(
    answer: str,
    citations: Sequence[Dict[str, Any]],
    snippet_key: str = "snippet",
) -> Dict[str, float]:
    """
    Compute all grounding metrics and return a composite summary.

    Returns dict with:
      - keyword_overlap: grounding_overlap_score result
      - methodology_grounding: methodology_grounding_score result
      - bigram_overlap: ngram_overlap_score (n=2) result
      - composite: weighted average

    Weighting strategy:
      - When methodology codes exist in answer: 0.4 kw + 0.3 meth + 0.3 bi
      - When no methodology codes: methodology_grounding trivially returns 1.0
        (nothing to validate), so redistribute its weight to the actual
        grounding signals: 0.55 kw + 0.0 meth + 0.45 bi
    """
    kw = grounding_overlap_score(answer, citations, snippet_key)
    meth = methodology_grounding_score(answer, citations, snippet_key)
    bi = ngram_overlap_score(answer, citations, snippet_key, n=2)

    has_codes = bool(_METHODOLOGY_CODE_RE.findall(answer))
    if has_codes:
        composite = 0.4 * kw + 0.3 * meth + 0.3 * bi
    else:
        composite = 0.55 * kw + 0.45 * bi

    return {
        "keyword_overlap": round(kw, 4),
        "methodology_grounding": round(meth, 4),
        "bigram_overlap": round(bi, 4),
        "composite": round(composite, 4),
    }
