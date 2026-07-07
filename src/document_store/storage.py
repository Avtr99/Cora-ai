from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Iterable

from fastapi import UploadFile

from ..config import get_settings
from ..db.database import get_connection
from .models import ConversionMode, DocumentJob, DocumentRecord, DocumentStatus, JobStatus

_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

# Extension → expected MIME type prefixes for content validation.
# python-magic is the source of truth; this map only flags obvious mismatches.
_EXPECTED_MIME_PREFIXES: dict[str, tuple[str, ...]] = {
    ".pdf": ("application/pdf",),
    ".md": ("text/plain", "text/markdown"),
    ".txt": ("text/plain",),
    ".csv": ("text/plain", "text/csv", "application/csv"),
    ".json": ("text/plain", "application/json"),
    ".jsonl": ("text/plain", "application/json"),
}
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS document_store_documents (
    id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    conversion_mode TEXT NOT NULL,
    original_path TEXT NOT NULL,
    converted_path TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER,
    tags_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error TEXT,
    title TEXT,
    registry TEXT,
    category TEXT,
    publisher TEXT,
    document_id TEXT,
    version_number TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_document_store_documents_status ON document_store_documents(status);
CREATE INDEX IF NOT EXISTS idx_document_store_documents_extension ON document_store_documents(extension);
CREATE INDEX IF NOT EXISTS idx_document_store_documents_created_at ON document_store_documents(created_at);
CREATE TABLE IF NOT EXISTS document_store_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES document_store_documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_document_store_jobs_document_id ON document_store_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_document_store_jobs_status ON document_store_jobs(status);
"""


def ensure_document_store_tables() -> None:
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


# Statuses that only exist while a background job is actively running.
# If a document is in one of these at startup, the process was interrupted
# (crash/restart) and the job will never resume — flip it to failed.
_INTERRUPTED_STATUSES = ("reading", "converting", "indexing", "deleting")


def recover_interrupted_documents() -> int:
    """Mark documents stuck in an in-flight status as failed.

    Called once at startup. Returns the number of documents recovered.
    Each recovered document gets error="Interrupted by server restart" so
    the UI can surface a clear reason and the user can re-trigger ingestion.

    Also flips any jobs left in 'queued' or 'processing' to 'failed' so the
    document_store_jobs table doesn't accumulate ghost rows that would mislead
    any future job-polling UI or admin query.
    """
    conn = get_connection()
    try:
        placeholders = ",".join("?" for _ in _INTERRUPTED_STATUSES)
        cursor = conn.execute(
            f"""
            UPDATE document_store_documents
            SET status = 'failed',
                error = 'Interrupted by server restart',
                updated_at = CURRENT_TIMESTAMP
            WHERE status IN ({placeholders})
            """,
            tuple(_INTERRUPTED_STATUSES),
        )
        count = cursor.rowcount
        job_cursor = conn.execute(
            """
            UPDATE document_store_jobs
            SET status = 'failed',
                error = 'Interrupted by server restart',
                updated_at = CURRENT_TIMESTAMP
            WHERE status IN ('queued', 'processing')
            """
        )
        if count or job_cursor.rowcount:
            conn.commit()
        return count
    finally:
        conn.close()


def document_root() -> Path:
    settings = get_settings()
    root = Path(settings.DOCUMENT_STORE_ROOT).resolve()
    allowed_dirs = [Path(p).resolve() for p in settings.allowed_document_dirs_resolved]
    if not any(root == allowed or allowed in root.parents for allowed in allowed_dirs):
        raise ValueError("Document store root is outside allowed document directories")
    root.mkdir(parents=True, exist_ok=True)
    for child in ("originals", "converted", "metadata"):
        (root / child).mkdir(parents=True, exist_ok=True)
    return root


def allowed_extensions() -> set[str]:
    settings = get_settings()
    return {
        ext.strip().lower()
        for ext in settings.DOCUMENT_ALLOWED_EXTENSIONS.split(",")
        if ext.strip()
    }


def normalize_tags(raw_tags: Iterable[str] | None) -> list[str]:
    if raw_tags is None:
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for value in raw_tags:
        tag = str(value).strip().lower()
        if not tag or len(tag) > 64 or tag in seen:
            continue
        tags.append(tag)
        seen.add(tag)
    return tags[:20]


def parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return normalize_tags(str(item) for item in parsed)
    except json.JSONDecodeError:
        pass
    return normalize_tags(part for part in raw.split(","))


def safe_original_filename(filename: str | None) -> str:
    fallback = "document"
    cleaned = _SAFE_FILENAME_CHARS.sub("_", (filename or fallback).strip()).strip("._")
    return cleaned or fallback


def _validate_upload_mime(extension: str, first_chunk: bytes, declared_mime: str | None) -> None:
    """Check that the uploaded file's magic bytes match its declared extension.

    ponytail: Uses python-magic if available; on import failure, skips validation
    so a missing libmagic DLL doesn't block uploads. Declared MIME is ignored —
    it is client-controlled and trivially spoofed.
    """
    try:
        import magic
    except Exception:
        return

    detected = magic.from_buffer(first_chunk, mime=True)
    expected = _EXPECTED_MIME_PREFIXES.get(extension)
    if expected and not detected.startswith(expected):
        raise ValueError(
            f"File content ({detected}) does not match extension {extension}"
        )


async def save_upload(file: UploadFile, conversion_mode: ConversionMode, tags: list[str]) -> DocumentRecord:
    ensure_document_store_tables()
    root = document_root()
    filename = safe_original_filename(file.filename)
    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions():
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}")

    settings = get_settings()
    max_bytes = int(settings.DOCUMENT_UPLOAD_MAX_BYTES)

    # Up-front size check when the client provides Content-Length.
    content_length = None
    if file.headers and "content-length" in file.headers:
        try:
            content_length = int(file.headers["content-length"])
        except ValueError:
            content_length = None
    if content_length is not None and content_length > max_bytes:
        raise ValueError(f"File is larger than the configured limit of {max_bytes} bytes")

    doc_id = f"doc_{uuid.uuid4().hex[:16]}"
    stored_filename = f"{doc_id}{extension}"
    original_path = root / "originals" / stored_filename
    converted_path = root / "converted" / f"{doc_id}.md"

    digest = hashlib.sha256()
    size = 0
    first_chunk: bytes | None = None
    try:
        with original_path.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                if first_chunk is None:
                    first_chunk = chunk
                    _validate_upload_mime(extension, first_chunk, file.content_type)
                size += len(chunk)
                if size > max_bytes:
                    handle.close()
                    original_path.unlink(missing_ok=True)
                    raise ValueError(f"File is larger than the configured limit of {max_bytes} bytes")
                digest.update(chunk)
                handle.write(chunk)
    finally:
        await file.close()

    sha256_hex = digest.hexdigest()
    existing = find_by_sha256(sha256_hex)
    if existing is not None:
        original_path.unlink(missing_ok=True)
        raise FileExistsError(
            f"A document with the same content already exists: {existing.original_filename}"
        )

    record = DocumentRecord(
        id=doc_id,
        original_filename=filename,
        stored_filename=stored_filename,
        mime_type=file.content_type or "application/octet-stream",
        extension=extension,
        size_bytes=size,
        sha256=sha256_hex,
        status="queued",
        conversion_mode=conversion_mode,
        original_path=str(original_path),
        converted_path=str(converted_path),
        tags=tags,
    )
    insert_document(record)
    write_metadata_file(record)
    return record


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
    status: DocumentStatus | None = None,
    converted_path: str | None = None,
    chunk_count: int | None = None,
    page_count: int | None = None,
    warnings: list[str] | None = None,
    error: str | None = None,
    title: str | None = None,
    registry: str | None = None,
    category: str | None = None,
    publisher: str | None = None,
    document_id: str | None = None,
    version_number: str | None = None,
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
    # states (reading/converting/indexing) — writing the JSON each time is
    # pure write amplification. The sidecar is a debugging aid; terminal
    # states (indexed/failed/deleted) are the ones a human would inspect.
    if status in ("indexed", "failed", "deleted"):
        write_metadata_file(record)
    return record


def get_document(document_id: str) -> DocumentRecord | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM document_store_documents WHERE id = ? AND status != 'deleted'",
            (document_id,),
        ).fetchone()
        return _row_to_record(row) if row else None
    finally:
        conn.close()


def get_document_including_deleted(document_id: str) -> DocumentRecord | None:
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


def find_by_sha256(sha256: str) -> DocumentRecord | None:
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


def list_documents(status: str | None = None, extension: str | None = None, tag: str | None = None) -> list[DocumentRecord]:
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


def create_job(document_id: str, action: str, message: str | None = None) -> DocumentJob:
    job = DocumentJob(
        id=f"job_{uuid.uuid4().hex[:16]}",
        document_id=document_id,
        action=action,
        status="queued",
        message=message,
    )
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO document_store_jobs (id, document_id, action, status, message) VALUES (?, ?, ?, ?, ?)",
            (job.id, job.document_id, job.action, job.status, job.message),
        )
        conn.commit()
    finally:
        conn.close()
    return job


def update_job(job_id: str, status: JobStatus, message: str | None = None, error: str | None = None) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE document_store_jobs
            SET status = ?, message = ?, error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, message, error, job_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_job(job_id: str) -> DocumentJob | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM document_store_jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return DocumentJob(
            id=row["id"],
            document_id=row["document_id"],
            action=row["action"],
            status=row["status"],
            message=row["message"],
            error=row["error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    finally:
        conn.close()


def read_markdown(record: DocumentRecord) -> str:
    if not record.converted_path:
        raise FileNotFoundError("Converted text is not ready")
    path = Path(record.converted_path)
    if not path.exists():
        raise FileNotFoundError("Converted text is not available")
    return path.read_text(encoding="utf-8")


def write_metadata_file(record: DocumentRecord) -> None:
    root = document_root()
    metadata_path = root / "metadata" / f"{record.id}.json"
    metadata_path.write_text(json.dumps(record.to_api(), indent=2), encoding="utf-8")


def remove_document_files(record: DocumentRecord) -> None:
    for value in (record.original_path, record.converted_path):
        if value:
            Path(value).unlink(missing_ok=True)
    root = document_root()
    (root / "metadata" / f"{record.id}.json").unlink(missing_ok=True)
