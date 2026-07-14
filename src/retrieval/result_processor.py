"""
Result post-processing for retrieval.

Handles formatting LangChain Documents into the dict shape expected by
the orchestrator, Voyage reranking, source diversification, and
VCM methodology-code boosting.
"""

import logging
import os
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Separators used to split methodology codes from descriptive filename titles.
FILENAME_SEPARATOR_RE = re.compile(r"[-_.\s]+")

METHODOLOGY_CODE_PATTERN = re.compile(
    r'\b(VM\d{4}|VMD\d{4}|ACM\d{4}|AMS-[IVX]+\.[A-Z]|CDM-[A-Z]+\d*|GS-[A-Z]+\d*|VT\d{4})\b',
    re.IGNORECASE
)


def format_results(docs_with_scores: List) -> Dict[str, Any]:
    """Format LangChain (Document, score) tuples into the orchestrator's result dict.

    Scores are clamped to [0, 1] and distance is computed as ``1 - score``.
    """
    ids = []
    documents = []
    metadatas = []
    distances = []
    scores = []

    for i, (doc, score) in enumerate(docs_with_scores):
        ids.append(doc.metadata.get("id", f"doc_{i}"))
        documents.append(doc.page_content)
        metadatas.append(doc.metadata)
        clamped_score = min(max(score, 0.0), 1.0)
        distances.append(1 - clamped_score)
        scores.append(clamped_score)

    return {
        "ids": ids,
        "documents": documents,
        "metadatas": metadatas,
        "distances": distances,
        "scores": scores,
    }


def empty_result() -> Dict[str, Any]:
    """Return an empty result structure matching format_results output."""
    return {
        "ids": [],
        "documents": [],
        "metadatas": [],
        "distances": [],
        "scores": [],
    }


def rerank_results(
    reranker,
    query: str,
    docs_with_scores: List,
    top_k: int,
) -> Dict[str, Any]:
    """Rerank results using a pluggable reranker.

    Falls back to dense scores (via format_results) if reranking fails or
    ``reranker`` is ``None`` (RERANK_PROVIDER=none).
    """
    if reranker is None:
        return format_results(docs_with_scores[:top_k])

    try:
        doc_texts = [doc.page_content for doc, _ in docs_with_scores]

        ranked = reranker.rerank(
            query=query,
            documents=doc_texts,
            top_k=top_k,
        )

        ids = []
        documents = []
        metadatas = []
        distances = []
        scores = []

        for original_index, relevance_score in ranked:
            original_doc, _ = docs_with_scores[original_index]
            ids.append(original_doc.metadata.get("id", f"doc_{original_index}"))
            documents.append(original_doc.page_content)
            metadatas.append(original_doc.metadata)
            clamped_score = min(max(relevance_score, 0.0), 1.0)
            distances.append(1 - clamped_score)
            scores.append(clamped_score)

        logger.debug("Reranking completed: %d results", len(documents))

        return {
            "ids": ids,
            "documents": documents,
            "metadatas": metadatas,
            "distances": distances,
            "scores": scores,
        }

    except Exception as e:
        logger.warning("Reranking failed, using dense scores: %s", e)
        return format_results(docs_with_scores[:top_k])


def diversify_by_source(
    results: Dict[str, Any],
    max_per_source: int,
    query: str,
) -> Dict[str, Any]:
    """Cap chunks per source to prevent single-source dominance.

    Applied after reranking but before methodology boosting.
    Methodology-matched chunks bypass the cap so that targeted
    VCM queries retain all relevant chunks from the correct source.
    """
    documents = results.get("documents", [])
    if not documents:
        return results

    query_codes = set(m.upper() for m in METHODOLOGY_CODE_PATTERN.findall(query))

    source_counts: Dict[str, int] = {}
    keep_indices: List[int] = []

    for i in range(len(documents)):
        meta = results["metadatas"][i] if i < len(results.get("metadatas", [])) else {}
        source = (meta or {}).get("source", "") or (meta or {}).get("file_name", "") or "unknown"

        # Methodology-matched chunks bypass the per-source cap
        bypassed = False
        if query_codes:
            doc_text = documents[i]
            doc_codes = set(m.upper() for m in METHODOLOGY_CODE_PATTERN.findall(doc_text))
            source_codes = set(m.upper() for m in METHODOLOGY_CODE_PATTERN.findall(source))
            doc_codes.update(source_codes)
            if query_codes & doc_codes:
                bypassed = True

        current_count = source_counts.get(source, 0)
        if bypassed or current_count < max_per_source:
            keep_indices.append(i)
            source_counts[source] = current_count + 1

    if len(keep_indices) == len(documents):
        return results  # nothing filtered

    dropped = len(documents) - len(keep_indices)
    logger.debug(
        "Source diversification: kept %d/%d chunks (dropped %d, max_per_source=%d)",
        len(keep_indices), len(documents), dropped, max_per_source,
    )

    return {
        key: [vals[i] for i in keep_indices if i < len(vals)]
        for key, vals in results.items()
    }


def boost_methodology_matches(
    results: Dict[str, Any],
    query: str,
) -> Dict[str, Any]:
    """Prioritize the primary document when a query references a specific code.

    Two problems this method solves:

    1) Score saturation: Voyage rerank scores at the top are routinely
       clamped at 1.0, so a flat additive boost is a no-op. We therefore
       use a *priority tier*.
    2) Primary-source surfacing: when the user asks about VM0048, the
       actual VM0048 specification (e.g. VM0048.md) must lead — not a
       review, database, or commentary that merely mentions VM0048.
       The same principle applies to policies, projects, standards, etc.

    Tiers (higher tier sorts first; ties broken by base rerank score):
      tier 3: source filename (without extension) IS the queried code.
              This is the unambiguous primary document.
      tier 2: document_id matches a query code and doc_type corresponds
              (methodology/policy/project/standard). A related record
              about the code, but not the primary file itself.
      tier 1: any other chunk whose text/source mentions a query code.
              (legacy +0.3 boost for relevance signalling.)
      tier 0: no code match (untouched score)
    """
    query_codes = set(match.upper() for match in METHODOLOGY_CODE_PATTERN.findall(query))

    if not query_codes or not results.get("documents"):
        return results

    def _filename_is_code(source_path: str, code: str) -> bool:
        """True when the basename without extension starts with the code.

        File names in the KB are long, hyphenated titles like
        ``VM0048-Reducing-Emissions-...v1.0.pdf``. The leading methodology
        code may itself contain hyphens (e.g. ``AMS-III.D`` or ``CDM-AM0010``),
        so we compare the leading token sequence against the code instead of
        splitting on the first separator.
        """
        if not source_path or not code:
            return False
        base = os.path.basename(source_path)
        name, _ = os.path.splitext(base)
        code_tokens = FILENAME_SEPARATOR_RE.split(code.upper())
        name_tokens = FILENAME_SEPARATOR_RE.split(name.upper())
        if len(name_tokens) < len(code_tokens):
            return False
        return code_tokens == name_tokens[:len(code_tokens)]

    ranked: List[tuple] = []  # (index, tier, score)
    for i, doc in enumerate(results["documents"]):
        base_score = results["scores"][i] if "scores" in results else (1 - results["distances"][i])

        metadata = results["metadatas"][i] or {}
        source = metadata.get("source", "") or metadata.get("file_name", "") or ""
        doc_type = (metadata.get("doc_type") or "").lower()
        document_id = (metadata.get("document_id") or "").upper()

        text_codes = set(m.upper() for m in METHODOLOGY_CODE_PATTERN.findall(doc))
        source_codes = set(m.upper() for m in METHODOLOGY_CODE_PATTERN.findall(source))
        doc_codes = text_codes | source_codes
        if document_id:
            doc_codes.add(document_id)

        if not (query_codes & doc_codes):
            ranked.append((i, 0, base_score))
            continue

        # Tier 3: the source filename IS the queried code (e.g. VM0048.md).
        if any(_filename_is_code(source, code) for code in query_codes):
            ranked.append((i, 3, min(base_score + 0.5, 1.0)))
            continue

        # Tier 2: a typed record whose document_id matches the code.
        is_typed_match = (
            doc_type in ("methodology", "policy", "project", "standard")
            and document_id in query_codes
        )
        if is_typed_match:
            ranked.append((i, 2, min(base_score + 0.3, 1.0)))
            continue

        # Tier 1: mentions the code but is not the primary document.
        ranked.append((i, 1, min(base_score + 0.2, 1.0)))

    ranked.sort(key=lambda r: (r[1], r[2]), reverse=True)
    sorted_indices = [idx for idx, _, _ in ranked]

    return {
        "ids": [results["ids"][i] for i in sorted_indices],
        "documents": [results["documents"][i] for i in sorted_indices],
        "metadatas": [results["metadatas"][i] for i in sorted_indices],
        "distances": [results["distances"][i] for i in sorted_indices],
        "scores": [score for _, _, score in ranked],
    }


def apply_post_processing(
    results: Dict[str, Any],
    query: str,
    max_per_source: int,
) -> Dict[str, Any]:
    """Apply source diversification and methodology boosting in sequence."""
    if max_per_source > 0:
        results = diversify_by_source(results, max_per_source, query)
    results = boost_methodology_matches(results, query)
    return results
