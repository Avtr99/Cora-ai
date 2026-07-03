"""
Test suite for the post-generation answer relevance check (Layer 4).

Covers:
1. The domain-agnostic relevance prompt (no hardcoded VCM examples that
   bias the judge, source titles included when provided)
2. AnswerValidator.check_relevance passing source titles into the prompt
3. extract_source_titles helper (dedup, cleaning, cap)
4. check_answer_relevance pass-through including backwards compatibility
   with validators that don't accept source_titles
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.agents.validator import AnswerValidator, RELEVANCE_CHECK_PROMPT
from src.agents.route_processor_utils import (
    check_answer_relevance,
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
    assert "Source documents the answer was grounded in" in prompt


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
    assert "Source documents the answer was grounded in" not in prompt


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
