from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from loguru import logger
from qdrant_client import QdrantClient, models

from ..config import get_settings
from ..embeddings import create_embeddings
from ..utils.cache import query_cache
from ..db.sqlite_cache import get_sqlite_cache
from .models import DocumentRecord
from .storage import read_markdown, update_document
from .title_utils import _extract_first_heading


def chunk_markdown(record: DocumentRecord) -> list[Document]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    text = read_markdown(record)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
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


async def index_document(record: DocumentRecord) -> int:
    update_document(record.id, status="indexing")
    chunks = chunk_markdown(record)
    await asyncio.to_thread(_replace_document_chunks, record, chunks)
    await invalidate_document_caches()
    update_document(record.id, status="indexed", chunk_count=len(chunks), error=None)
    return len(chunks)


async def delete_document_chunks(document_id: str) -> None:
    await asyncio.to_thread(_delete_document_chunks_sync, document_id)
    await invalidate_document_caches()


async def invalidate_document_caches() -> None:
    await query_cache.clear()
    cache = get_sqlite_cache()
    await cache.clear()


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
    # rewriter's filters are actually usable. Must stay in sync with the
    # metadata dict in chunk_markdown().
    for field in (
        "metadata.doc_store_id",
        "metadata.original_filename",
        "metadata.file_type",
        "metadata.tags",
        "metadata.registry",
        "metadata.publisher",
        "metadata.document_id",
        "metadata.title",
        "metadata.version_number",
        "metadata.registry_document_id",
        "metadata.methodology_codes",
    ):
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema="keyword",
            )
        except Exception as exc:
            # Index already exists or creation is unsupported — safe to skip.
            logger.debug("Payload index not created for %s: %s", field, exc)


def _replace_document_chunks(record: DocumentRecord, chunks: list[Document]) -> None:
    client = _qdrant_client()
    _ensure_collection(client)
    _delete_document_chunks_sync(record.id, client=client)
    settings = get_settings()
    vector_store = QdrantVectorStore(
        client=client,
        collection_name=settings.QDRANT_COLLECTION_NAME,
        embedding=create_embeddings(),
        validate_collection_config=False,
    )
    ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"{record.id}:{index}")) for index in range(len(chunks))]
    if chunks:
        vector_store.add_documents(chunks, ids=ids)


def _delete_document_chunks_sync(document_id: str, client: QdrantClient | None = None) -> None:
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
