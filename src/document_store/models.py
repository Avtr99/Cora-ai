from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

DocumentStatus = Literal[
    "queued",
    "reading",
    "converting",
    "indexing",
    "indexed",
    "needs_review",
    "failed",
    "deleting",
    "deleted",
]
ConversionMode = Literal["standard", "llm_api"]
JobStatus = Literal["queued", "processing", "completed", "failed"]


@dataclass
class DocumentRecord:
    id: str
    original_filename: str
    stored_filename: str
    mime_type: str
    extension: str
    size_bytes: int
    sha256: str
    status: DocumentStatus
    conversion_mode: ConversionMode
    original_path: str
    converted_path: str | None = None
    chunk_count: int = 0
    page_count: int | None = None
    tags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    # VCM metadata extracted once during conversion and persisted.
    # Read by the indexer (chunk metadata) and the RAG citation pipeline.
    title: str | None = None
    registry: str | None = None
    publisher: str | None = None
    document_id: str | None = None
    version_number: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_api(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "status": self.status,
            "conversion_mode": self.conversion_mode,
            "original_path": self.original_path,
            "converted_path": self.converted_path,
            "chunk_count": self.chunk_count,
            "page_count": self.page_count,
            "tags": self.tags,
            "warnings": self.warnings,
            "error": self.error,
            "title": self.title,
            "registry": self.registry,
            "publisher": self.publisher,
            "document_id": self.document_id,
            "version_number": self.version_number,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class DocumentJob:
    id: str
    document_id: str
    action: str
    status: JobStatus
    message: str | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def to_api(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "action": self.action,
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
