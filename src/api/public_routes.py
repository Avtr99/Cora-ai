import uuid
import logging
from typing import Optional, List, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, BackgroundTasks
import sqlite3

from ..db.database import get_connection
from fastapi.concurrency import run_in_threadpool

logger = logging.getLogger(__name__)

router = APIRouter(tags=["public"])

# --- Models ---

class FeedbackPayload(BaseModel):
    messageId: str = Field(..., max_length=128)
    chatId: Optional[str] = Field(None, max_length=128)
    userId: Optional[str] = Field(None, max_length=128)
    rating: Literal["positive", "negative"]
    tags: Optional[List[str]] = Field(None, max_length=10)
    comment: Optional[str] = Field(None, max_length=2000)
    userQuery: Optional[str] = Field(None, max_length=5000)
    botAnswer: Optional[str] = Field(None, max_length=20000)

# --- Database Operations ---

def _insert_feedback(payload: FeedbackPayload) -> str:
    conn = get_connection()
    try:
        feedback_id = str(uuid.uuid4())
        # Store non-column data in metadata_json
        import json
        metadata = {}
        if payload.tags:
            metadata["tags"] = payload.tags
        if payload.userQuery:
            metadata["userQuery"] = payload.userQuery
        if payload.botAnswer:
            metadata["botAnswer"] = payload.botAnswer

        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO feedback (id, conversation_id, message_id, rating, comment, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                payload.chatId,
                payload.messageId,
                payload.rating,
                payload.comment,
                json.dumps(metadata) if metadata else None
            )
        )
        conn.commit()
        return feedback_id
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"Failed to insert feedback: {e}")
        raise
    finally:
        conn.close()

# --- Routes ---

@router.post("/submit-feedback", status_code=201)
@router.post("/feedback", status_code=201) # also support cleaner URL
async def submit_feedback(payload: FeedbackPayload, background_tasks: BackgroundTasks):
    """Submit user feedback for an AI response."""
    try:
        # Run DB operation in threadpool to avoid blocking event loop
        feedback_id = await run_in_threadpool(_insert_feedback, payload)
        return {"status": "success", "id": feedback_id}
    except Exception as e:
        logger.error(f"Error processing feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")