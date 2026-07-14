"""
Test suite for the post-generation answer relevance check (Layer 4).

Covers:
1. The domain-agnostic, retrieval-aware relevance prompt (no hardcoded VCM examples)
2. AnswerValidator.check_relevance passing source titles and source chunks into the prompt
3. extract_source_titles and extract_source_chunks helpers
4. check_answer_relevance pass-through including backwards compatibility
   with validators that don't accept source_titles or source_chunks
5. Config flag to disable the web-supplement relevance check without disabling validation
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.agents.streaming_handler import KBStreamingHandler
from src.agents.validator import AnswerValidator, RELEVANCE_CHECK_PROMPT
from src.agents.route_processor_utils import (
    check_answer_relevance,
    clean_source_display_name,
    extract_source_chunks,
    extract_source_titles,
)
from src.query_processing.fallback_llm_client import FallbackLLMClient

@pytest.fixture
def mock_llm():
    """Create a mock LLMClient with generate_text."""
    llm = Mock()
    llm.generate_text = AsyncMock()
    return llm

@pytest.fixture
def validator(mock_llm):
    """Create an AnswerValidator with mocked LLM client."""
    return AnswerValidator(mock_llm)

def test_relevance_prompt_has_no_hardcoded_domain_examples():
    """The prompt must not name specific methodologies/policies as examples.

    Hardcoded examples (e.g. 'VM0047 ARR' as the canonical off-topic answer)
    caused the lite judge to pattern-match and flag on-topic answers as
    irrelevant.
    """
    for term in ["VM0047", "CORSIA", "Just Transition", "Article 6", "VM####"]:
        assert term not in RELEVANCE_CHECK_PROMPT

@pytest.mark.asyncio
async def test_check_relevance_includes_source_titles(validator, mock_llm):
    """Source titles should be embedded in the prompt when provided."""
    mock_llm.generate_text.return_value = (
        '{"is_relevant": true, "confidence": 0.95, "reason": "Answer describes VM0047"}'
    )
    answer = "VM0047 is Verra's methodology for afforestation, reforestation and revegetation projects."
    result = await validator.check_relevance(
        "What is VM0047 methodology",
        answer,
        source_titles=["VM0047 ARR v1.0 1"],
    )
    assert result["is_relevant"] is True

    prompt = mock_llm.generate_text.call_args[0][0]
    assert "VM0047 ARR v1.0 1" in prompt
    assert "Source document titles" in prompt

@pytest.mark.asyncio
async def test_check_relevance_includes_source_chunks(validator, mock_llm):
    """Retrieved source chunks should be embedded in the relevance prompt."""
    mock_llm.generate_text.return_value = (
        '{"is_relevant": true, "confidence": 0.95, "reason": "Grounded in retrieved chunks"}'
    )
    answer = "VM0048 is a methodology for reducing emissions from deforestation."
    source_chunks = [
        "Source 1 (VM0048 REDD v1.0):\n"
        "VM0048 is a methodology that reduces emissions from deforestation and forest degradation."
    ]
    result = await validator.check_relevance(
        "What is VM0048?",
        answer,
        source_titles=["VM0048 REDD v1.0"],
        source_chunks=source_chunks,
    )
    assert result["is_relevant"] is True

    prompt = mock_llm.generate_text.call_args[0][0]
    assert "Retrieved source chunks" in prompt
    assert "reduces emissions from deforestation" in prompt
    assert "Source document titles" in prompt

@pytest.mark.asyncio
async def test_check_relevance_without_source_titles(validator, mock_llm):
    """No sources section should appear when titles are absent."""
    mock_llm.generate_text.return_value = (
        '{"is_relevant": false, "confidence": 0.9, "reason": "Different subject"}'
    )
    result = await validator.check_relevance(
        "What is the Just Transition Mechanism",
        "VM0047 is a methodology for afforestation and reforestation projects.",
    )
    assert result["is_relevant"] is False

    prompt = mock_llm.generate_text.call_args[0][0]
    assert "Source document titles" not in prompt
    assert "Retrieved source chunks" not in prompt

def test_extract_source_titles_dedup_and_clean():
    vector_results = {
        "metadatas": [
            {"source": "docs/VM0047_ARR_v1.0-1.pdf"},
            {"source": "docs/VM0047_ARR_v1.0-1.pdf"},
            {"title": "VCS Standard v4.5"},
            {},
            "not-a-dict",
        ]
    }
    titles = extract_source_titles(vector_results)
    assert titles == ["VM0047 ARR v1.0 1", "VCS Standard v4.5"]

def test_extract_source_titles_respects_cap():
    vector_results = {
        "metadatas": [{"source": f"doc_{i}.pdf"} for i in range(10)]
    }
    assert len(extract_source_titles(vector_results, max_titles=5)) == 5

def test_extract_source_titles_empty_results():
    assert extract_source_titles({}) == []
    assert extract_source_titles({"metadatas": []}) == []

def test_extract_source_chunks_uses_documents_and_metadata():
    vector_results = {
        "documents": [
            "VM0048 reduces emissions from deforestation and forest degradation.",
            "This is a second chunk from the same source.",
        ],
        "metadatas": [
            {"source": "docs/VM0048_ARR_v1.0-1.pdf"},
            {"source": "docs/VM0048_ARR_v1.0-1.pdf"},
        ],
    }
    chunks = extract_source_chunks(vector_results, max_chunks=5, max_chars_per_chunk=1000)
    assert len(chunks) == 2
    assert "VM0048 ARR v1.0 1" in chunks[0]
    assert "deforestation" in chunks[0]
    assert "Source 2" in chunks[1]

def test_extract_source_chunks_respects_limits():
    vector_results = {
        "documents": ["chunk" * 500 for _ in range(10)],
        "metadatas": [{} for _ in range(10)],
    }
    chunks = extract_source_chunks(vector_results, max_chunks=2, max_chars_per_chunk=20)
    assert len(chunks) == 2
    assert all(len(chunk) <= 40 for chunk in chunks)  # prefix + truncated text

def test_extract_source_chunks_empty_results():
    assert extract_source_chunks({}) == []
    assert extract_source_chunks({"documents": [], "metadatas": []}) == []

def test_clean_source_display_name_decodes_deeply_encoded_filename():
    assert clean_source_display_name("VM0048%252520Methodology.pdf") == "VM0048 Methodology"

class _Config:
    web_supplement_relevance_confidence_threshold = 0.8

def _make_llm(response_text: str):
    """Return a minimal fake LLM whose generate_text coroutine returns response_text."""
    llm = Mock()
    llm.generate_text = AsyncMock(return_value=response_text)
    return llm

@pytest.mark.asyncio
async def test_answer_validator_uses_explicit_relevance_model_override():
    """An explicit model_name_lite override is passed to the LLM."""
    llm = _make_llm('{"is_relevant": true, "confidence": 0.9, "reason": "on-topic"}')
    validator = AnswerValidator(llm, model_name="main-model", model_name_lite="custom-lite-model")
    await validator.check_relevance("What is X?", "X is a detailed concept with many important properties and applications in the relevant domain.")
    _, kwargs = llm.generate_text.call_args
    assert kwargs.get("model") == "custom-lite-model"

@pytest.mark.asyncio
async def test_answer_validator_defaults_to_client_model_relevance():
    """When model_name_lite is None, the client's model_relevance is used."""
    llm = _make_llm('{"is_relevant": true, "confidence": 0.9, "reason": "on-topic"}')
    llm.model_relevance = "provider-relevance-model"
    validator = AnswerValidator(llm, model_name="main-model")
    await validator.check_relevance("What is X?", "X is a detailed concept with many important properties and applications in the relevant domain.")
    _, kwargs = llm.generate_text.call_args
    assert kwargs.get("model") == "provider-relevance-model"

@pytest.mark.asyncio
async def test_answer_validator_defaults_to_none_when_client_has_no_relevance_model():
    """If the client has no model_relevance, model_name_lite stays None."""
    class PlainLLM:
        def __init__(self, response_text):
            self.generate_text = AsyncMock(return_value=response_text)

    llm = PlainLLM('{"is_relevant": true, "confidence": 0.9, "reason": "on-topic"}')
    validator = AnswerValidator(llm, model_name="main-model")
    await validator.check_relevance("What is X?", "X is a detailed concept with many important properties and applications in the relevant domain.")
    _, kwargs = llm.generate_text.call_args
    assert kwargs.get("model") is None

@pytest.mark.asyncio
async def test_check_answer_relevance_passes_source_titles():
    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": False, "confidence": 0.9, "reason": "off-topic",
    })
    is_irrelevant, reason = await check_answer_relevance(
        validator, _Config(), "query", "answer",
        source_titles=["Doc A"],
    )
    assert is_irrelevant is True
    assert reason == "off-topic"
    validator.check_relevance.assert_awaited_once_with(
        "query", "answer", source_titles=["Doc A"],
    )

@pytest.mark.asyncio
async def test_check_answer_relevance_legacy_validator_without_titles_kwarg():
    """Validators without the source_titles kwarg must still work."""
    class LegacyValidator:
        def __init__(self):
            self.calls = []

        async def check_relevance(self, query, answer):
            self.calls.append((query, answer))
            return {"is_relevant": True, "confidence": 0.9, "reason": "on-topic"}

    validator = LegacyValidator()
    is_irrelevant, reason = await check_answer_relevance(
        validator, _Config(), "query", "answer",
        source_titles=["Doc A"],
    )
    assert is_irrelevant is False
    assert validator.calls == [("query", "answer")]

@pytest.mark.asyncio
async def test_check_answer_relevance_below_confidence_threshold():
    """Low-confidence irrelevance verdicts must not trigger fallback."""
    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": False, "confidence": 0.5, "reason": "unsure",
    })
    is_irrelevant, _ = await check_answer_relevance(
        validator, _Config(), "query", "answer",
    )
    assert is_irrelevant is False

@pytest.mark.asyncio
async def test_check_answer_relevance_keeps_on_topic_grounded_answer():
    """A grounded, on-topic KB answer is not marked irrelevant."""
    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": True, "confidence": 0.95, "reason": "grounded in source",
    })
    source_chunks = [
        "Source 1 (VM0048 Reducing Emissions from Deforestation and Forest Degradation v1.0):\n"
        "VM0048 is a methodology that reduces emissions from deforestation and forest degradation."
    ]
    is_irrelevant, reason = await check_answer_relevance(
        validator,
        _Config(),
        "What is VM0048?",
        "VM0048 is Verra's methodology for reducing emissions from deforestation and forest degradation.",
        source_titles=["VM0048 Reducing Emissions from Deforestation and Forest Degradation v1.0"],
        source_chunks=source_chunks,
    )
    assert is_irrelevant is False
    assert reason == ""

@pytest.mark.asyncio
async def test_check_answer_relevance_keeps_named_standard_definition_in_kb():
    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": True, "confidence": 0.95, "reason": "grounded in source",
    })
    source_chunks = [
        "Source 1 (VCS Standard v4.7):\n"
        "The VCS Standard sets the rules and requirements for projects in the Verified Carbon Standard program."
    ]
    is_irrelevant, _ = await check_answer_relevance(
        validator,
        _Config(),
        "What is the VCS Standard?",
        "The VCS Standard sets the rules and requirements for projects in the Verified Carbon Standard program.",
        source_titles=["VCS Standard v4.7"],
        source_chunks=source_chunks,
    )
    assert is_irrelevant is False

@pytest.mark.asyncio
async def test_check_answer_relevance_passes_source_chunks():
    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": True, "confidence": 0.95, "reason": "grounded",
    })
    source_chunks = ["Source 1 (Doc A):\nSome source text."]
    await check_answer_relevance(
        validator,
        _Config(),
        "query",
        "answer",
        source_titles=["Doc A"],
        source_chunks=source_chunks,
    )
    validator.check_relevance.assert_awaited_once_with(
        "query", "answer", source_titles=["Doc A"], source_chunks=source_chunks,
    )

@pytest.mark.asyncio
async def test_check_answer_relevance_disabled_by_config():
    """ENABLE_WEB_SUPPLEMENT_RELEVANCE_CHECK=false bypasses the check."""
    class _DisabledConfig:
        enable_web_supplement_relevance_check = False
        web_supplement_relevance_confidence_threshold = 0.8

    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": False, "confidence": 0.95, "reason": "off-topic",
    })
    is_irrelevant, reason = await check_answer_relevance(
        validator, _DisabledConfig(), "query", "answer",
    )
    assert is_irrelevant is False
    assert reason == ""
    validator.check_relevance.assert_not_awaited()

@pytest.mark.asyncio
async def test_check_answer_relevance_rejects_off_topic_answer_without_sources():
    """A high-confidence off-topic verdict still triggers fallback."""
    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": False, "confidence": 0.95, "reason": "No grounded source",
    })
    is_irrelevant, reason = await check_answer_relevance(
        validator,
        _Config(),
        "What is VM0048?",
        "VM0048 is a methodology for reducing emissions from deforestation.",
        source_titles=None,
    )
    assert is_irrelevant is True
    assert reason == "No grounded source"

@pytest.mark.asyncio
async def test_check_answer_relevance_rejects_same_document_but_wrong_detail():
    """An answer that mentions the queried entity but does not answer the detail is not relevant."""
    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": False, "confidence": 0.95, "reason": "Does not explain leakage calculations",
    })
    source_chunks = [
        "Source 1 (VM0048 Reducing Emissions from Deforestation and Forest Degradation v1.0):\n"
        "VM0048 is a methodology for reducing emissions from deforestation and forest degradation."
    ]
    is_irrelevant, reason = await check_answer_relevance(
        validator,
        _Config(),
        "How does VM0048 calculate leakage?",
        "VM0048 is a methodology for reducing emissions from deforestation.",
        source_titles=["VM0048 Reducing Emissions from Deforestation and Forest Degradation v1.0"],
        source_chunks=source_chunks,
    )
    assert is_irrelevant is True
    assert reason == "Does not explain leakage calculations"

def test_fallback_llm_client_model_relevance_returns_primary_model_name():
    """FallbackLLMClient.model_relevance must be a valid model name, not a
    concatenated observability string, because AnswerValidator passes it to
    generate_text(model=...).
    """
    primary = Mock()
    primary.model_main = "primary-main"
    primary.model_lite = "primary-lite"
    primary.model_relevance = "primary-relevance"
    fallback = Mock()
    fallback.model_main = "fallback-main"
    fallback.model_lite = "fallback-lite"
    fallback.model_relevance = "fallback-relevance"

    client = FallbackLLMClient(primary, fallback)
    assert client.model_relevance == "primary-relevance"
    assert client.model_main == "primary-main"
    assert client.model_lite == "primary-lite"


class _StreamingConfig:
    retrieval_threshold = 0.2
    kb_min_top_relevance_score = 0.4
    enable_web_search = True
    enable_web_supplement_relevance_check = True
    web_supplement_relevance_confidence_threshold = 0.8


class _StreamingRetriever:
    async def retrieve(self, **kwargs):
        return {
            "documents": ["The program requires accreditation for the applicable sectoral scope."],
            "metadatas": [{"title": "VCS Program Guide v4.4"}],
            "scores": [0.9],
        }


class _StreamingAnswerGenerator:
    def __init__(self, answer):
        self.answer = answer

    async def search_and_process_stream(self, query, vector_results):
        yield {"type": "token", "chunk": self.answer}
        yield {
            "type": "final",
            "result": {
                "answer": self.answer,
                "sources": ["VCS Program Guide v4.4"],
            },
        }


async def _collect_stream_events(
    handler,
    web_supplement_callback,
    emit_tokens=False,
    finalize_citations_callback=None,
):
    events = []
    async for event in handler.process_stream(
        query="VCS Program Guide accreditation requirements",
        original_query="What accreditation is required?",
        metadata_filters=None,
        steps=[],
        web_supplement_callback=web_supplement_callback,
        web_route_callback=AsyncMock(return_value={"answer": "web-only"}),
        emit_tokens=emit_tokens,
        finalize_citations_callback=finalize_citations_callback,
    ):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_tokens_false_keeps_relevant_streamed_kb_answer():
    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": True,
        "confidence": 0.95,
        "reason": "The answer directly addresses the question",
    })
    web_supplement = AsyncMock(return_value={"answer": "supplemented"})
    handler = KBStreamingHandler(
        _StreamingRetriever(),
        _StreamingAnswerGenerator("Applicable sectoral-scope accreditation is required."),
        Mock(),
        _StreamingConfig(),
        validator,
    )

    events = await _collect_stream_events(handler, web_supplement)

    final = next(event["result"] for event in events if event["type"] == "final")
    assert final["answer"] == "Applicable sectoral-scope accreditation is required."
    web_supplement.assert_not_awaited()
    validator.check_relevance.assert_awaited_once()


@pytest.mark.asyncio
async def test_tokens_false_supplements_explicit_streamed_non_answer():
    validator = Mock()
    validator.check_relevance = AsyncMock()
    web_supplement = AsyncMock(return_value={"answer": "supplemented"})
    handler = KBStreamingHandler(
        _StreamingRetriever(),
        _StreamingAnswerGenerator("Information not found, try rephrasing your question again."),
        Mock(),
        _StreamingConfig(),
        validator,
    )

    events = await _collect_stream_events(handler, web_supplement)

    final = next(event["result"] for event in events if event["type"] == "final")
    assert final["answer"] == "supplemented"
    web_supplement.assert_awaited_once()
    validator.check_relevance.assert_not_awaited()


@pytest.mark.asyncio
async def test_tokens_false_supplements_high_confidence_irrelevant_answer():
    validator = Mock()
    validator.check_relevance = AsyncMock(return_value={
        "is_relevant": False,
        "confidence": 0.95,
        "reason": "The answer does not address accreditation",
    })
    web_supplement = AsyncMock(return_value={"answer": "supplemented"})
    handler = KBStreamingHandler(
        _StreamingRetriever(),
        _StreamingAnswerGenerator("This document describes carbon project registration."),
        Mock(),
        _StreamingConfig(),
        validator,
    )

    events = await _collect_stream_events(handler, web_supplement)

    final = next(event["result"] for event in events if event["type"] == "final")
    assert final["answer"] == "supplemented"
    web_supplement.assert_awaited_once()
    validator.check_relevance.assert_awaited_once()


class _NonStreamingAnswerGenerator:
    def __init__(self, answer):
        self.answer = answer

    async def search_and_process(self, query, vector_results):
        return {
            "answer": self.answer,
            "sources": ["VCS Program Guide v4.4"],
        }


@pytest.mark.asyncio
async def test_tokens_true_non_answer_gate_supplements():
    """The emit_tokens=True buffer gate suppresses the non-answer token and supplements."""
    web_supplement = AsyncMock(return_value={"answer": "supplemented"})
    non_answer = "Information not found, try rephrasing your question again."
    handler = KBStreamingHandler(
        _StreamingRetriever(),
        _StreamingAnswerGenerator(non_answer),
        Mock(),
        _StreamingConfig(),
        validator=None,
    )

    events = await _collect_stream_events(handler, web_supplement, emit_tokens=True)

    token_chunks = [event["chunk"] for event in events if event["type"] == "token"]
    final = next(event["result"] for event in events if event["type"] == "final")
    assert final["answer"] == "supplemented"
    assert non_answer not in token_chunks
    assert token_chunks == ["supplemented"]
    web_supplement.assert_awaited_once()


@pytest.mark.asyncio
async def test_tokens_true_finalizes_citations_before_emit():
    """The late buffered token is emitted AFTER finalize_citations_callback renumbers the answer."""
    def _finalize(result, query):
        result["answer"] = result["answer"].replace("[cite:1]", "[cite:2]")

    finalize = Mock(side_effect=_finalize)
    web_supplement = AsyncMock(return_value={"answer": "supplemented"})
    handler = KBStreamingHandler(
        _StreamingRetriever(),
        _StreamingAnswerGenerator("Answer [cite:1]"),
        Mock(),
        _StreamingConfig(),
        validator=None,
    )

    events = await _collect_stream_events(
        handler,
        web_supplement,
        emit_tokens=True,
        finalize_citations_callback=finalize,
    )

    token = next((event["chunk"] for event in events if event["type"] == "token"), None)
    final = next(event["result"] for event in events if event["type"] == "final")
    assert token == "Answer [cite:2]"
    assert final["answer"] == "Answer [cite:2]"
    web_supplement.assert_not_awaited()
    finalize.assert_called_once()


@pytest.mark.asyncio
async def test_non_stream_fallback_relevant_finalizes_citations():
    """The non-stream fallback path finalizes citations before yielding the final result."""
    def _finalize(result, query):
        result["answer"] = result["answer"].replace("[cite:1]", "[cite:2]")

    finalize = Mock(side_effect=_finalize)
    web_supplement = AsyncMock(return_value={"answer": "supplemented"})
    handler = KBStreamingHandler(
        _StreamingRetriever(),
        _NonStreamingAnswerGenerator("Answer [cite:1]"),
        Mock(),
        _StreamingConfig(),
        validator=None,
    )

    events = await _collect_stream_events(
        handler,
        web_supplement,
        emit_tokens=True,
        finalize_citations_callback=finalize,
    )

    token = next((event["chunk"] for event in events if event["type"] == "token"), None)
    final = next(event["result"] for event in events if event["type"] == "final")
    assert token == "Answer [cite:2]"
    assert final["answer"] == "Answer [cite:2]"
    web_supplement.assert_not_awaited()
    finalize.assert_called_once()
    assert finalize.call_args.args[1] == "What accreditation is required?"


@pytest.mark.asyncio
async def test_non_stream_fallback_non_answer_supplements():
    """The non-stream fallback path supplements an explicit non-answer fallback."""
    web_supplement = AsyncMock(return_value={"answer": "supplemented"})
    non_answer = "Information not found, try rephrasing your question again."
    handler = KBStreamingHandler(
        _StreamingRetriever(),
        _NonStreamingAnswerGenerator(non_answer),
        Mock(),
        _StreamingConfig(),
        validator=None,
    )

    events = await _collect_stream_events(handler, web_supplement, emit_tokens=True)

    token_chunks = [event["chunk"] for event in events if event["type"] == "token"]
    final = next(event["result"] for event in events if event["type"] == "final")
    assert final["answer"] == "supplemented"
    assert non_answer not in token_chunks
    assert token_chunks == ["supplemented"]
    web_supplement.assert_awaited_once()
