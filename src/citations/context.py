"""Canonical knowledge-base context builder.

This is the single place where retrieved chunks become prompt context. Every
chunk placed in the prompt is numbered consecutively starting at 1 — the
``<source index="N">`` tag, the ``[cite_kb: N]`` marker the model emits, and
the ``Citation.index`` the displayed list uses all share that number. Nothing
downstream renumbers.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Dict, List

from .config import CitationConfig, SAFE_METADATA_FIELDS
from .models import Citation, VectorResults
from .source_name import clean_source_name, get_source_name
from ..config import get_settings
from ..query_processing.prompts import MAX_CONTEXT_LENGTH
from ..retrieval.score_utils import DistanceMetric, normalize_score


@dataclass
class KBContext:
    """Prompt-ready KB context plus one citation per chunk actually placed."""

    text: str
    summaries: List[str]
    sources: List[str]
    citations: List[Citation]


def build_kb_context(vector_results: Dict[str, Any]) -> KBContext:
    """Build prompt context and per-chunk citations from vector results.

    Numbering is per chunk placed in the prompt: the first placed chunk is
    index 1 and indices are consecutive — skipped empty chunks consume no
    number, and a chunk partially included by the character budget still gets
    a citation.
    """
    docs = vector_results.get("documents", [])
    metas = vector_results.get("metadatas", [])

    if not docs:
        return KBContext(text="", summaries=[], sources=[], citations=[])

    if vector_results.get("structured_mode"):
        return _structured_context(vector_results)

    settings = get_settings()
    max_context_chars = getattr(settings, "MAX_CONTEXT_CHARS", MAX_CONTEXT_LENGTH)
    max_docs = getattr(settings, "MAX_DOCUMENTS_FOR_ANSWER", 10)
    config = CitationConfig()

    typed = VectorResults.from_dict(vector_results)
    # Resolve distance metric from retrieval results, fallback to cosine distance.
    try:
        metric = DistanceMetric(typed.distance_metric) if typed.distance_metric else DistanceMetric.COSINE_DISTANCE
    except ValueError:
        metric = DistanceMetric.COSINE_DISTANCE

    sources: List[str] = []
    summaries: List[str] = []
    context_parts: List[str] = []
    citations: List[Citation] = []
    current_length = 0
    placed = 0

    for i, doc in enumerate(docs):
        if not doc or i >= max_docs:
            continue

        meta = metas[i] if i < len(metas) else None
        source_name = ""
        if meta and isinstance(meta, dict):
            # Prefer the extracted document title (from the converted markdown)
            # over the raw filename, which may be a placeholder name.
            src = get_source_name(meta)
            if src:
                source_name = clean_source_name(src) or src
                if source_name and source_name not in sources:
                    sources.append(source_name)
            if meta.get("summary"):
                summaries.append(meta["summary"])

        # Wrap the chunk with a source label and its 1-indexed prompt position
        # so the LLM can cite with [cite_kb: N] and the number is stable all
        # the way through to the displayed citation list.
        index = placed + 1
        tag_name = html.escape(source_name or f"Document {index}", quote=True)
        wrapped = f'<source index="{index}" name="{tag_name}">\n{doc}\n</source>'
        wrapped_len = len(wrapped)

        if current_length + wrapped_len > max_context_chars:
            remaining = max_context_chars - current_length
            if remaining > 100:
                placed = index
                truncated = wrapped[:remaining]
                last_para = truncated.rfind("\n\n")
                if last_para > 0:
                    context_parts.append(wrapped[:last_para])
                else:
                    for punct in [".", "!", "?"]:
                        last_punct = truncated.rfind(punct)
                        if last_punct > 0 and last_punct + 1 < len(truncated) and truncated[last_punct + 1].isspace():
                            context_parts.append(wrapped[:last_punct + 1])
                            break
                    else:
                        context_parts.append(wrapped[:remaining])
                citations.append(_chunk_citation(typed, i, index, source_name, config, metric))
            break

        placed = index
        context_parts.append(wrapped)
        current_length += wrapped_len
        citations.append(_chunk_citation(typed, i, index, source_name, config, metric))

    return KBContext(
        text="\n\n".join(context_parts),
        summaries=summaries,
        sources=sources,
        citations=citations,
    )


def citations_from_result(result: Dict[str, Any]) -> List[Citation]:
    """Pop the ``context_citations`` payload a ``search_and_process`` result
    carries and rebuild the Citations. Returns ``[]`` when absent."""
    raw = result.pop("context_citations", None) or []
    return [Citation.from_dict(item) for item in raw if isinstance(item, dict)]


def _chunk_citation(
    typed: VectorResults,
    pos: int,
    index: int,
    source_name: str,
    config: CitationConfig,
    metric: DistanceMetric,
) -> Citation:
    """Build the citation for the chunk at document-list position ``pos``
    placed in the prompt at ``index``."""
    metadata = typed.metadatas[pos]
    document = typed.documents[pos]

    # Prefer the explicit similarity score from the retriever when it is
    # available (e.g., from a reranker). Fall back to normalizing raw
    # distances, which may be cosine distance or 1 - similarity.
    if typed.scores and pos < len(typed.scores):
        relevance_score = max(0.0, min(1.0, float(typed.scores[pos])))
    else:
        distance = typed.distances[pos] if pos < len(typed.distances) else 1.0
        relevance_score = normalize_score(distance, metric)

    body = _strip_leading_context(document, metadata)
    snippet = (
        body[: config.snippet_max_length] + "..."
        if len(body) > config.snippet_max_length
        else body
    )

    safe_metadata = {k: v for k, v in metadata.items() if k in SAFE_METADATA_FIELDS}
    doc_store_id = metadata.get("doc_store_id")
    return Citation(
        source_id=metadata.get("id", f"doc_{pos}"),
        source_name=source_name or f"Document {index}",
        source_type="knowledge_base",
        content_snippet=snippet,
        relevance_score=round(relevance_score, 3),
        page_number=metadata.get("page_number"),
        section=metadata.get("section"),
        url=metadata.get("url"),
        metadata=safe_metadata,
        index=index,
        marker_type="knowledge_base",
        document_key=str(doc_store_id) if doc_store_id is not None else None,
    )


def _strip_leading_context(document: str, metadata: Dict[str, Any]) -> str:
    """Drop the index-time context block so the snippet shows chunk content.

    ``page_content`` leads with retrieval context rather than the chunk body:
    a flat ``title\\n\\n`` / ``original_filename\\n\\n`` header (legacy chunks,
    heading-less chunks, dataset rows), or the contextualize() heading
    ancestry ``title\\nsection\\n…\\nbody``. The ``section`` metadata field
    stores that same ancestry joined by ``" / "``, so both shapes are
    recoverable exactly.
    """
    section = metadata.get("section")
    if isinstance(section, str) and section:
        heading_block = section.replace(" / ", "\n")
        if document.startswith(heading_block):
            return document[len(heading_block) :].lstrip()
    for name in (metadata.get("title"), metadata.get("original_filename")):
        if isinstance(name, str) and name and document.startswith(name):
            rest = document[len(name) :]
            if rest.startswith("\n"):
                return rest.lstrip("\n")
    return document


def _structured_context(vector_results: Dict[str, Any]) -> KBContext:
    """Structured dataset context is already formatted by the retriever.

    The whole dataset is one citation with ``index=None`` — there is no
    ``<source index>`` tag for markers to reference.
    """
    docs = vector_results.get("documents", [])
    metas = vector_results.get("metadatas", [])
    meta = metas[0] if metas and isinstance(metas[0], dict) else {}
    document = docs[0]
    config = CitationConfig()

    raw_name = get_source_name(meta)
    source_name = (clean_source_name(raw_name) or raw_name) if raw_name else "Dataset"
    snippet = (
        document[: config.snippet_max_length] + "..."
        if len(document) > config.snippet_max_length
        else document
    )

    scores = vector_results.get("scores") or []
    try:
        relevance_score = float(scores[0]) if scores else 1.0
    except (TypeError, ValueError):
        relevance_score = 1.0

    doc_store_id = meta.get("doc_store_id")
    citation = Citation(
        source_id=meta.get("id", "doc_0"),
        source_name=source_name,
        source_type="knowledge_base",
        content_snippet=snippet,
        relevance_score=round(max(0.0, min(1.0, relevance_score)), 3),
        page_number=meta.get("page_number"),
        section=meta.get("section"),
        url=meta.get("url"),
        metadata={k: v for k, v in meta.items() if k in SAFE_METADATA_FIELDS},
        marker_type="knowledge_base",
        document_key=str(doc_store_id) if doc_store_id is not None else None,
    )
    return KBContext(text=document, summaries=[], sources=[], citations=[citation])
