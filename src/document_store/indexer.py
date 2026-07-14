from __future__ import annotations

from typing import Optional

import asyncio
import re
import threading
import time
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from loguru import logger
from qdrant_client import QdrantClient, models

from ..config import get_settings
from ..embeddings import create_embeddings
from ..db.sqlite_cache import get_sqlite_cache
from .logging_utils import _log_ingestion_stage
from .models import DocumentRecord
from .storage import read_markdown, update_document
from .title_utils import _extract_first_heading

# Payload field indexes created on the dense collection.
# Must stay in sync with the metadata dict built in chunk_markdown() so the
# query rewriter's filters are usable on the collection.
_PAYLOAD_INDEX_FIELDS = (
    "metadata.doc_store_id",
    "metadata.original_filename",
    "metadata.file_type",
    "metadata.tags",
    "metadata.registry",
    "metadata.category",
    "metadata.publisher",
    "metadata.document_id",
    "metadata.title",
    "metadata.version_number",
    "metadata.registry_document_id",
    "metadata.methodology_codes",
)

# Docling's standard-mode Markdown serializer emits ``<!-- image -->`` for every
# detected image region. These placeholders carry zero retrieval signal, waste
# embedding budget, and produce 14-char garbage chunks. llm_api mode, by
# contrast, sends the page image to an LLM that writes a real text description —
# so we must NOT strip placeholders from llm_api-converted documents.
_IMAGE_PLACEHOLDER_RE = re.compile(r"<!--\s*image\s*-->\s*")

# Debounce cache invalidation during ingestion bursts. A single ``DELETE`` clears
# the whole backend_cache table, so repeated calls from many documents hitting
# the same burst are coalesced into one call after the delay expires.
# Trade-off: the invalidation is asynchronous, so for ~0.7s after a document is
# marked "completed" the query cache may still return stale results. This is
# acceptable for the ingestion backlog use case; the delay is a fixed module
# constant, not a runtime setting.
_CACHE_INVALIDATION_DEBOUNCE_SECONDS = 0.7

_invalidation_task: Optional[asyncio.Task] = None
_invalidation_lock = asyncio.Lock()

# Reuse the Qdrant vector store and embeddings client across indexing calls to
# avoid connection churn to Qdrant and the embedding provider (e.g., VoyageAI).
# Initialized lazily on first use and protected by double-checked locking.
_vector_store_singleton: Optional[QdrantVectorStore] = None
_vector_store_lock = threading.Lock()

def chunk_markdown(record: DocumentRecord) -> list[Document]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text = read_markdown(record)
    # Strip Docling's ``<!-- image -->`` placeholders from standard-mode
    # conversions. They carry no retrieval signal and produce garbage chunks.
    # llm_api mode writes real image descriptions — keep those.
    if record.conversion_mode == "standard":
        text = _IMAGE_PLACEHOLDER_RE.sub("", text)
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.CHUNK_SIZE,
        chunk_overlap=settings.CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    # Read the title and VCM metadata from the record (single source of truth,
    # extracted once during conversion and persisted). Fall back to the first
    # heading in the markdown if the record has no title (e.g. pre-migration).
    title = record.title or _extract_first_heading(text) or Path(record.original_filename).stem
    # Derive methodology_codes from the registry document ID. Verra methodology
    # IDs (VM0047, ACM0003, etc.) are the canonical "methodology_codes" the
    # query rewriter filters on. For non-methodology docs this will be None.
    methodology_codes = None
    if record.document_id:
        doc_id_upper = record.document_id.upper()
        if doc_id_upper.startswith(("VM", "ACM", "AM", "AR-", "AMS")):
            methodology_codes = record.document_id
    base_doc = Document(
        page_content=text,
        metadata={
            "source": record.original_filename,
            "doc_store_id": record.id,
            "original_filename": record.original_filename,
            "file_type": record.extension.lstrip("."),
            "tags": record.tags,
            # document_id = the VCM registry document ID (e.g. "VM0047"),
            # matching what the query rewriter extracts. The internal doc
            # store ID is in doc_store_id above.
            "document_id": record.document_id,
            "title": title,
            "registry": record.registry,
            "category": record.category,
            "publisher": record.publisher,
            "registry_document_id": record.document_id,
            "version_number": record.version_number,
            "methodology_codes": methodology_codes,
        },
    )
    chunks = splitter.split_documents([base_doc])
    for index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = index
        chunk.metadata["source_chunk_index"] = index
    return chunks


async def index_document(record: DocumentRecord, job_id: Optional[str] = None) -> int:
    update_document(record.id, status="indexing")
    start = time.perf_counter()
    chunks = chunk_markdown(record)
    _log_ingestion_stage("indexer", "chunking", record.id, job_id, time.perf_counter() - start, len(chunks))

    await asyncio.to_thread(_replace_document_chunks, record, chunks, job_id)

    start = time.perf_counter()
    await schedule_cache_invalidation()
    _log_ingestion_stage("indexer", "cache_invalidation", record.id, job_id, time.perf_counter() - start)

    update_document(record.id, status="indexed", chunk_count=len(chunks), error=None)
    return len(chunks)


async def delete_document_chunks(document_id: str) -> None:
    await asyncio.to_thread(_delete_document_chunks_sync, document_id)
    await schedule_cache_invalidation()


async def invalidate_document_caches() -> None:
    """Clear all cached query results, routing decisions, and rewrites.

    A single ``clear()`` with no handler_type removes every row from
    backend_cache (query, route, rewrite, etc.) — no need to clear
    individual handler types separately.
    """
    cache = await get_sqlite_cache()
    await cache.clear()


async def schedule_cache_invalidation() -> None:
    """Schedule a debounced cache invalidation.

    Multiple calls in rapid succession reset the timer and collapse into a
    single ``invalidate_document_caches()`` call after the debounce delay.
    """
    global _invalidation_task
    async with _invalidation_lock:
        if _invalidation_task is not None:
            _invalidation_task.cancel()
        _invalidation_task = asyncio.create_task(_run_debounced_invalidation())


async def _run_debounced_invalidation() -> None:
    """Wait for the debounce delay, then clear caches."""
    try:
        await asyncio.sleep(_CACHE_INVALIDATION_DEBOUNCE_SECONDS)
        await invalidate_document_caches()
    except asyncio.CancelledError:
        return
    except Exception:
        logger.exception("Debounced cache invalidation failed")
    finally:
        global _invalidation_task
        async with _invalidation_lock:
            current = asyncio.current_task()
            if _invalidation_task is current:
                _invalidation_task = None


def _qdrant_client() -> QdrantClient:
    settings = get_settings()
    if not settings.QDRANT_URL:
        raise ValueError("QDRANT_URL is required")
    return QdrantClient(
        url=settings.QDRANT_URL,
        timeout=settings.QDRANT_TIMEOUT,
    )


def _ensure_collection(client: QdrantClient) -> None:
    settings = get_settings()
    collection_name = settings.QDRANT_COLLECTION_NAME
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=settings.EMBEDDING_DIM,
                distance=models.Distance.COSINE,
            ),
        )
    # Index every metadata field the indexer writes to payloads so the query
    # rewriter's filters are actually usable. _PAYLOAD_INDEX_FIELDS is the
    # single source of truth shared with chunk_markdown().
    for field in _PAYLOAD_INDEX_FIELDS:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema="keyword",
            )
        except Exception as exc:
            # Index already exists or creation is unsupported — safe to skip.
            logger.debug("Payload index not created for {}: {}", field, exc)


def _get_vector_store() -> QdrantVectorStore:
    """Return the shared QdrantVectorStore instance, creating it lazily.

    The embeddings client and Qdrant client are created once per process and
    reused across all indexing calls. Settings changes after startup do not
    recreate the singleton; restart the process to pick up new provider/url
    configuration.
    """
    global _vector_store_singleton
    if _vector_store_singleton is not None:
        return _vector_store_singleton
    with _vector_store_lock:
        if _vector_store_singleton is not None:
            return _vector_store_singleton
        settings = get_settings()
        client = _qdrant_client()
        _ensure_collection(client)
        embeddings = create_embeddings()
        _vector_store_singleton = QdrantVectorStore(
            client=client,
            collection_name=settings.QDRANT_COLLECTION_NAME,
            embedding=embeddings,
            validate_collection_config=False,
        )
        return _vector_store_singleton


def _replace_document_chunks(
    record: DocumentRecord, chunks: list[Document], job_id: Optional[str] = None
) -> None:
    vector_store = _get_vector_store()
    _delete_document_chunks_sync(record.id, client=vector_store.client)
    if not chunks:
        return

    ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{record.id}:{index}")) for index in range(len(chunks))]
    texts = [chunk.page_content for chunk in chunks]
    metadatas = [chunk.metadata for chunk in chunks]

    start = time.perf_counter()
    settings = get_settings()
    batch_size = settings.EMBEDDING_BATCH_SIZE
    batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]

    try:
        if len(batches) == 1:
            vectors = vector_store.embeddings.embed_documents(batches[0])
        else:
            # Embed batches sequentially in the same thread. Embedding clients
            # are often not thread-safe (they may reuse a single HTTP client),
            # so avoid ThreadPoolExecutor here. index_document already runs
            # this function inside asyncio.to_thread, so the event loop is not
            # blocked.
            vectors = []
            for batch in batches:
                vectors.extend(vector_store.embeddings.embed_documents(batch))
    except Exception as e:
        logger.exception(
            "Embedding failed for document {}: {}", record.id, e
        )
        raise
    _log_ingestion_stage(
        "indexer", "embedding", record.id, job_id, time.perf_counter() - start, len(chunks)
    )

    points = [
        models.PointStruct(
            id=ids[i],
            vector=vectors[i],
            payload={
                vector_store.content_payload_key: texts[i],
                vector_store.metadata_payload_key: metadatas[i],
            },
        )
        for i in range(len(chunks))
    ]

    start = time.perf_counter()
    upsert_batch_size = settings.QDRANT_UPSERT_BATCH_SIZE
    for i in range(0, len(points), upsert_batch_size):
        try:
            vector_store.client.upsert(
                collection_name=vector_store.collection_name,
                points=points[i : i + upsert_batch_size],
                wait=True,
            )
        except Exception as e:
            logger.exception(
                "Qdrant upsert failed for document {}: {}", record.id, e
            )
            raise
    _log_ingestion_stage("indexer", "upsert", record.id, job_id, time.perf_counter() - start, len(chunks))


def _delete_document_chunks_sync(document_id: str, client: Optional[QdrantClient] = None) -> None:
    qdrant_client = client or _qdrant_client()
    settings = get_settings()
    if not qdrant_client.collection_exists(settings.QDRANT_COLLECTION_NAME):
        return
    qdrant_client.delete(
        collection_name=settings.QDRANT_COLLECTION_NAME,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="metadata.doc_store_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )
        ),
        wait=True,
    )
