from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from loguru import logger

from ..document_store.jobs import delete_document_job, process_document_job, reindex_document_job
from ..document_store.converter import get_conversion_capabilities
from ..document_store.storage import (
    create_job,
    get_document,
    get_job,
    list_documents,
    parse_tags,
    read_markdown,
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


@router.get("/conversion-info", response_model=ConversionCapabilitiesResponse)
async def get_conversion_info():
    """Return availability and resolved provider/model for each conversion mode."""
    return get_conversion_capabilities()


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
        record = await save_upload(file, conversion_mode, parse_tags(tags))
        job = create_job(record.id, "process", "Document queued")
        background_tasks.add_task(process_document_job, record.id, job.id)
        return {"document": record.to_api(), "job_id": job.id}
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
        background_tasks.add_task(reindex_document_job, record.id, job.id)
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
        background_tasks.add_task(delete_document_job, record.id, job.id)
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
    job = create_job(record.id, "reindex", "Document refresh queued")
    background_tasks.add_task(reindex_document_job, record.id, job.id)
    return {"document": record.to_api(), "job_id": job.id}


@router.delete("/{document_id}", response_model=DocumentActionResponse, status_code=202)
async def delete_document(document_id: str, background_tasks: BackgroundTasks):
    record = get_document(document_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Document not found")
    job = create_job(record.id, "delete", "Document deletion queued")
    background_tasks.add_task(delete_document_job, record.id, job.id)
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
