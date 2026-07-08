"""Pydantic models for query API request/response payloads."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator


class Message(BaseModel):
    """Conversation message for short-term history window."""

    role: Literal["system", "assistant", "user"]
    content: str


class Query(BaseModel):
    """Query request model."""

    text: str = Field(min_length=1, description="The user's query text.")
    conversation_id: Optional[str] = Field(
        default=None,
        max_length=64,
        pattern=r"^[a-zA-Z0-9\-]+$",
        description="Unique conversation identifier (UUID format recommended)",
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=128,
        description="Reserved for future use. Session binding uses server-side state.",
    )
    history: Optional[List[Message]] = Field(default=None, max_length=50)
    history_signature: Optional[str] = Field(
        default=None,
        max_length=64,
        pattern=r"^(?:[0-9a-fA-F]+|unsigned)$",
        description="HMAC-SHA256 hex signature for history integrity, or 'unsigned' for dev mode.",
    )
    include_debug: bool = False


class CitationDetail(BaseModel):
    """Citation detail model."""

    source_name: str
    source_type: str
    relevance_score: float
    page_number: Optional[int] = None
    section: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None
    # VCM metadata surfaced from the source document (registry, publisher,
    # version_number, document_id, methodology_codes, etc.). Present for KB
    # citations when the source document carries VCM metadata; absent for web
    # citations.
    metadata: Optional[Dict[str, Any]] = None


class CitationResponse(BaseModel):
    """Citation response model."""

    count: int
    sources: List[str]
    details: List[CitationDetail]


class AgentStepResponse(BaseModel):
    """Agent reasoning step model."""

    name: str
    status: str
    duration_ms: Optional[float] = None
    details: Dict[str, Any]


class QuizResponse(BaseModel):
    """Optional quiz payload attached to query responses."""

    question: str
    options: List[str]
    correctIndex: int
    explanation: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        question = value.strip()
        if not question:
            raise ValueError("question must be non-empty")
        return question

    @field_validator("options")
    @classmethod
    def validate_options(cls, value: List[str]) -> List[str]:
        if len(value) < 2:
            raise ValueError("options must contain at least 2 entries")
        return value

    @field_validator("correctIndex")
    @classmethod
    def validate_correct_index(cls, value: int, info: ValidationInfo) -> int:
        options = info.data.get("options", []) if info.data else []
        if value < 0 or value >= len(options):
            raise ValueError("correctIndex must be within options range")
        return value


class QueryMetadataResponse(BaseModel):
    """Optional query metadata surfaced to clients."""

    original_query: Optional[str] = None
    rewritten_query: Optional[str] = None
    route: Optional[str] = None
    route_confidence: Optional[float] = None
    total_time_ms: Optional[float] = None
    rewrite_info: Optional[Dict[str, Any]] = None
    timeout_exceeded: Optional[bool] = None
    timeout_reason: Optional[str] = None
    timing_breakdown: Optional[Dict[str, float]] = None
    history_verification_failed: bool = False
    history_items_dropped: int = 0


class Response(BaseModel):
    """Query response model."""

    answer: str
    confidence: float
    sources: List[str]
    conversation_id: str
    timestamp: str
    citations: Optional[CitationResponse] = None
    reasoning_steps: Optional[List[AgentStepResponse]] = None
    metadata: Optional[QueryMetadataResponse] = None
    quiz: Optional[QuizResponse] = None
    suggested_prompts: Optional[List[str]] = None
    history_signature: Optional[str] = None
    truncated: bool = False


class TestQueryRequest(BaseModel):
    """Test query request for direct testing."""

    query: str
    include_sources: bool = True
    include_reasoning: bool = True


class TestQueryResponse(BaseModel):
    """Test query response with full details."""

    query: str
    answer: str
    confidence: float
    sources: List[str]
    latency_ms: float
    reasoning_steps: Optional[List[Dict[str, Any]]] = None
    citations: Optional[Dict[str, Any]] = None
