"""
Document summarization service with domain-specific styles.

Adapted from GuidelineCopilot's summarize_guideline() with VCM-specific
styles and retrieval queries. Each style uses a tailored retrieval query
and prompt template to produce structured summaries for carbon credit
methodology documents.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence

from ..evaluation.grounding_metrics import composite_grounding_score
from ..retrieval.score_utils import normalize_score, DistanceMetric

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Style-specific retrieval queries
# ---------------------------------------------------------------------------

_STYLE_RETRIEVAL_QUERIES: Dict[str, str] = {
    "methodology_overview": "{title} summary overview key recommendations purpose scope main findings applicability conditions",
    "key_requirements": "{title} key requirements mandatory criteria compliance conditions must shall required provisions",
    "monitoring_steps": "{title} monitoring steps measurement reporting verification MRV procedure data collection frequency parameters",
    "eligibility_criteria": "{title} eligibility criteria inclusion exclusion conditions qualifying applicability scope project type",
}

# ---------------------------------------------------------------------------
# Style-specific prompt instructions
# ---------------------------------------------------------------------------

_STYLE_INSTRUCTIONS: Dict[str, str] = {
    "methodology_overview": (
        "Create a concise TL;DR summary of the carbon credit methodology:\n"
        "- 6–10 bullets max\n"
        "- Include purpose + key applicability conditions + any critical warnings\n"
        "- Cite methodology codes (VM0007, etc.) when mentioned in excerpts\n"
        "- Keep it non-hallucinated and grounded in excerpts\n"
    ),
    "key_requirements": (
        "Create a focused summary of key requirements:\n"
        "- Bullet list of mandatory provisions (use 'must' / 'shall' / 'required' wording)\n"
        "- Group by theme (e.g., additionality, baseline, leakage, permanence)\n"
        "- Include any numeric thresholds or timelines if present\n"
        "- Be specific and actionable\n"
    ),
    "monitoring_steps": (
        "Create a step-by-step summary of monitoring and MRV requirements:\n"
        "- 6–12 ordered steps for the monitoring/verification workflow\n"
        "- Include parameters to measure, data collection frequency, and reporting deadlines\n"
        "- Include any decision points or conditional monitoring requirements\n"
        "- Be specific and actionable\n"
    ),
    "eligibility_criteria": (
        "Create a focused eligibility summary:\n"
        '- "Eligible if" bullet list\n'
        '- "Not eligible if" bullet list\n'
        "- Include any numeric thresholds (e.g., minimum project size, vintage requirements)\n"
        "- Include applicable project type restrictions\n"
    ),
}

# System prompt for summarization
_SUMMARIZE_SYSTEM = (
    "You are a helpful assistant summarizing carbon credit methodology excerpts. "
    "Use ONLY the provided excerpts. If information is missing, say so. "
    "Do not add information not present in the excerpts."
)


def _build_retrieval_query(style: str, title: Optional[str] = None) -> str:
    """Build a style-specific retrieval query, optionally prefixed with document title."""
    template = _STYLE_RETRIEVAL_QUERIES.get(style, _STYLE_RETRIEVAL_QUERIES["methodology_overview"])
    return template.format(title=title or "")


def _build_user_prompt(style: str, context: str) -> str:
    """Build the user prompt with style-specific instructions and context."""
    instructions = _STYLE_INSTRUCTIONS.get(style, _STYLE_INSTRUCTIONS["methodology_overview"])
    return (
        f"{instructions}\n\n"
        f"Methodology excerpts (cite internally by referring to the numbered blocks):\n"
        f"{context}"
    )


def _build_context(citations: Sequence[Dict[str, Any]]) -> str:
    """Build numbered context blocks from retrieved citations."""
    blocks = []
    for i, c in enumerate(citations, start=1):
        meta = c.get("metadata", c.get("meta", {}))
        doc_id = meta.get("document_id", meta.get("doc_id", ""))
        page = meta.get("page_number", meta.get("page", ""))
        text = c.get("content", c.get("text", ""))
        page_ref = f" p.{page}" if page else ""
        doc_ref = f" ({doc_id}{page_ref})" if doc_id else ""
        blocks.append(f"[{i}]{doc_ref}\n{text}")
    return "\n\n".join(blocks)


def _build_citations_raw(
    documents: List[str],
    metadatas: List[Dict[str, Any]],
    distances: List[float],
    top_k: int,
) -> List[Dict[str, Any]]:
    """Zip retrieval results into citation dicts with content/metadata/distance."""
    return [
        {"content": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(documents[:top_k], metadatas[:top_k], distances[:top_k])
    ]


async def summarize_document(
    style: str = "methodology_overview",
    document_id: Optional[str] = None,
    top_k: int = 8,
    retriever=None,
    gemini_client=None,
) -> Dict[str, Any]:
    """
    Summarize a document (or all documents) using style-specific retrieval
    and generation.

    Args:
        style: Summarization style (methodology_overview, key_requirements, etc.)
        document_id: Optional document ID filter for retrieval.
        top_k: Number of chunks to retrieve.
        retriever: LangChainRetriever instance.
        gemini_client: GeminiClient instance.

    Returns:
        Dict with summary, citations, grounding_score, metadata.
    """
    start_time = time.perf_counter()

    if retriever is None or gemini_client is None:
        raise ValueError("retriever and gemini_client are required")

    # Build retrieval filter
    where = {"document_id": document_id} if document_id else None

    # Retrieve
    retrieval_query = _build_retrieval_query(style)
    vector_results = await retriever.retrieve(query=retrieval_query, where=where)

    # Extract citations for context building
    documents = vector_results.get("documents", [])
    metadatas = vector_results.get("metadatas", [])
    distances = vector_results.get("distances", [])

    citations_raw = _build_citations_raw(documents, metadatas, distances, top_k)

    # Try to extract document title from first result metadata
    doc_title = None
    if citations_raw:
        doc_title = citations_raw[0]["metadata"].get("title")
        # Re-build retrieval query with title if available
        if doc_title:
            enhanced_query = _build_retrieval_query(style, title=doc_title)
            if enhanced_query != retrieval_query:
                vector_results = await retriever.retrieve(query=enhanced_query, where=where)
                documents = vector_results.get("documents", [])
                metadatas = vector_results.get("metadatas", [])
                distances = vector_results.get("distances", [])
                citations_raw = _build_citations_raw(documents, metadatas, distances, top_k)

    context = _build_context(citations_raw)
    user_prompt = _build_user_prompt(style, context)

    # Generate summary via LLM
    full_prompt = f"{_SUMMARIZE_SYSTEM}\n\n{user_prompt}"
    try:
        summary_text = await gemini_client.generate_text(full_prompt)
    except Exception as e:
        logger.error("Summarize generation failed: %s", e, exc_info=True)
        summary_text = f"Summary generation failed: {type(e).__name__}. Please try again."

    # Compute grounding score
    grounding_citations = [{"snippet": c["content"][:500]} for c in citations_raw]
    grounding = composite_grounding_score(summary_text, grounding_citations)

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # Format citations for response
    formatted_citations = []
    for c in citations_raw:
        meta = c["metadata"]
        dist = c["distance"]
        formatted_citations.append({
            "source_name": (
                meta.get("file_name")
                or meta.get("parent_doc")
                or meta.get("source")
                or "Unknown"
            ),
            "snippet": c["content"][:350],
            "relevance_score": round(normalize_score(dist, DistanceMetric.COSINE_DISTANCE), 3),
            "document_id": meta.get("document_id"),
            "page_number": meta.get("page_number"),
            "section": meta.get("section"),
        })

    return {
        "summary": summary_text,
        "style": style,
        "document_id": document_id,
        "citations": formatted_citations,
        "grounding_score": grounding["composite"],
        "metadata": {
            "chunks_retrieved": len(citations_raw),
            "elapsed_ms": round(elapsed_ms, 1),
            "grounding_detail": grounding,
        },
    }
