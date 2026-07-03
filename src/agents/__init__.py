"""
Multi-Agent RAG System

This module provides a multi-agent architecture for improved RAG performance:
- QueryRewriterAgent: Fixes typos, expands acronyms, clarifies intent
- RouterAgent: Decides between vector store and web search
- WebSearchAgent: Uses Gemini Google Search grounding for web queries
- AnswerValidator: Validates answer grounding (optional)
- RAGOrchestrator: Coordinates all agents
- OrchestratorConfig: Configuration for the orchestrator
- RouteProcessor: Handles route-specific processing logic
- AgentStep: Represents a step in the agent pipeline
"""

from .query_rewriter import QueryRewriterAgent
from .router import RouterAgent
from .web_search import WebSearchAgent
from .validator import AnswerValidator
from .orchestrator import RAGOrchestrator
from .orchestrator_config import OrchestratorConfig
from .route_processors import RouteProcessor
from .reasoning_formatter import AgentStep, format_reasoning_steps

__all__ = [
    "QueryRewriterAgent",
    "RouterAgent", 
    "WebSearchAgent",
    "AnswerValidator",
    "RAGOrchestrator",
    "OrchestratorConfig",
    "RouteProcessor",
    "AgentStep",
    "format_reasoning_steps",
]
