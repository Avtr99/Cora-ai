"""Tests for reasoning step formatting and legacy-step upgrades.

Formatted steps carry a stable ``details.kind`` for frontend icon/message
mapping, user-facing titles, and ``details.sources`` on retrieval steps.
``upgrade_reasoning_steps`` normalizes steps cached by older deploys.
"""

from src.agents.reasoning_formatter import (
    AgentStep,
    format_reasoning_steps,
    upgrade_reasoning_steps,
)


def _details(step: dict) -> dict:
    return step["details"]


def test_every_step_kind_emitted():
    steps = [
        AgentStep(name="Query Rewriting", status="completed"),
        AgentStep(name="Query Routing", status="completed", details={"route": "knowledge_base"}),
        AgentStep(name="Knowledge Base Retrieval", status="completed", details={"documents_retrieved": 2}),
        AgentStep(name="Web Search", status="completed", details={"sources_found": 3}),
        AgentStep(name="Hybrid Retrieval", status="completed", details={"kb_documents": 1, "web_sources": 1}),
        AgentStep(name="Web Supplementation", status="completed", details={"sources_found": 1}),
        AgentStep(name="Fallback Decision", status="completed"),
        AgentStep(name="Answer Generation", status="completed"),
        AgentStep(name="Answer Validation", status="completed"),
        AgentStep(name="Mystery Step", status="completed"),
    ]
    formatted = format_reasoning_steps(steps)
    kinds = [_details(s)["kind"] for s in formatted]
    assert kinds == [
        "understand", "route", "search_kb", "search_web", "search_kb",
        "search_web", "fallback", "compose", "verify", "step",
    ]


def test_user_facing_titles():
    steps = [
        AgentStep(name="Query Rewriting", status="completed"),
        AgentStep(name="Query Routing", status="completed"),
        AgentStep(name="Knowledge Base Retrieval", status="completed", details={"documents_retrieved": 1}),
        AgentStep(name="Hybrid Retrieval", status="completed", details={"kb_documents": 1}),
        AgentStep(name="Web Supplementation", status="completed"),
        AgentStep(name="Answer Generation", status="completed"),
        AgentStep(name="Answer Validation", status="completed"),
        AgentStep(name="Fallback Decision", status="completed"),
    ]
    titles = [_details(s)["title"] for s in format_reasoning_steps(steps)]
    assert titles == [
        "Understand the question",
        "Route the question",
        "Search the knowledge base",
        "Search the knowledge base and web",
        "Also check the web",
        "Compose the answer",
        "Verify the answer",
        "Handle the fallback",
    ]


def test_retrieval_step_sources_mirrored_from_highlights():
    steps = [
        AgentStep(
            name="Knowledge Base Retrieval",
            status="completed",
            details={
                "documents_retrieved": 2,
                "highlights": ['ACM0003: "snippet one"', 'VM0048: "snippet two"'],
            },
        )
    ]
    details = _details(format_reasoning_steps(steps)[0])
    assert details["sources"] == ['ACM0003: "snippet one"', 'VM0048: "snippet two"']


def test_upgrade_adds_kind_and_current_titles_to_legacy_steps():
    legacy = [
        {
            "name": "Query Rewriting",
            "status": "completed",
            "duration_ms": 1,
            "details": {"title": "Clarify the question", "summary": "x", "highlights": []},
        },
        {
            "name": "Query Routing",
            "status": "completed",
            "duration_ms": 1,
            "details": {"title": "Route the task", "summary": "x", "highlights": []},
        },
        {
            "name": "Knowledge Base Retrieval",
            "status": "completed",
            "duration_ms": 1,
            "details": {
                "title": "Retrieve information",
                "summary": "x",
                "highlights": ['ACM0003: "excerpt"'],
            },
        },
        {
            "name": "Answer Generation",
            "status": "completed",
            "duration_ms": 1,
            "details": {"title": "Draft the answer", "summary": "x", "highlights": []},
        },
        {
            "name": "Answer Validation",
            "status": "completed",
            "duration_ms": 1,
            "details": {"title": "Validate answer quality", "summary": "x"},
        },
        {
            "name": "Fallback Decision",
            "status": "completed",
            "duration_ms": 1,
            "details": {"title": "Adjust strategy", "summary": "x"},
        },
    ]
    upgraded = upgrade_reasoning_steps(legacy)

    assert _details(upgraded[0])["kind"] == "understand"
    assert _details(upgraded[0])["title"] == "Understand the question"
    assert _details(upgraded[1])["title"] == "Route the question"
    assert _details(upgraded[2])["title"] == "Search the knowledge base"
    assert _details(upgraded[2])["sources"] == ['ACM0003: "excerpt"']
    assert _details(upgraded[3])["title"] == "Compose the answer"
    assert _details(upgraded[4])["title"] == "Verify the answer"
    assert _details(upgraded[5])["title"] == "Handle the fallback"


def test_upgrade_leaves_current_and_malformed_steps_untouched():
    current = [
        {
            "name": "Knowledge Base Retrieval",
            "status": "completed",
            "details": {
                "title": "Search the knowledge base",
                "kind": "search_kb",
                "sources": ["Doc A"],
            },
        },
        "not-a-dict",
        {"name": "No Details Step"},
    ]
    upgraded = upgrade_reasoning_steps(current)
    assert _details(upgraded[0])["kind"] == "search_kb"
    assert _details(upgraded[0])["sources"] == ["Doc A"]
    assert upgraded[1] == "not-a-dict"
    assert upgraded[2] == {"name": "No Details Step"}


def test_upgrade_non_list_passthrough():
    assert upgrade_reasoning_steps(None) is None
    assert upgrade_reasoning_steps("text") == "text"


def test_timeout_response_uses_formatted_steps():
    from src.agents.reasoning_formatter import create_timeout_response

    steps = [AgentStep(name="Query Routing", status="completed", details={"route": "web_search"})]
    result = create_timeout_response("q?", steps, 45000)
    step = result["reasoning_steps"][0]
    assert step["details"]["kind"] == "route"
    assert step["details"]["title"] == "Route the question"
    assert result["error_fallback"] is True
