"""
Orchestrator Utilities

Utility functions for the RAG orchestrator:
- Timing breakdown
- Timeout extraction
- Time budget management
- Timeout checking
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .reasoning_formatter import AgentStep, create_timeout_response

logger = logging.getLogger(__name__)


def remaining_time_ms(max_total_time_ms: int, start_time: float) -> Optional[int]:
    """
    Get remaining orchestrator budget in milliseconds.
    
    Args:
        max_total_time_ms: Maximum total time budget in ms (0 or negative = unlimited)
        start_time: Start time from time.time()
        
    Returns:
        Remaining milliseconds, or None if unlimited.
        Returns 0 if elapsed time exceeds budget (expired).
        Returns at least 500ms when time remains (minimum floor).
    """
    if max_total_time_ms <= 0:
        return None
    elapsed_ms = int((time.time() - start_time) * 1000)
    if elapsed_ms >= max_total_time_ms:
        return 0  # Expired
    return max(max_total_time_ms - elapsed_ms, 500)


def build_timing_breakdown(steps: List[AgentStep]) -> Dict[str, float]:
    """
    Build per-stage timing map from recorded agent steps.
    
    Args:
        steps: List of AgentStep objects with timing info
        
    Returns:
        Dict mapping step name to duration in ms
    """
    durations: Dict[str, float] = {}
    for step in steps:
        rounded_duration = round(step.duration_ms or 0.0, 2)
        durations[step.name] = durations.get(step.name, 0) + rounded_duration
    return durations


def extract_timeout_reason(steps: List[AgentStep]) -> Optional[str]:
    """
    Extract structured timeout reason code from step details when present.
    
    Args:
        steps: List of AgentStep objects
        
    Returns:
        Timeout reason code or None
    """
    for step in reversed(steps):
        details = step.details or {}
        if details.get("timed_out"):
            if "web" in step.name.lower():
                return "web_timeout"
            if "retrieval" in step.name.lower():
                return "retrieval_timeout"
            return "step_timeout"
    return None


def build_step_summary(steps: List[AgentStep]) -> List[Dict[str, Any]]:
    """
    Build a summary list of steps for logging.
    
    Args:
        steps: List of AgentStep objects
        
    Returns:
        List of step summary dicts
    """
    return [
        {
            "name": step.name,
            "status": step.status,
            "duration_ms": step.duration_ms,
        }
        for step in steps
    ]


def check_timeout(
    deadline: Optional[float],
    start_time: float,
    steps: List[AgentStep],
    phase: str,
    query: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Check if timeout budget is exceeded. Returns timeout response if so, None otherwise.
    
    Args:
        deadline: Absolute deadline timestamp (None = no deadline)
        start_time: Pipeline start time
        steps: Current agent steps
        phase: Human-readable phase name for logging
        query: Original query for timeout response
        
    Returns:
        Timeout response dict if exceeded, None if within budget
    """
    if deadline is None:
        return None
    
    now = time.time()
    if now <= deadline:
        return None

    total_time_ms = round((now - start_time) * 1000, 2)
    logger.warning(
        "Query processing timeout after %s",
        phase,
        extra={
            "total_time_ms": total_time_ms,
            "timeout_reason": "budget_exceeded",
            "timing_breakdown": build_timing_breakdown(steps),
            "steps": build_step_summary(steps),
        },
    )
    return create_timeout_response(query, steps, total_time_ms)
