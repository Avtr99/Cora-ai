"""
Route Processor Utilities

Utility functions for route processing:
- Source name extraction and cleaning
- Timeout budget management
- Validator creation
- Cache fallback before web search
"""

import asyncio
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from .protocols import AnswerGeneratorProtocol, RelevanceCheckerProtocol

logger = logging.getLogger(__name__)


def clean_source_display_name(source_name: str) -> str:
    """
    Clean source name for display by removing path prefixes and extensions.

    Also URL-decodes names like ``vm0047%20arr%20v1.0`` so they render as
    readable text in the UI.

    Args:
        source_name: Raw source name from metadata

    Returns:
        Cleaned display name
    """
    from urllib.parse import unquote

    if not source_name:
        return source_name

    # URL-decode first so %20 becomes a space before further cleaning.
    decoded = source_name
    for _ in range(8):
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    source_name = decoded


    # Remove path prefixes
    if "/" in source_name:
        source_name = source_name.rsplit("/", 1)[-1]
    if "\\" in source_name:
        source_name = source_name.rsplit("\\", 1)[-1]

    # Remove common extensions
    for ext in [".pdf", ".docx", ".doc", ".txt", ".md", ".html"]:
        if source_name.lower().endswith(ext):
            source_name = source_name[:-len(ext)]
            break

    # Clean up underscores and hyphens
    source_name = source_name.replace("_", " ").replace("-", " ")

    return source_name.strip()


def source_name_from_metadata(
    metadata: Dict[str, Any],
    fallback: str = "Unknown Source",
) -> str:
    """
    Extract source name from document metadata.
    
    Args:
        metadata: Document metadata dict
        fallback: Fallback name if no source found
        
    Returns:
        Source name string
    """
    # Try common metadata keys in order of preference
    for key in ["source", "title", "filename", "file_name", "name", "document_name"]:
        if key in metadata and metadata[key]:
            return str(metadata[key])
    
    return fallback


def normalize_sources(sources: List[Union[str, Dict[str, Any]]]) -> List[str]:
    """
    Normalize sources to list of strings.
    
    Args:
        sources: List of source strings or dicts
        
    Returns:
        List of source name strings
    """
    normalized = []
    for source in sources:
        if isinstance(source, str):
            normalized.append(source)
        elif isinstance(source, dict):
            # Extract title or URL from dict
            name = source.get("title") or source.get("url") or source.get("name") or "unknown"
            normalized.append(str(name))
        else:
            normalized.append(str(source))
    return normalized


def remaining_budget_ms(
    timeout_budget_ms: Optional[int],
    step_start: float,
) -> Optional[int]:
    """
    Calculate remaining time budget in milliseconds.
    
    Args:
        timeout_budget_ms: Original timeout budget
        step_start: Start time of current step
        
    Returns:
        Remaining budget in ms, or None if unlimited
    """
    if timeout_budget_ms is None:
        return None
    
    elapsed_ms = int((time.time() - step_start) * 1000)
    return max(timeout_budget_ms - elapsed_ms, 500)


def derive_web_timeout_ms(timeout_budget_ms: Optional[int]) -> Optional[int]:
    """
    Derive web search timeout from remaining budget.
    
    Reserves some time for post-processing.
    
    Args:
        timeout_budget_ms: Remaining timeout budget
        
    Returns:
        Web search timeout in ms
    """
    if timeout_budget_ms is None:
        return None
    
    # Reserve 2 seconds for post-processing
    return max(timeout_budget_ms - 2000, 1000)


def kb_top_relevance(vector_results: Dict[str, Any]) -> float:
    """Return the highest relevance score among retrieved KB documents.

    Reranked results are sorted by relevance, but we take ``max`` defensively
    in case ordering changed during post-processing. Falls back to deriving a
    score from ``distances`` (``1 - min_distance``) when ``scores`` are absent.

    Returns 0.0 when there are no documents or scores cannot be parsed, which
    callers treat as "KB has nothing confidently relevant".
    """
    scores = vector_results.get("scores") or []
    if scores:
        try:
            return float(max(scores))
        except (TypeError, ValueError):
            return 0.0
    distances = vector_results.get("distances") or []
    if distances:
        try:
            return 1.0 - float(min(distances))
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def split_into_stream_chunks(text: str, words_per_chunk: int = 5) -> List[str]:
    """Split a finished answer into small chunks for progressive rendering.

    Used to stream already-computed answers (web/hybrid/fallback/cache) as
    several token events instead of one large chunk, so the client paints the
    text progressively. Splitting/rejoining on single spaces is lossless:
    concatenating the returned chunks reproduces ``text`` exactly.
    """
    if not text:
        return []
    parts = text.split(" ")
    chunks: List[str] = []
    for i in range(0, len(parts), words_per_chunk):
        chunk = " ".join(parts[i:i + words_per_chunk])
        if i + words_per_chunk < len(parts):
            chunk += " "  # restore the separator that join() between groups drops
        if chunk:
            chunks.append(chunk)
    return chunks


async def emit_text_as_token_events(
    text: str,
    words_per_chunk: int = 5,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Yield ``{"type": "token", ...}`` events for an already-computed answer.

    Emits the text in small chunks (no artificial delay) and yields control to
    the event loop between chunks so the SSE layer can flush each one, giving a
    progressive-render effect for non-streaming routes.
    """
    for chunk in split_into_stream_chunks(text, words_per_chunk):
        yield {"type": "token", "chunk": chunk}
        await asyncio.sleep(0)


def get_relevance_checker(
    answer_generator: AnswerGeneratorProtocol,
    logger: logging.Logger,
) -> Optional[RelevanceCheckerProtocol]:
    """
    Return the answer_generator if it supports relevance checking (has check_relevance).
    
    Args:
        answer_generator: GeminiClient or similar
        logger: Logger instance
        
    Returns:
        The input answer_generator if it has check_relevance, otherwise None
    """
    if hasattr(answer_generator, "check_relevance"):
        return answer_generator
    
    logger.debug("Answer generator does not support relevance checking")
    return None


def compute_merged_coverage_score(
    total_citations: int,
    kb_citation_count: int,
    web_citation_count: int,
) -> float:
    """
    Compute coverage score for merged KB and web citations.

    Args:
        total_citations: Total number of citations (merged)
        kb_citation_count: Number of KB citations
        web_citation_count: Number of web citations

    Returns:
        Coverage score between 0.0 and 1.0
    """
    if total_citations >= 5:
        return 1.0
    elif total_citations >= 3:
        return 0.8
    elif total_citations >= 1:
        return 0.6
    elif kb_citation_count > 0 or web_citation_count > 0:
        return 0.4
    else:
        return 0.0


def extract_cache_answer(result: Any) -> str:
    """Return the answer string from a cached result dict, or '' if invalid.

    Centralises the defensive ``isinstance`` + ``.get("answer", "")`` pattern
    that was previously duplicated across cache-fallback call sites.
    """
    if isinstance(result, dict):
        return str(result.get("answer", "") or "")
    return ""


async def try_serve_cached_answer(
    answer_generator: Any,
    original_query: str,
    steps: List[Any],
    fallback_reason: str = "No KB results, served from cache",
    logger: Optional[logging.Logger] = None,
) -> Optional[Dict[str, Any]]:
    """Check the query cache and return a cached answer if one is available.

    Used by KB route handlers as a fallback before falling back to web search
    when KB retrieval returns 0 results.  Returns the cached result dict
    (with ``citations`` and ``coverage_score`` defaults applied) on a hit, or
    ``None`` on a miss / empty answer / cache error.

    Args:
        answer_generator: Object implementing ``check_query_cache``.
        original_query: Original user query (un-rewritten).
        steps: List to append an ``AgentStep`` to on a cache hit.
        fallback_reason: Reason text for the recorded step.
        logger: Optional logger; if None, a module-level logger is used.

    Returns:
        Cached result dict on hit, ``None`` on miss.
    """
    log = logger or logging.getLogger(__name__)
    check_cache = getattr(answer_generator, "check_query_cache", None)
    if check_cache is None:
        return None

    try:
        cached_result = await check_cache(original_query)
    except Exception as cache_exc:
        log.debug("Cache check before web fallback failed: %s", cache_exc)
        return None

    if cached_result is None or not isinstance(cached_result, dict):
        return None

    cached_answer = extract_cache_answer(cached_result)
    if not cached_answer:
        return None

    log.info(
        "KB retrieval returned 0 results; serving cached answer "
        "instead of falling back to web search"
    )
    steps.append(_make_fallback_step(fallback_reason))
    # citations must be Optional[CitationResponse] (a dict or None) to satisfy
    # the Response model; a raw list raises a Pydantic ValidationError.
    cached_result.setdefault("citations", None)
    cached_result.setdefault("coverage_score", 1.0)
    return cached_result


def _make_fallback_step(reason: str) -> Any:
    """Create an AgentStep recording a fallback decision.

    Imported lazily to avoid a circular import at module load time.
    """
    from .reasoning_formatter import AgentStep
    return AgentStep(
        name="Fallback Decision",
        status="completed",
        details={"reason": reason},
    )


def extract_source_titles(
    vector_results: Dict[str, Any],
    max_titles: int = 5,
) -> List[str]:
    """Extract deduplicated source document titles from vector results.

    Used to give the LLM relevance checker context about which documents
    the answer was grounded in.

    Args:
        vector_results: Retrieval results with a "metadatas" list.
        max_titles: Maximum number of unique titles to return.

    Returns:
        List of cleaned, unique source display names (may be empty).
    """
    titles: List[str] = []
    for metadata in vector_results.get("metadatas", []) or []:
        if not isinstance(metadata, dict):
            continue
        name = source_name_from_metadata(metadata, fallback="")
        if not name:
            continue
        cleaned = clean_source_display_name(name)
        if cleaned and cleaned not in titles:
            titles.append(cleaned)
            if len(titles) >= max_titles:
                break
    return titles


def extract_source_chunks(
    vector_results: Dict[str, Any],
    max_chunks: int = 10,
    max_chars_per_chunk: int = 1600,
) -> List[str]:
    """Extract the top retrieved source chunk texts from vector results.

    Used as evidence for the retrieval-aware relevance judge. Each chunk is
    prefixed with its source name (when available) and truncated to keep the
    relevance prompt within the model's context budget.

    Args:
        vector_results: Retrieval results with "documents" and "metadatas" lists.
        max_chunks: Maximum number of chunks to return.
        max_chars_per_chunk: Maximum characters per chunk.

    Returns:
        List of formatted source chunk strings (may be empty).
    """
    documents = vector_results.get("documents", []) or []
    metadatas = vector_results.get("metadatas", []) or []
    chunks: List[str] = []
    for i, doc in enumerate(documents[:max_chunks]):
        if not doc:
            continue
        text = str(doc)[:max_chars_per_chunk]
        metadata = metadatas[i] if i < len(metadatas) else {}
        source_name = ""
        if isinstance(metadata, dict):
            source_name = source_name_from_metadata(metadata, fallback="")
            source_name = clean_source_display_name(source_name)
        prefix = f"Source {i + 1}"
        if source_name:
            prefix += f" ({source_name})"
        chunks.append(f"{prefix}:\n{text}")
    return chunks


async def check_answer_relevance(
    validator: Any,
    config: Any,
    query: str,
    answer: str,
    log_tag: str = "KB",
    source_titles: Optional[List[str]] = None,
    source_chunks: Optional[List[str]] = None,
) -> tuple[bool, str]:
    """Run the retrieval-aware LLM relevance check on a generated answer.

    Shared by the sync KB handler, hybrid handler, and streaming non-stream
    fallback. Returns ``(is_irrelevant, reason)``: when ``is_irrelevant`` is
    True the caller should fall back to web. The check is only considered
    conclusive when the validator's confidence is at or above
    ``config.web_supplement_relevance_confidence_threshold``.

    The relevance check can be disabled with ``config.enable_web_supplement_relevance_check``
    without affecting the separate grounding-validation step.

    Args:
        validator: Object implementing ``check_relevance(query, answer)``.
        config: OrchestratorConfig (or compatible) with the confidence
            threshold and enable flags.
        query: Original user query.
        answer: Generated answer text to validate.
        log_tag: Short label for log messages (e.g. "KB", "Hybrid", "Streaming").
        source_titles: Optional titles of the retrieved documents the answer
            was grounded in, passed to the validator for extra context.
        source_chunks: Optional list of retrieved source chunk texts. When
            provided, these are passed to the validator so the judge can verify
            that the answer is supported by the KB.

    Returns:
        ``(True, reason)`` if the answer is irrelevant with high confidence,
        ``(False, "")`` otherwise (including when the validator is missing,
        the check is disabled, returns a non-dict, or raises).
    """
    if not getattr(config, "enable_web_supplement_relevance_check", True):
        logger.debug("Web supplement relevance check disabled by config")
        return False, ""

    if not validator:
        return False, ""

    try:
        kwargs: Dict[str, Any] = {}
        if source_titles:
            kwargs["source_titles"] = source_titles
        if source_chunks:
            kwargs["source_chunks"] = source_chunks

        try:
            relevance_result = await validator.check_relevance(query, answer, **kwargs)
        except TypeError:
            # Validator implementation does not accept source_chunks; try source_titles only.
            kwargs.pop("source_chunks", None)
            try:
                relevance_result = await validator.check_relevance(query, answer, **kwargs)
            except TypeError:
                # Validator implementation does not accept source_titles either.
                kwargs.pop("source_titles", None)
                relevance_result = await validator.check_relevance(query, answer, **kwargs)

        if not isinstance(relevance_result, dict):
            logger.debug(
                "Skipping relevance check (%s): non-dict response type %s",
                log_tag,
                type(relevance_result).__name__,
            )
            return False, ""

        confidence = float(relevance_result.get("confidence", 0.0) or 0.0)
        threshold = float(
            getattr(config, "web_supplement_relevance_confidence_threshold", 0.8)
        )
        is_relevant = bool(relevance_result.get("is_relevant", True))
        reason = relevance_result.get("reason", "Answer not relevant")
        logger.info(
            "%s relevance check: is_relevant=%s confidence=%.2f threshold=%.2f reason=%s",
            log_tag,
            is_relevant,
            confidence,
            threshold,
            reason,
        )
        if not is_relevant and confidence >= threshold:
            logger.info("%s answer failed relevance check: %s", log_tag, reason)
            return True, reason
    except Exception as e:
        logger.warning("Relevance check error (%s): %s", log_tag, e)

    return False, ""
