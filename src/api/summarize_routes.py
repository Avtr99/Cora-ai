"""API route for document summarization."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException

from .lifespan import get_retriever, get_gemini_client
from .summarize_models import SummarizeRequest, SummarizeResponse, SummarizeCitation
from ..query_processing.summarize_service import summarize_document

logger = logging.getLogger(__name__)

_SAFE_VALUE_ERROR_MESSAGES = frozenset({
    "retriever and gemini_client are required",
})

router = APIRouter(tags=["summarize"])


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(req: SummarizeRequest):
    """
    Summarize a carbon credit methodology document with style-specific
    retrieval and generation.

    Styles:
    - **methodology_overview**: TL;DR with purpose, applicability, warnings
    - **key_requirements**: Mandatory provisions grouped by theme
    - **monitoring_steps**: MRV workflow steps
    - **eligibility_criteria**: Eligible/not-eligible conditions
    """
    try:
        # Get shared components from app state
        retriever = await get_retriever()
        gemini_client = get_gemini_client()

        result = await summarize_document(
            style=req.style,
            document_id=req.document_id,
            top_k=req.top_k,
            retriever=retriever,
            gemini_client=gemini_client,
        )

        citations = [
            SummarizeCitation(**c) for c in result["citations"]
        ]

        return SummarizeResponse(
            summary=result["summary"],
            style=result["style"],
            document_id=result["document_id"],
            citations=citations,
            grounding_score=result["grounding_score"],
            metadata=result["metadata"],
        )

    except ValueError as e:
        safe_msg = str(e) if str(e) in _SAFE_VALUE_ERROR_MESSAGES else "Invalid request"
        logger.warning(f"Summarize ValueError: {e}")
        raise HTTPException(status_code=400, detail=safe_msg)
    except Exception:
        error_id = str(uuid.uuid4())
        logger.exception(f"Summarize failed [id={error_id}]")
        raise HTTPException(
            status_code=500,
            detail=f"Summarization failed (error_id: {error_id})",
        )
