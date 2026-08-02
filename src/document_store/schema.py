"""Database schema, infrastructure constants, and document-store path helpers.

These are the lowest-level concerns: table creation, the magic-byte/MIME map,
interrupted-status list, and the resolved document-store root directory. Other
submodules (``files``, ``repository``, ``uploads``) depend on this module, so
it must not import any of them (avoids circular imports).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..config import get_settings
from ..db.database import get_connection

# Extension -> expected MIME type prefixes for content validation.
# python-magic is the source of truth; this map only flags obvious mismatches.
_EXPECTED_MIME_PREFIXES: dict[str, tuple[str, ...]] = {
    ".pdf": ("application/pdf",),
    ".md": ("text/plain", "text/markdown"),
    ".txt": ("text/plain",),
    ".csv": ("text/plain", "text/csv", "application/csv"),
    ".json": ("text/plain", "application/json"),
    ".jsonl": ("text/plain", "application/json"),
}

_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")

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
    processing_job_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_document_store_documents_status ON document_store_documents(status);
CREATE INDEX IF NOT EXISTS idx_document_store_documents_processing_job_id ON document_store_documents(processing_job_id);
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
# (crash/restart) and the job will never resume -- flip it to failed.
_INTERRUPTED_STATUSES = ("reading", "converting", "indexing", "deleting")


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
