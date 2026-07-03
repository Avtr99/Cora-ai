"""
Conversation memory module using LangChain Embeddings + Qdrant.

Provides persistent memory for chat conversations, enabling the AI to remember
user preferences and past interactions across sessions.

Uses pluggable LangChain Embeddings (Voyage / Cohere / Ollama) for embeddings
and Qdrant for vector storage.

Heavy imports (qdrant_client) are deferred until first use to reduce startup time.
"""
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from loguru import logger

from ..config import get_settings
from ..utils.patterns import singleton
from .validators import validate_id, validate_metadata, validate_pagination
from .memory_security import MemorySecurity

# Type hints only - not imported at runtime
if TYPE_CHECKING:
    from qdrant_client import QdrantClient

MEMORY_COLLECTION_NAME = "cora_memories"


@singleton
class ConversationMemory:
    """
    Manages conversation memory using LangChain Embeddings + Qdrant.
    
    Stores and retrieves conversation history per user and session,
    enabling personalized AI responses that remember past interactions.
    """
    
    # Class-level declarations for static analysis
    _initialized: bool = False
    client: "QdrantClient | None" = None
    
    def _initialize(self):
        """Initialize Qdrant client and collection for memories."""
        self._initialized = False
        try:
            settings = get_settings()
            
            # Validate memory secret is configured before proceeding
            secret_key = getattr(settings, 'MEMORY_SECRET_KEY', None) or getattr(settings, 'SECRET_KEY', None)
            if not secret_key or not str(secret_key).strip():
                raise ValueError(
                    "MEMORY_SECRET_KEY (preferred) or SECRET_KEY must be configured in settings for secure memory operations. "
                    "User ID anonymization and delete tokens require a cryptographic secret."
                )
            
            # Lazy imports for cold start optimization
            from qdrant_client import QdrantClient
            from qdrant_client.models import VectorParams, Distance
            from .memory_storage import MemoryStorage
            
            # Create Qdrant client
            self.client = QdrantClient(
                url=settings.QDRANT_URL,
                timeout=60,
            )
            self.collection_name = MEMORY_COLLECTION_NAME
            
            # Ensure collection exists
            if not self.client.collection_exists(self.collection_name):
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=settings.EMBEDDING_DIM,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created memory collection: {self.collection_name}")
            
            # Initialize storage (embeddings created inside MemoryStorage via factory)
            self.storage = MemoryStorage(self.client, self.collection_name)
            self._initialized = True
            logger.info("Conversation memory initialized (embeddings=%s + Qdrant)", settings.EMBEDDING_PROVIDER)
            
        except Exception as e:
            logger.error(f"Failed to initialize conversation memory: {e}", exc_info=True)
            self._initialized = False
    
    @property
    def is_available(self) -> bool:
        """Check if memory service is available."""
        return self._initialized
    
    def get_delete_token(self, user_id: str) -> str:
        """
        Get a delete authorization token for a user.
        
        This token must be included in delete requests to authorize
        the deletion of memories. Tokens are user-specific.
        
        Args:
            user_id: The user ID to get token for
            
        Returns:
            Authorization token string
            
        Raises:
            ValueError: If user_id is invalid
        """
        validate_id(user_id, "user_id")
        return MemorySecurity.generate_delete_token(user_id)
    
    async def add_conversation(
        self,
        messages: List[Dict[str, str]],
        user_id: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a conversation in memory.
        
        Args:
            messages: List of message dicts with 'role' and 'content' keys
            user_id: Unique identifier for the user
            session_id: Optional session identifier for grouping conversations
            metadata: Optional additional metadata to store
            
        Returns:
            Result dict with status and memory IDs
        """
        if not self._initialized:
            return {"status": "disabled", "message": "Memory not available"}
        
        try:
            # Validate inputs
            validate_id(user_id, "user_id")
            if session_id:
                validate_id(session_id, "session_id")
            validate_metadata(metadata)
            
            # Combine messages into a single memory text
            memory_text = self.storage.format_messages(messages)
            if not memory_text.strip():
                return {"status": "error", "message": "No content to store"}
            
            # Store using storage layer
            user_id_hash = MemorySecurity.anonymize_user_id(user_id)
            return await self.storage.add_memory(
                memory_text=memory_text,
                user_id_hash=user_id_hash,
                session_id=session_id,
                metadata=metadata
            )
            
        except ValueError as e:
            logger.warning(f"Validation error adding conversation: {e}")
            return {
                "status": "error",
                "error_type": "validation",
                "message": "Invalid input parameters"
            }
        except Exception as e:
            logger.error(f"Error adding conversation to memory: {e}", exc_info=True)
            return {
                "status": "error",
                "error_type": "internal",
                "message": "Failed to add conversation"
            }
    
    async def search_memories(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant memories based on a query.
        
        Args:
            query: Search query string
            user_id: User ID to search memories for
            session_id: Optional session ID to filter by
            limit: Maximum number of results to return
            
        Returns:
            List of relevant memory entries
        """
        if not self._initialized:
            return []
        
        try:
            # Validate inputs
            validate_id(user_id, "user_id")
            if session_id:
                validate_id(session_id, "session_id")
            
            # Search using storage layer
            user_id_hash = MemorySecurity.anonymize_user_id(user_id)
            return await self.storage.search_memories(
                query=query,
                user_id_hash=user_id_hash,
                session_id=session_id,
                limit=limit
            )
            
        except ValueError as e:
            logger.warning(f"Validation error searching memories: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching memories: {e}", exc_info=True)
            return []
    
    def get_all_memories(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 100,
        offset: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get paginated memories for a user.

        Args:
            user_id: User ID to get memories for
            session_id: Optional session ID to filter by
            limit: Maximum number of results per page (default: 100, max: 1000)
            offset: Cursor for pagination (point ID from previous page's next_page_offset)

        Returns:
            Dict with 'memories' list, 'count', 'limit', 'offset', and 'has_more' flag
        """
        if not self._initialized:
            return {"memories": [], "count": 0, "limit": limit, "offset": offset, "has_more": False}
        
        try:
            # Validate inputs
            validate_id(user_id, "user_id")
            if session_id:
                validate_id(session_id, "session_id")

            # Validate limit only (offset is now a cursor string)
            limit = validate_pagination(limit, 0)[0]

            # Get memories using storage layer
            user_id_hash = MemorySecurity.anonymize_user_id(user_id)
            return self.storage.get_all_memories(
                user_id_hash=user_id_hash,
                session_id=session_id,
                limit=limit,
                offset=offset
            )
            
        except ValueError as e:
            logger.warning(f"Validation error getting memories: {e}")
            return {"memories": [], "count": 0, "limit": limit, "offset": offset, "has_more": False, "message": "Invalid request parameters"}
        except Exception as e:
            logger.error(f"Error getting all memories: {e}", exc_info=True)
            return {"memories": [], "count": 0, "limit": limit, "offset": offset, "has_more": False, "message": "Internal error retrieving memories"}
    
    async def get_conversation_context(
        self,
        query: str,
        user_id: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Get formatted conversation context for a query.
        
        This is a convenience method that searches memories and formats
        them into a context string suitable for including in prompts.
        
        Args:
            query: The current user query
            user_id: User ID
            session_id: Optional session ID
            
        Returns:
            Formatted context string
        """
        memories = await self.search_memories(query, user_id, session_id)
        
        if not memories:
            return ""
        
        context_parts = ["Relevant information from previous conversations:"]
        for memory in memories:
            memory_text = memory.get("memory", "")
            if memory_text:
                context_parts.append(f"- {memory_text}")
        
        return "\n".join(context_parts)
    
    def delete_memories(
        self,
        user_id: str,
        auth_token: str,
        session_id: Optional[str] = None,
        confirm: bool = False
    ) -> Dict[str, Any]:
        """
        Delete memories for a user with authorization.
        
        Requires a valid authorization token obtained via get_delete_token().
        This prevents unauthorized deletion of user data.
        
        Args:
            user_id: User ID to delete memories for
            auth_token: Authorization token from get_delete_token()
            session_id: Optional session ID to delete specific session
            confirm: Must be True to confirm deletion (prevents accidental calls)
            
        Returns:
            Result dict with status and deleted_count
        """
        if not self._initialized:
            return {"status": "disabled", "message": "Memory not available"}
        
        try:
            # Validate inputs
            validate_id(user_id, "user_id")
            if session_id:
                validate_id(session_id, "session_id")
            
            # Require confirmation flag to prevent accidental deletion
            if not confirm:
                return {
                    "status": "error",
                    "error_type": "validation",
                    "message": "Deletion requires confirm=True to prevent accidental data loss"
                }
            
            # Verify authorization token
            if not MemorySecurity.verify_delete_token(user_id, auth_token):
                logger.warning("Unauthorized memory deletion attempt")
                return {
                    "status": "error",
                    "error_type": "authorization",
                    "message": "Invalid or missing authorization token"
                }
            
            # Delete using storage layer
            user_id_hash = MemorySecurity.anonymize_user_id(user_id)
            deleted_count = self.storage.delete_memories(
                user_id_hash=user_id_hash,
                session_id=session_id
            )
            
            return {"status": "success", "deleted_count": deleted_count}
            
        except ValueError as e:
            logger.warning(f"Validation error deleting memories: {e}")
            return {"status": "error", "error_type": "validation", "message": "Invalid request parameters"}
        except Exception as e:
            logger.error(f"Error deleting memories: {e}", exc_info=True)
            return {
                "status": "error",
                "error_type": "internal",
                "message": "Failed to delete memories"
            }


# Singleton accessor function (for backward compatibility)
_memory_client: Optional[ConversationMemory] = None


def get_memory_client() -> ConversationMemory:
    """
    Get or create the singleton memory client.
    
    Returns:
        ConversationMemory instance
    """
    global _memory_client
    if _memory_client is None:
        _memory_client = ConversationMemory.get_instance()
    return _memory_client
