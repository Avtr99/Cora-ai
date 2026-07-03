"""
Memory API routes for conversation memory management.

Provides endpoints for storing and retrieving conversation history
using pluggable embeddings + Qdrant for persistent memory across sessions.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from ..memory import get_memory_client
from ..utils.patterns import handle_api_errors
from .middleware import (
    AuthenticatedUser,
    get_authenticated_user,
    validate_user_access
)

router = APIRouter(prefix="/memory", tags=["memory"])


class Message(BaseModel):
    """A single message in a conversation."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class AddConversationRequest(BaseModel):
    """Request to add a conversation to memory."""
    messages: List[Message] = Field(..., description="List of conversation messages")
    user_id: str = Field(..., description="Unique user identifier")
    session_id: Optional[str] = Field(None, description="Optional session identifier")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")


class AddConversationResponse(BaseModel):
    """Response after adding a conversation."""
    status: str
    message: str
    result: Optional[Dict[str, Any]] = None


class SearchMemoriesRequest(BaseModel):
    """Request to search memories."""
    query: str = Field(..., description="Search query")
    user_id: str = Field(..., description="User ID to search memories for")
    session_id: Optional[str] = Field(None, description="Optional session ID filter")
    limit: int = Field(5, description="Maximum results to return", ge=1, le=20)


class MemoryEntry(BaseModel):
    """A single memory entry."""
    memory: str
    id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchMemoriesResponse(BaseModel):
    """Response from memory search."""
    memories: List[Dict[str, Any]]
    count: int
    query: str


class GetContextRequest(BaseModel):
    """Request to get conversation context."""
    query: str = Field(..., description="Current query to get context for")
    user_id: str = Field(..., description="User ID")
    session_id: Optional[str] = Field(None, description="Optional session ID")


class GetContextResponse(BaseModel):
    """Response with formatted context."""
    context: str
    has_context: bool


class DeleteMemoriesRequest(BaseModel):
    """Request to delete memories with authorization."""
    user_id: str = Field(..., description="User ID to delete memories for")
    auth_token: str = Field(..., description="Authorization token from /memory/delete-token endpoint")
    session_id: Optional[str] = Field(None, description="Optional session ID to delete")
    confirm: bool = Field(..., description="Must be explicitly set to True to confirm deletion")
    
    @field_validator('confirm')
    @classmethod
    def validate_confirm(cls, v: bool) -> bool:
        """Ensure confirm is True to prevent accidental deletion."""
        if not v:
            raise ValueError("confirm must be True to proceed with deletion")
        return v


@router.post("/add", response_model=AddConversationResponse)
@handle_api_errors()
async def add_conversation(
    request: AddConversationRequest,
    auth_user: AuthenticatedUser = Depends(get_authenticated_user)
):
    """
    Add a conversation to memory.
    
    Stores the conversation messages for later retrieval, enabling
    the AI to remember past interactions with the user.
    
    Requires X-User-ID header matching request.user_id.
    """
    # Validate authenticated user matches requested user_id
    validate_user_access(auth_user, request.user_id)
    
    memory_client = get_memory_client()
    
    if not memory_client.is_available:
        raise HTTPException(
            status_code=503,
            detail="Memory service is not available"
        )
    
    # Convert Pydantic models to dicts
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    result = await memory_client.add_conversation(
        messages=messages,
        user_id=auth_user.user_id,
        session_id=request.session_id,
        metadata=request.metadata
    )
    
    if result["status"] == "success":
        return AddConversationResponse(
            status="success",
            message="Conversation added to memory",
            result=result.get("result")
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=result.get("message", "Failed to add conversation")
        )


@router.post("/search", response_model=SearchMemoriesResponse)
@handle_api_errors()
async def search_memories(
    request: SearchMemoriesRequest,
    auth_user: AuthenticatedUser = Depends(get_authenticated_user)
):
    """
    Search for relevant memories based on a query.
    
    Returns memories that are semantically similar to the query,
    filtered by user and optionally by session.
    
    Requires X-User-ID header matching request.user_id.
    """
    # Validate authenticated user matches requested user_id
    validate_user_access(auth_user, request.user_id)
    
    memory_client = get_memory_client()
    
    if not memory_client.is_available:
        return SearchMemoriesResponse(
            memories=[],
            count=0,
            query=request.query
        )
    
    memories = await memory_client.search_memories(
        query=request.query,
        user_id=auth_user.user_id,
        session_id=request.session_id,
        limit=request.limit
    )
    
    return SearchMemoriesResponse(
        memories=memories,
        count=len(memories),
        query=request.query
    )


@router.post("/context", response_model=GetContextResponse)
@handle_api_errors()
async def get_context(
    request: GetContextRequest,
    auth_user: AuthenticatedUser = Depends(get_authenticated_user)
):
    """
    Get formatted conversation context for a query.
    
    Returns a formatted string of relevant past conversations
    that can be included in prompts for personalized responses.
    
    Requires X-User-ID header matching request.user_id.
    """
    # Validate authenticated user matches requested user_id
    validate_user_access(auth_user, request.user_id)
    
    memory_client = get_memory_client()
    
    if not memory_client.is_available:
        return GetContextResponse(
            context="",
            has_context=False
        )
    
    context = await memory_client.get_conversation_context(
        query=request.query,
        user_id=auth_user.user_id,
        session_id=request.session_id
    )
    
    return GetContextResponse(
        context=context,
        has_context=bool(context)
    )


@router.get("/all/{user_id}")
@handle_api_errors()
async def get_all_memories(
    user_id: str,
    session_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    auth_user: AuthenticatedUser = Depends(get_authenticated_user)
):
    """
    Get paginated memories for a user.
    
    Returns paginated memories, optionally filtered by session.
    Supports pagination via limit (max 1000) and offset parameters.
    
    Requires X-User-ID header matching path user_id.
    """
    # Validate authenticated user matches requested user_id
    validate_user_access(auth_user, user_id)
    
    memory_client = get_memory_client()
    
    if not memory_client.is_available:
        return {
            "memories": [],
            "count": 0,
            "limit": limit,
            "offset": offset,
            "has_more": False
        }
    
    result = memory_client.get_all_memories(
        user_id=auth_user.user_id,
        session_id=session_id,
        limit=limit,
        offset=offset
    )
    
    return result


@router.post("/delete-token")
@handle_api_errors()
async def get_delete_token(
    user_id: str,
    auth_user: AuthenticatedUser = Depends(get_authenticated_user)
):
    """
    Get an authorization token for deleting memories.
    
    This token must be included in delete requests to authorize
    the deletion. Tokens are user-specific and required for security.
    
    Requires X-User-ID header matching query user_id.
    """
    # Validate authenticated user matches requested user_id
    validate_user_access(auth_user, user_id)
    
    memory_client = get_memory_client()
    
    if not memory_client.is_available:
        raise HTTPException(
            status_code=503,
            detail="Memory service is not available"
        )
    
    try:
        token = memory_client.get_delete_token(auth_user.user_id)
        return {
            "status": "success",
            "auth_token": token,
            "message": "Include this token in your delete request"
        }
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid request parameters")


@router.delete("/delete")
@handle_api_errors()
async def delete_memories(
    request: DeleteMemoriesRequest,
    auth_user: AuthenticatedUser = Depends(get_authenticated_user)
):
    """
    Delete memories for a user with authorization.
    
    Requires a valid auth_token from /memory/delete-token endpoint
    and confirm=True to prevent accidental deletion.
    
    Requires X-User-ID header matching request.user_id.
    
    NOTE: Future improvement - have memory_client raise specific exceptions
    (AuthorizationError, ValidationError) instead of returning error dicts,
    so this handler can catch them directly.
    """
    # Validate authenticated user matches requested user_id
    validate_user_access(auth_user, request.user_id)
    
    # Early validation: confirm must be True (redundant with Pydantic validator, but explicit)
    if not request.confirm:
        raise HTTPException(
            status_code=400,
            detail="confirm must be True to proceed with deletion"
        )
    
    memory_client = get_memory_client()
    
    if not memory_client.is_available:
        raise HTTPException(
            status_code=503,
            detail="Memory service is not available"
        )
    
    result = memory_client.delete_memories(
        user_id=auth_user.user_id,
        auth_token=request.auth_token,
        session_id=request.session_id,
        confirm=request.confirm
    )
    
    # Use structured error handling instead of substring matching
    if result["status"] == "success":
        return {
            "status": "success",
            "message": "Memories deleted successfully",
            "deleted_count": result.get("deleted_count", 0)
        }
    
    # Check for structured error_type field
    error_type = result.get("error_type")
    error_message = result.get("message", "Failed to delete memories")
    
    if error_type == "authorization":
        raise HTTPException(status_code=403, detail=error_message)
    elif error_type == "validation":
        raise HTTPException(status_code=400, detail=error_message)
    else:
        # Generic error - could be 500 or 400 depending on context
        raise HTTPException(status_code=400, detail=error_message)


@router.get("/status")
@handle_api_errors()
async def memory_status():
    """
    Get memory service status.
    
    Returns whether the memory service is available and basic stats.
    """
    memory_client = get_memory_client()
    
    return {
        "available": memory_client.is_available,
        "provider": "voyage-qdrant" if memory_client.is_available else None,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
