"""
Memory storage module with lazy loading for startup optimization.

Heavy imports (qdrant_client, embedding provider) are deferred until first use
to reduce startup time.
"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from datetime import datetime, timezone
import uuid
import hashlib
import asyncio
from loguru import logger

from .pii_redactor import get_pii_redactor

# Type hints only - not imported at runtime
if TYPE_CHECKING:
    from qdrant_client import QdrantClient
    from langchain_core.embeddings import Embeddings


class EmbeddingError(Exception):
    """Error during embedding generation."""


class MemoryStorage:
    """Handles storage operations for conversation memory using Qdrant."""
    
    def __init__(self, client: "QdrantClient", collection_name: str, embeddings: Optional["Embeddings"] = None):
        """
        Initialize memory storage.

        Args:
            client: QdrantClient instance
            collection_name: Name of the Qdrant collection
            embeddings: Optional LangChain Embeddings instance (created via
                provider factory if not provided)
        """
        self.client = client
        self.collection_name = collection_name
        if embeddings is None:
            # Use pluggable embedding provider factory
            from ..embeddings import create_embeddings
            self.embeddings = create_embeddings()
        else:
            self.embeddings = embeddings

    def _build_qdrant_filter(self, user_id_hash: str, session_id: Optional[str] = None):
        """
        Build Qdrant filter for memory queries.

        Args:
            user_id_hash: Anonymized user ID
            session_id: Optional session ID filter (will be hashed to match stored values)

        Returns:
            Filter instance for Qdrant queries
        """
        # Lazy import for cold start optimization
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        # Build Qdrant filter
        conditions = [FieldCondition(key="user_id_hash", match=MatchValue(value=user_id_hash))]
        if session_id:
            # Hash session_id to match the hashed value stored in add_memory
            session_hash = hashlib.sha256(session_id.encode('utf-8')).hexdigest()[:16]
            conditions.append(FieldCondition(key="session_id", match=MatchValue(value=session_hash)))
        return Filter(must=conditions)

    def _format_session_context(self, session_id: Optional[str]) -> str:
        """
        Format session context for logging with anonymized session_id.

        Args:
            session_id: Optional session identifier

        Returns:
            Anonymized session context string for audit logs (GDPR-compliant)
        """
        if not session_id:
            return ""
        # Use short hash to avoid exposing identifying information
        session_hash = hashlib.sha256(session_id.encode('utf-8')).hexdigest()[:8]
        return f"session_hash={session_hash}, "
    
    def format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format messages into a single text string for embedding."""
        parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                parts.append(f"{role}: {content}")
        return "\n".join(parts)
    
    async def add_memory(
        self,
        memory_text: str,
        user_id_hash: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Add a memory to storage.
        
        PII is automatically redacted before storage for GDPR compliance.
        
        Args:
            memory_text: Formatted memory text
            user_id_hash: Anonymized user ID
            session_id: Optional session identifier
            metadata: Optional additional metadata
            
        Returns:
            Result dict with status and memory ID
        """
        try:
            # Redact PII before storage (GDPR compliance)
            # Offload CPU-bound redaction to thread to avoid blocking event loop
            redactor = get_pii_redactor()
            redaction_result = await asyncio.to_thread(redactor.redact, memory_text)
            safe_memory_text = redaction_result.redacted_text
            
            # Guard against None/empty redacted text before embedding
            if not safe_memory_text:
                logger.error(
                    f"PII redaction returned empty/None text, skipping storage. "
                    f"Original length={len(memory_text) if memory_text else 0}, "
                    f"detections={redaction_result.detections}"
                )
                return {
                    "status": "error",
                    "error_type": "redaction",
                    "message": "Redaction resulted in empty text, memory not stored"
                }
            
            # Generate embedding using LangChain Embeddings (async)
            # Use redacted text to prevent PII from entering vector embeddings
            try:
                embedding = await self.embeddings.aembed_query(safe_memory_text)
            except Exception as e:
                # Wrap embedding errors in custom EmbeddingError
                raise EmbeddingError(f"Voyage AI embedding failed: {e}") from e
            
            # Build metadata
            meta = metadata.copy() if metadata else {}
            meta["user_id_hash"] = user_id_hash
            meta["timestamp"] = datetime.now(timezone.utc).isoformat()
            if session_id:
                # Hash session_id to avoid storing plain PII
                session_hash = hashlib.sha256(session_id.encode('utf-8')).hexdigest()[:16]
                meta["session_id"] = session_hash
            
            # Generate unique ID
            memory_id = str(uuid.uuid4())
            
            # Lazy import for cold start optimization
            from qdrant_client.models import PointStruct
            
            # Store in Qdrant (use redacted text)
            point = PointStruct(
                id=memory_id,
                vector=embedding,
                payload={
                    "document": safe_memory_text,
                    **meta
                }
            )
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
            
            logger.debug("Added memory to storage")
            return {"status": "success", "result": {"memory_id": memory_id}}
            
        except EmbeddingError as e:
            logger.error(f"Embedding error adding memory: {e}", exc_info=True)
            return {
                "status": "error",
                "error_type": "embedding",
                "message": "An error occurred while processing embeddings"
            }
        except Exception as e:
            logger.error(f"Error adding memory to storage: {e}", exc_info=True)
            return {
                "status": "error",
                "error_type": "internal",
                "message": "Internal server error"
            }
    
    async def search_memories(
        self,
        query: str,
        user_id_hash: str,
        session_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant memories.

        Args:
            query: Search query string
            user_id_hash: Anonymized user ID
            session_id: Optional session ID filter
            limit: Maximum number of results (must be between 1 and 100)

        Returns:
            List of relevant memory entries
        """
        # Validate limit parameter
        MAX_LIMIT = 100
        if not isinstance(limit, int):
            raise ValueError(f"limit must be an integer, got {type(limit).__name__}")
        if limit < 1:
            raise ValueError(f"limit must be at least 1, got {limit}")
        if limit > MAX_LIMIT:
            raise ValueError(f"limit cannot exceed {MAX_LIMIT}, got {limit}")

        try:
            # Generate query embedding using LangChain Embeddings (async)
            try:
                query_embedding = await self.embeddings.aembed_query(query)
            except Exception as e:
                # Wrap embedding errors in custom EmbeddingError
                raise EmbeddingError(f"Voyage AI embedding failed: {e}") from e
            
            # Build Qdrant filter using helper
            query_filter = self._build_qdrant_filter(user_id_hash, session_id)
            
            # Query Qdrant
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_embedding,
                query_filter=query_filter,
                limit=limit,
                with_payload=True
            )
            results = response.points

            # Format results
            memories = []
            for point in results:
                payload = point.payload or {}
                memory = {
                    "id": point.id,
                    "memory": payload.get("document", ""),
                    "metadata": {k: v for k, v in payload.items() if k != "document"},
                    "similarity": point.score
                }
                memories.append(memory)
            
            logger.debug(f"Found {len(memories)} memories for query")
            return memories
            
        except EmbeddingError as e:
            logger.error(f"Embedding error searching memories: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            return []
    
    def get_all_memories(
        self,
        user_id_hash: str,
        session_id: Optional[str] = None,
        limit: int = 100,
        offset: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get paginated memories.

        Note: This method is synchronous because the Qdrant client is a blocking
        synchronous client. While add_memory and search_memories are async due to
        embedding generation, the Qdrant client operations themselves are blocking.
        Callers should be aware this method will block the event loop.

        Args:
            user_id_hash: Anonymized user ID
            session_id: Optional session ID filter
            limit: Maximum results per page
            offset: Cursor for pagination (point ID from previous page's next_page_offset)

        Returns:
            Dict with memories list and pagination info
        """
        try:
            # Build Qdrant filter using helper
            query_filter = self._build_qdrant_filter(user_id_hash, session_id)

            # Scroll through matching documents with cursor-based pagination
            # offset should be None for first page, or the next_page_offset from previous scroll
            results, next_page_offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=query_filter,
                limit=limit,
                offset=offset,  # Expects point ID cursor, not numeric skip
                with_payload=True
            )
            
            # Check if there are more results based on next_page_offset
            has_more = next_page_offset is not None
            
            memories = []
            for point in results:
                payload = point.payload or {}
                memory = {
                    "id": point.id,
                    "memory": payload.get("document", ""),
                    "metadata": {k: v for k, v in payload.items() if k != "document"}
                }
                memories.append(memory)
            
            return {
                "memories": memories,
                "count": len(memories),
                "limit": limit,
                "offset": offset,
                "has_more": has_more,
                "next_page_offset": next_page_offset  # Return cursor for next page
            }
            
        except Exception as e:
            logger.error(f"Error getting all memories: {e}", exc_info=True)
            return {"memories": [], "count": 0, "limit": limit, "offset": offset, "has_more": False, "error": "An internal error occurred"}
    
    def delete_memories(
        self,
        user_id_hash: str,
        session_id: Optional[str] = None
    ) -> int:
        """
        Delete memories from storage using native filter deletion.

        Args:
            user_id_hash: Anonymized user ID
            session_id: Optional session ID filter

        Returns:
            Number of deleted memories (estimated, Qdrant doesn't return exact count)
        """
        try:
            # Build Qdrant filter using helper
            query_filter = self._build_qdrant_filter(user_id_hash, session_id)
            
            # Lazy import for FilterSelector
            from qdrant_client.models import FilterSelector

            # Use native filter deletion (O(1) single API call)
            # Note: Qdrant doesn't return the exact count of deleted items in this mode
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(filter=query_filter)
            )

            # Audit log with anonymized context
            session_context = self._format_session_context(session_id)
            logger.info(
                f"Memory deletion completed: user_hash={user_id_hash[:8]}..., "
                f"{session_context}status=success (native filter deletion)"
            )

            # Return 0 as count since Qdrant doesn't provide exact count in filter deletion mode
            return 0

        except Exception as e:
            logger.error(f"Error deleting memories: {e}", exc_info=True)
            raise
