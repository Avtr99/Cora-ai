"""Query route adapters and backward-compatible exports."""

import time
import uuid

from fastapi import HTTPException, Request
from loguru import logger

from ..config import get_settings
from .query_models import (
    Message,
    Query,
    QuizResponse,
    Response,
    TestQueryRequest,
    TestQueryResponse,
)
from .query_sanitization import sanitize_quiz_payload
from .query_service import process_query_core


async def process_query(query: Query, request: Request) -> Response:
    """
    Process a user query using RAG pipeline with security sanitization.
    
    Args:
        query: The query request
        request: FastAPI request object
        
    Returns:
        Response with answer, sources, and citations
    """
    try:
        return await process_query_core(
            query,
            request,
            include_reasoning=query.include_debug,
            include_metadata=False,
            include_duration_ms=False,
            include_chat_history_in_orchestrator=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_id = str(uuid.uuid4())[:8]
        # Public log: only error type and ID (no sensitive query data)
        logger.error(f"Error processing query [error_id={error_id}]: {type(e).__name__}")
        # Secure audit log: full exception details with traceback (INFO ensures visibility in production)
        logger.opt(depth=1).bind(audit=True, error_id=error_id).info(
            "Full error details for debugging", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error processing query (error_id: {error_id})"
        )


async def test_query(request: Request, test_request: TestQueryRequest) -> TestQueryResponse:
    """
    Direct query testing endpoint for development.
    
    Allows testing queries directly without frontend, with full debug output.
    Reuses process_query_core to ensure consistent security and sanitization.
    """
    settings = get_settings()
    if not settings.ENABLE_TEST_ENDPOINT:
        raise HTTPException(status_code=404, detail="Endpoint not available")
    
    start_time = time.time()
    
    try:
        # Convert TestQueryRequest to Query and reuse the core pipeline
        query = Query(text=test_request.query, include_debug=test_request.include_reasoning)
        response = await process_query_core(
            query,
            request,
            include_reasoning=test_request.include_reasoning,
            include_metadata=True,
            include_duration_ms=True,
            include_chat_history_in_orchestrator=False,
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Map Response to TestQueryResponse
        sanitized_reasoning = None
        sanitized_citations = None
        
        if test_request.include_reasoning and response.reasoning_steps:
            sanitized_reasoning = [
                {
                    "name": step.name,
                    "status": step.status,
                    "duration_ms": step.duration_ms,
                    "details": step.details,
                }
                for step in response.reasoning_steps
            ]
        
        if test_request.include_sources and response.citations:
            sanitized_citations = {
                "count": response.citations.count,
                "sources": response.citations.sources,
                "details": [detail.model_dump() for detail in response.citations.details],
            }
        
        return TestQueryResponse(
            query=query.text,
            answer=response.answer,
            confidence=response.confidence,
            sources=response.sources,
            latency_ms=round(latency_ms, 2),
            reasoning_steps=sanitized_reasoning,
            citations=sanitized_citations,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        error_id = str(uuid.uuid4())[:8]
        logger.error(f"Test query error [error_id={error_id}]: {type(e).__name__}")
        logger.opt(depth=1).bind(audit=True, error_id=error_id).info(
            "Full error details for debugging", exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error processing test query (error_id: {error_id})"
        )


__all__ = [
    "Message",
    "Query",
    "QuizResponse",
    "Response",
    "TestQueryRequest",
    "TestQueryResponse",
    "process_query",
    "process_query_core",
    "sanitize_quiz_payload",
    "test_query",
]
