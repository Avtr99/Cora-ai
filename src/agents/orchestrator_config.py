"""
Orchestrator Configuration

Configuration dataclass for the RAG orchestrator.
"""

from dataclasses import dataclass
from .router import RouteDecision


@dataclass(frozen=True)
class OrchestratorConfig:
    """Configuration for the RAG orchestrator."""
    # Query rewriting
    enable_rewriting: bool = True
    use_quick_rewrite: bool = False  # Use local acronym expansion only
    
    # Routing
    enable_routing: bool = True
    default_route: RouteDecision = RouteDecision.KNOWLEDGE_BASE
    
    # Retrieval
    retrieval_k: int = 10
    retrieval_threshold: float = 0.5
    retrieval_rounds: int = 2
    # Minimum TOP rerank score for the KB to be trusted as the sole answer
    # source. Below this, the orchestrator falls back to web search. 0 disables.
    kb_min_top_relevance_score: float = 0.0

    # Web search
    enable_web_search: bool = True
    web_supplement_relevance_confidence_threshold: float = 0.8

    # Validation
    enable_validation: bool = False  # Disabled by default for speed
    validate_long_answers_only: bool = True
    
    # Performance
    max_total_time_ms: int = 30000  # 30 second default; configurable via settings
    parallel_retrieval: bool = True
