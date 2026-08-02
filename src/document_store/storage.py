"""Backwards-compatible re-export facade for the document store persistence layer.

The implementation has been split into cohesive submodules:

- :mod:`.schema`     -- DB schema, infrastructure constants, document-root resolution
- :mod:`.repository` -- document record CRUD and cross-process document locking
- :mod:`.jobs_repo`  -- job record CRUD and atomic worker job claiming
- :mod:`.recovery`   -- crash recovery and stale-lock cleanup
- :mod:`.uploads`    -- upload saving, MIME validation, tag/filename helpers
- :mod:`.files`      -- converted-markdown and metadata-sidecar filesystem I/O

This module re-exports every public name that previously lived here so all
existing ``from src.document_store.storage import X`` import sites (jobs,
worker, routes, lifespan, converter, indexer, tests) keep working unchanged.
"""

from __future__ import annotations

from .files import read_markdown, remove_document_files, write_metadata_file
from .jobs_repo import claim_next_job, create_job, get_job, update_job
from .recovery import recover_interrupted_documents
from .repository import (
    find_by_sha256,
    get_document,
    get_document_including_deleted,
    insert_document,
    list_documents,
    release_document_lock,
    try_acquire_document_lock,
    update_document,
)
from .schema import (
    _INTERRUPTED_STATUSES,
    _SAFE_FILENAME_CHARS,
    allowed_extensions,
    document_root,
    ensure_document_store_tables,
)
from .uploads import (
    _EXPECTED_MIME_PREFIXES,
    _validate_upload_mime,
    normalize_tags,
    parse_tags,
    safe_original_filename,
    save_upload,
)

__all__ = [
    # schema
    "ensure_document_store_tables",
    "document_root",
    "allowed_extensions",
    "_INTERRUPTED_STATUSES",
    "_SAFE_FILENAME_CHARS",
    "_EXPECTED_MIME_PREFIXES",
    # repository
    "insert_document",
    "update_document",
    "get_document",
    "get_document_including_deleted",
    "find_by_sha256",
    "list_documents",
    "try_acquire_document_lock",
    "release_document_lock",
    # jobs_repo
    "create_job",
    "update_job",
    "get_job",
    "claim_next_job",
    # recovery
    "recover_interrupted_documents",
    # uploads
    "save_upload",
    "safe_original_filename",
    "normalize_tags",
    "parse_tags",
    "_validate_upload_mime",
    # files
    "read_markdown",
    "write_metadata_file",
    "remove_document_files",
]
