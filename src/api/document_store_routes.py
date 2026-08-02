from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from loguru import logger

from ..config import get_settings
from ..document_store.jobs import (
    delete_document_job,
    process_document_job,
    raise_if_conversion_unavailable,
    reindex_document_job,
    schedule_ingestion_job,
)
from ..document_store.converter import get_conversion_capabilities
from ..document_store.storage import (
    create_job,
    get_document,
    get_job,
    list_documents,
    parse_tags,
    read_markdown,
    safe_original_filename,
    save_upload,
    update_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


class DocumentResponse(BaseModel):
    id: str
    original_filename: str
    mime_type: str
    extension: str
    size_bytes: int
    sha256: str
    status: str
    conversion_mode: str
    original_path: str
    converted_path: str | None = None
    chunk_count: int = 0
    page_count: int | None = None
    tags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class DocumentUploadResponse(BaseModel):
    document: DocumentResponse
    job_id: str
    warning: str | None = Field(
        None,
        description="Present when the upload was accepted but processing may not proceed (e.g. no ingest-worker running).",
    )


class DocumentJobResponse(BaseModel):
    id: str
    document_id: str
    action: str
    status: str
    message: str | None = None
    error: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class MarkdownResponse(BaseModel):
    document_id: str
    markdown: str


class DocumentActionResponse(BaseModel):
    document: DocumentResponse
    job_id: str


class BulkActionResponse(BaseModel):
    queued: int = Field(description="Number of documents queued for processing")
    job_ids: list[str] = Field(default_factory=list)


class ConversionCapabilitiesResponse(BaseModel):
    standard: dict = Field(description="Standard mode availability (Docling classical, non-VLM pipeline)")
    llm_api: dict = Field(description="AI service mode availability, provider, and model")
    upload_limits: dict = Field(
        default_factory=dict,
        description="Server-side upload constraints: allowed_extensions and max_bytes",
    )
    worker_status: dict = Field(
        default_factory=dict,
        description=(
            "Ingestion worker runtime status. Contains 'dispatch_mode' "
            "(worker|in_process) and 'alive' (bool). When dispatch_mode is "
            "'worker' and alive is False, uploads will be accepted and queued "
            "but will not be processed until the ingest-worker is started."
        ),
    )


@router.get("/conversion-info", response_model=ConversionCapabilitiesResponse)
async def get_conversion_info():
    """Return availability and resolved provider/model for each conversion mode,
    plus the ingest-worker runtime status so the frontend can warn the user
    *before* uploading when the worker is down in worker-dispatch mode."""
    capabilities = get_conversion_capabilities()
    dispatch_mode = getattr(get_settings(), "INGESTION_DISPATCH", "in_process")
    if dispatch_mode == "worker":
        from ..document_store.worker import is_worker_alive

        alive = is_worker_alive()
    else:
        # In-process: the API process itself handles ingestion, so it is
        # trivially alive if this endpoint is responding.
        alive = True
    capabilities["worker_status"] = {
        "dispatch_mode": dispatch_mode,
        "alive": alive,
    }
    return capabilities


@router.get("", response_model=DocumentListResponse)
async def get_documents(
    status: str | None = None,
    extension: str | None = None,
    tag: str | None = None,
):
    records = list_documents(status=status, extension=extension, tag=tag)
    return {"documents": [record.to_api() for record in records]}


@router.post("", response_model=DocumentUploadResponse, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tags: str | None = Form(None),
    conversion_mode: Literal["standard", "llm_api"] = Form("standard"),
):
    try:
        # Fail fast before writing the file if this container cannot handle a
        # standard PDF in in_process mode. Prevents an orphaned record/file.
        original_name = safe_original_filename(file.filename)
        raise_if_conversion_unavailable(
            conversion_mode, Path(original_name).suffix.lower()
        )

        record = await save_upload(file, conversion_mode, parse_tags(tags))
        job = create_job(record.id, "process", "Document queued")
        schedule_ingestion_job(background_tasks, process_document_job, record.id, job.id)
        response: dict = {"document": record.to_api(), "job_id": job.id}
        # In worker-dispatch mode, warn if no ingest-worker is running so the
        # user knows the upload will sit in 'queued' indefinitely.
        dispatch_mode = getattr(get_settings(), "INGESTION_DISPATCH", "in_process")
        if dispatch_mode == "worker":
            from ..document_store.worker import is_worker_alive
            if not is_worker_alive():
                response["warning"] = (
                    "Your file was saved but won't be parsed into the knowledge "
                    "base yet. The background parser that reads PDFs is not "
                    "running. Start it from your terminal with: "
                    "docker compose up -d ingest-worker"
                )
        return response
    except HTTPException:
        raise
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        error_id = str(uuid.uuid4())[:8]
        logger.exception("Document upload failed [error_id={}]", error_id)
        raise HTTPException(status_code=500, detail=f"Document upload failed (error_id: {error_id})") from exc


@router.post("/reindex-all", response_model=BulkActionResponse, status_code=202)
async def reindex_all_documents(background_tasks: BackgroundTasks):
    """Queue reindex jobs for all non-deleted documents."""
    records = list_documents()
    if not records:
        raise HTTPException(status_code=400, detail="No documents to reindex")
    job_ids: list[str] = []
    for record in records:
        job = create_job(record.id, "reindex", "Document refresh queued")
        schedule_ingestion_job(background_tasks, reindex_document_job, record.id, job.id)
        job_ids.append(job.id)
    logger.info("Reindex-all queued {} documents", len(records))
    return {"queued": len(records), "job_ids": job_ids}


@router.delete("", response_model=BulkActionResponse, status_code=202)
async def clear_all_documents(background_tasks: BackgroundTasks):
    """Queue deletion jobs for all non-deleted documents."""
    records = list_documents()
    if not records:
        raise HTTPException(status_code=400, detail="No documents to delete")
    job_ids: list[str] = []
    for record in records:
        job = create_job(record.id, "delete", "Document deletion queued")
        schedule_ingestion_job(background_tasks, delete_document_job, record.id, job.id)
        job_ids.append(job.id)
    logger.info("Clear-all queued {} documents for deletion", len(records))
    return {"queued": len(records), "job_ids": job_ids}


@router.get("/jobs/{job_id}", response_model=DocumentJobResponse)
async def get_document_job(job_id: str):
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Document job not found")
    return job.to_api()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document_detail(document_id: str):
    record = get_document(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return record.to_api()


@router.get("/{document_id}/markdown", response_model=MarkdownResponse)
async def get_document_markdown(document_id: str):
    record = get_document(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        return {"document_id": document_id, "markdown": read_markdown(record)}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{document_id}/reindex", response_model=DocumentActionResponse, status_code=202)
async def reindex_document(document_id: str, background_tasks: BackgroundTasks):
    record = get_document(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # Clear any prior error so the UI stops showing the old failure message.
    # Don't set a status here — the document stays at its current status
    # (e.g. 'failed' or 'indexed') until the worker picks up the reindex job
    # and the handler transitions it to 'converting'/'indexing'. Setting
    # 'queued' here would leave the document stuck if the worker crashed
    # before the handler ran, because 'queued' is not in
    # _INTERRUPTED_STATUSES and would never be recovered.
    record = update_document(document_id, error=None)
    job = create_job(record.id, "reindex", "Document refresh queued")
    schedule_ingestion_job(background_tasks, reindex_document_job, record.id, job.id)
    return {"document": record.to_api(), "job_id": job.id}


@router.delete("/{document_id}", response_model=DocumentActionResponse, status_code=202)
async def delete_document(document_id: str, background_tasks: BackgroundTasks):
    record = get_document(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    # Mark as deleting immediately so the user sees visual feedback and the
    # frontend keeps polling until the document disappears. The actual file +
    # Qdrant cleanup runs in-process as a BackgroundTask (delete doesn't need
    # the worker's Docling stack — just Qdrant + filesystem + SQLite).
    record = update_document(document_id, status="deleting", error=None)
    job = create_job(record.id, "delete", "Document deletion queued")
    schedule_ingestion_job(background_tasks, delete_document_job, record.id, job.id)
    return {"document": record.to_api(), "job_id": job.id}


@router.post("/{document_id}/review", response_model=DocumentResponse)
async def mark_document_reviewed(document_id: str):
    """Dismiss the needs_review status and mark the document as ready."""
    record = get_document(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if record.status != "needs_review":
        raise HTTPException(status_code=409, detail=f"Document is not pending review (current status: {record.status})")
    updated = update_document(document_id, status="indexed", error=None)
    return updated.to_api()
