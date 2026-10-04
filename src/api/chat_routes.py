"""Server-side chat endpoints (Phase 7).

Chats live in the instance SQLite database under the request's ``user_id`` —
the chat id is the conversation id (B2), so the path parameter uses the same
constraints as ``Query.conversation_id``. The router is mounted under ``/v1``
and ``/api``; both are protected path prefixes, so ``SecurityMiddleware`` has
already set ``request.state.user_id`` when protection is on.
"""
import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from ..db import chats as chat_store
from .auth.session_auth import current_user_id

router = APIRouter(prefix="/chats", tags=["Chats"])

# Same constraints as Query.conversation_id in query_models.py (B2).
_CHAT_ID = Path(max_length=64, pattern=r"^[a-zA-Z0-9\-]+$")


class ChatSummaryResponse(BaseModel):
    id: str
    title: str
    updated_at: str


class ChatListResponse(BaseModel):
    chats: List[ChatSummaryResponse]


class ChatTurnResponse(BaseModel):
    message_id: str
    answer_id: str
    user_text: str
    response: Dict[str, Any]
    created_at: str


class ChatDetailResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    turns: List[ChatTurnResponse]


@router.get("", response_model=ChatListResponse)
async def list_chats(user_id: str = Depends(current_user_id)):
    """List the current user's chats, most recently updated first."""
    chats = await asyncio.to_thread(chat_store.list_chats, user_id)
    return {"chats": chats}


@router.get("/{chat_id}", response_model=ChatDetailResponse)
async def get_chat(chat_id: str = _CHAT_ID, user_id: str = Depends(current_user_id)):
    """Return one chat with all its turns. Other users' chats 404 (D33)."""
    chat = await asyncio.to_thread(chat_store.get_chat, user_id, chat_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(chat_id: str = _CHAT_ID, user_id: str = Depends(current_user_id)):
    """Delete one chat and its turns. Other users' chats 404 (D33)."""
    deleted = await asyncio.to_thread(chat_store.delete_chat, user_id, chat_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat not found")
