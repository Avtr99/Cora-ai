"""
Reasoning Step Formatter for RAG Orchestrator.

Formats agent pipeline steps for transparent workflow display.
"""
from typing import Dict, Any, List, Literal
from dataclasses import dataclass, field, asdict


@dataclass
class AgentStep:
    """
    Represents a step in the agent pipeline for reasoning display.
    
    Attributes:
        name: Step name (e.g., "Query Rewriting", "Query Routing")
        status: Step status - must be "completed", "in_progress", or "skipped"
        duration_ms: Time taken for this step in milliseconds
        details: Additional step-specific information
    """
    name: str
    status: Literal["completed", "in_progress", "skipped", "cached", "failed", "fallback"]
    duration_ms: float = 0
    details: Dict[str, Any] = field(default_factory=dict)


def format_reasoning_steps(steps: List[AgentStep]) -> List[Dict[str, Any]]:
    """
    Format reasoning steps for transparent agentic workflow display.
    
    Creates user-friendly reasoning steps showing:
    - Query rewriting
    - Routing decision
    - Document retrieval or web search
    - Retrieved content summary
    - Answer generation
    
    Args:
        steps: List of agent steps
        
    Returns:
        List of formatted reasoning steps
    """
    formatted_steps: List[Dict[str, Any]] = []

    for step in steps:
        name = step.name
        status = step.status
        details = step.details or {}

        formatted_step = {
            "name": name,
            "status": status,
            "duration_ms": step.duration_ms,
            "details": {
                "title": name,
                "summary": "",
                "highlights": [],
            },
        }

        if name == "Query Rewriting":
            intent = details.get("intent")
            rewritten = details.get("rewritten")
            summary = "Refined and clarified the question for better search results"
            if status == "skipped":
                summary = "Used the original question as-is"
            elif status == "cached":
                summary = "Used a previously refined version of a similar question"

            highlights = []
            if intent:
                highlights.append(f"Intent detected: {intent}")
            if rewritten and rewritten != details.get("original"):
                highlights.append("Clarified wording to improve search accuracy")

            step_details: Dict[str, Any] = {
                "title": "Clarify the question",
                "summary": summary,
                "highlights": highlights or ["Prepared the query for the next steps"],
            }
            # Include rewritten_query so the frontend can display the actual clarified query
            if rewritten:
                step_details["rewritten_query"] = rewritten
            if intent:
                step_details["intent"] = intent

            formatted_step["details"] = step_details

        elif name == "Query Routing":
            route = str(details.get("route", "")).lower()
            reason = details.get("reason", "Routing decision completed")
            route_label = {
                "knowledge_base": "knowledge base documents",
                "web_search": "web sources",
                "hybrid": "both knowledge base and web sources",
            }.get(route, route or "the best available source")

            formatted_step["details"] = {
                "title": "Route the task",
                "summary": f"Selected {route_label} for this query",
                "highlights": [reason],
                "route": route or "unknown",
                "reason": reason,
            }

        elif name in {"Knowledge Base Retrieval", "Web Search", "Hybrid Retrieval", "Web Supplementation"}:
            kb_docs = details.get("documents_retrieved", details.get("kb_documents", 0))
            web_sources = details.get("sources_found", details.get("web_sources", 0))
            doc_highlights = details.get("highlights", [])
            total_sources = kb_docs + web_sources

            # Prefer actual source snippets over generic count messages
            display_highlights = []
            if doc_highlights:
                display_highlights.extend(doc_highlights[:6])
            else:
                if kb_docs:
                    display_highlights.append(f"Found {kb_docs} relevant document(s) from knowledge base")
                if web_sources:
                    display_highlights.append(f"Found {web_sources} relevant web source(s)")
            if not display_highlights:
                display_highlights.append("Retrieved supporting information for answer generation")

            formatted_step["details"] = {
                "title": "Retrieve information",
                "summary": f"Found {total_sources} relevant source(s)" if total_sources else "Collected evidence to answer the question",
                "highlights": display_highlights,
                "documents_retrieved": total_sources,
            }

        elif name in {"Answer Generation", "Answer Synthesis"}:
            source = details.get("source") or details.get("method") or "available evidence"
            answer_summary = details.get("summary", "")

            display_highlights = []
            if answer_summary:
                display_highlights.append(answer_summary)

            formatted_step["details"] = {
                "title": "Draft the answer",
                "summary": f"Generated answer from {source}",
                "highlights": display_highlights or ["Composed a response based on retrieved information"],
                "source": source,
            }

        elif name == "Answer Validation":
            grounded = details.get("is_grounded")
            confidence = details.get("confidence")
            if grounded is True:
                validation_summary = "Verified that the answer is grounded in facts from the knowledge base"
            elif grounded is False:
                validation_summary = "Answer may contain claims not fully supported by sources"
            elif status == "skipped":
                validation_summary = "Quality check skipped for speed"
            else:
                validation_summary = "Checked answer grounding against retrieved sources"

            step_details: Dict[str, Any] = {
                "title": "Validate answer quality",
                "summary": validation_summary,
            }
            if grounded is not None:
                step_details["is_grounded"] = grounded
            if confidence is not None:
                step_details["confidence"] = confidence

            formatted_step["details"] = step_details

        elif name == "Fallback Decision":
            formatted_step["details"] = {
                "title": "Adjust strategy",
                "summary": "Switched to an alternative retrieval strategy",
                "highlights": [details.get("reason", "Fallback applied")],
            }

        else:
            formatted_step["details"] = {
                "title": name,
                "summary": "Processing step completed",
                "highlights": ["Step finished"],
            }

        formatted_steps.append(formatted_step)

    return formatted_steps


def create_timeout_response(query: str, steps: List[AgentStep], total_time_ms: float) -> Dict[str, Any]:
    """
    Create a timeout response when processing exceeds time limit.
    
    Args:
        query: Original user query
        steps: List of completed agent steps
        total_time_ms: Total processing time in milliseconds
        
    Returns:
        Timeout response dictionary
    """
    return {
        "answer": "Your query is taking longer than expected to process. Please try simplifying your question or try again later.",
        "sources": [],
        "error": "Request timeout",
        "metadata": {
            "original_query": query,
            "total_time_ms": round(total_time_ms, 2),
            "timeout_exceeded": True,
        },
        "reasoning_steps": [asdict(s) for s in steps],
    }
