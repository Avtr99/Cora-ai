"""Document record CRUD and cross-process document locking.

All SQLite access for the ``document_store_documents`` table lives here:
row mapping, insert, partial update, single-record lookups (with and without
soft-deleted rows), SHA-256 dedup lookup, filtered listing, and the
``processing_job_id``-based lock used to serialize concurrent jobs on the
same document.
"""

from __future__ import annotations

import json
from typing import Optional

from ..db.database import get_connection
from .files import write_metadata_file
from .models import DocumentRecord, DocumentStatus


def _row_to_record(row) -> DocumentRecord:
    # Use .keys() to handle pre-migration databases that lack the new columns.
    keys = set(row.keys())
    return DocumentRecord(
        id=row["id"],
        original_filename=row["original_filename"],
        stored_filename=row["stored_filename"],
        mime_type=row["mime_type"],
        extension=row["extension"],
        size_bytes=row["size_bytes"],
        sha256=row["sha256"],
        status=row["status"],
        conversion_mode=row["conversion_mode"],
        original_path=row["original_path"],
        converted_path=row["converted_path"],
        chunk_count=row["chunk_count"],
        page_count=row["page_count"],
        tags=json.loads(row["tags_json"] or "[]"),
        warnings=json.loads(row["warnings_json"] or "[]"),
        error=row["error"],
        title=row["title"] if "title" in keys else None,
        registry=row["registry"] if "registry" in keys else None,
        category=row["category"] if "category" in keys else None,
        publisher=row["publisher"] if "publisher" in keys else None,
        document_id=row["document_id"] if "document_id" in keys else None,
        version_number=row["version_number"] if "version_number" in keys else None,
        processing_job_id=row["processing_job_id"] if "processing_job_id" in keys else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def insert_document(record: DocumentRecord) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO document_store_documents (
                id, original_filename, stored_filename, mime_type, extension, size_bytes,
                sha256, status, conversion_mode, original_path, converted_path, chunk_count,
                page_count, tags_json, warnings_json, error,
                title, registry, category, publisher, document_id, version_number
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.original_filename,
                record.stored_filename,
                record.mime_type,
                record.extension,
                record.size_bytes,
                record.sha256,
                record.status,
                record.conversion_mode,
                record.original_path,
                record.converted_path,
                record.chunk_count,
                record.page_count,
                json.dumps(record.tags),
                json.dumps(record.warnings),
                record.error,
                record.title,
                record.registry,
                record.category,
                record.publisher,
                record.document_id,
                record.version_number,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def update_document(
    record_id: str,
    *,
    status: Optional[DocumentStatus] = None,
    converted_path: Optional[str] = None,
    chunk_count: Optional[int] = None,
    page_count: Optional[int] = None,
    warnings: Optional[list[str]] = None,
    error: Optional[str] = None,
    title: Optional[str] = None,
    registry: Optional[str] = None,
    category: Optional[str] = None,
    publisher: Optional[str] = None,
    document_id: Optional[str] = None,
    version_number: Optional[str] = None,
) -> DocumentRecord:
    """Update a document record.

    ``record_id`` is the primary key (``DocumentRecord.id``). The ``document_id``
    keyword argument matches the VCM registry document ID field name.
    """
    fields: list[str] = []
    values: list[object] = []
    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if converted_path is not None:
        fields.append("converted_path = ?")
        values.append(converted_path)
    if chunk_count is not None:
        fields.append("chunk_count = ?")
        values.append(chunk_count)
    if page_count is not None:
        fields.append("page_count = ?")
        values.append(page_count)
    if warnings is not None:
        fields.append("warnings_json = ?")
        values.append(json.dumps(warnings))
    # Update the error column unless we are transitioning to "failed" without an
    # explicit error message (in that one case, leave the existing error untouched).
    # Forward-looking guard: no current caller does status="failed" without an
    # error, but this prevents a future caller from silently wiping a useful
    # error string when flipping a doc to failed for a non-conversion reason.
    if not (status == "failed" and error is None):
        fields.append("error = ?")
        values.append(error)
    if title is not None:
        fields.append("title = ?")
        values.append(title)
    if registry is not None:
        fields.append("registry = ?")
        values.append(registry)
    if category is not None:
        fields.append("category = ?")
        values.append(category)
    if publisher is not None:
        fields.append("publisher = ?")
        values.append(publisher)
    if document_id is not None:
        fields.append("document_id = ?")
        values.append(document_id)
    if version_number is not None:
        fields.append("version_number = ?")
        values.append(version_number)
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(record_id)

    conn = get_connection()
    try:
        conn.execute(
            f"UPDATE document_store_documents SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        conn.commit()
    finally:
        conn.close()
    record = get_document(record_id)
    if record is None:
        # If the document was just marked as deleted, read it back from the
        # database including soft-deleted records so the update succeeds.
        record = get_document_including_deleted(record_id)
        if record is None or record.status != "deleted":
            raise ValueError("Document not found")
    # ponytail: only write the metadata sidecar on terminal statuses.
    # During a single ingest update_document is called 4-5 times for transient
    # states (reading/converting/indexing) -- writing the JSON each time is
    # pure write amplification. The sidecar is a debugging aid; terminal
    # states (indexed/failed/deleted) are the ones a human would inspect.
    if status in ("indexed", "failed", "deleted"):
        write_metadata_file(record)
    return record


def try_acquire_document_lock(document_id: str, job_id: str) -> bool:
    """Set ``processing_job_id`` to ``job_id`` if it is currently NULL.

    Returns ``True`` if the lock was acquired, ``False`` if another job already
    holds it. The caller is responsible for retrying or backing off.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "UPDATE document_store_documents SET processing_job_id = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND processing_job_id IS NULL",
            (job_id, document_id),
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def release_document_lock(document_id: str, job_id: str) -> None:
    """Release the document lock if it is still held by ``job_id``."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE document_store_documents SET processing_job_id = NULL, "
            "updated_at = CURRENT_TIMESTAMP WHERE id = ? AND processing_job_id = ?",
            (document_id, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_document(document_id: str) -> Optional[DocumentRecord]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM document_store_documents WHERE id = ? AND status != 'deleted'",
            (document_id,),
        ).fetchone()
        return _row_to_record(row) if row else None
    finally:
        conn.close()


def get_document_including_deleted(document_id: str) -> Optional[DocumentRecord]:
    """Return a document record regardless of status, or None if it does not exist."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM document_store_documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        return _row_to_record(row) if row else None
    finally:
        conn.close()


def find_by_sha256(sha256: str) -> Optional[DocumentRecord]:
    """Return the first non-deleted document with the given SHA-256 hash, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM document_store_documents WHERE sha256 = ? AND status != 'deleted' LIMIT 1",
            (sha256,),
        ).fetchone()
        return _row_to_record(row) if row else None
    finally:
        conn.close()


def list_documents(status: Optional[str] = None, extension: Optional[str] = None, tag: Optional[str] = None) -> list[DocumentRecord]:
    clauses = ["status != 'deleted'"]
    values: list[object] = []
    if status:
        clauses.append("status = ?")
        values.append(status)
    if extension:
        clauses.append("extension = ?")
        values.append(extension.lower())
    conn = get_connection()
    try:
        rows = conn.execute(
            f"SELECT * FROM document_store_documents WHERE {' AND '.join(clauses)} ORDER BY datetime(created_at) DESC",
            tuple(values),
        ).fetchall()
        records = [_row_to_record(row) for row in rows]
        if tag:
            normalized = tag.strip().lower()
            records = [record for record in records if normalized in record.tags]
        return records
    finally:
        conn.close()
