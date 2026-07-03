"""Pydantic models for the /summarize API endpoint."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


StyleLiteral = Literal[
    "methodology_overview",
    "key_requirements",
    "monitoring_steps",
    "eligibility_criteria",
]


class SummarizeRequest(BaseModel):
    """Request model for document summarization."""

    document_id: Optional[str] = Field(
        default=None,
        max_length=64,
        pattern=r"^[A-Za-z0-9_\-]+$",
        description="Specific document ID to summarize (e.g. VM0007). "
        "If omitted, all documents are considered.",
    )
    style: StyleLiteral = Field(
        default="methodology_overview",
        description="Summarization style controlling retrieval query and prompt template.",
    )
    top_k: int = Field(default=8, ge=1, le=20, description="Number of chunks to retrieve.")


class SummarizeCitation(BaseModel):
    """Citation attached to a summary."""

    source_name: str
    snippet: str
    relevance_score: float = Field(ge=0.0, le=1.0)
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    section: Optional[str] = None


class SummarizeResponse(BaseModel):
    """Response model for document summarization."""

    summary: str
    style: StyleLiteral
    document_id: Optional[str] = None
    citations: List[SummarizeCitation] = Field(default_factory=list)
    grounding_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Composite grounding score (0-1) measuring summary-to-evidence overlap.",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
