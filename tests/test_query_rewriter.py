"""
Test suite for optimized query rewriter with few-shot examples.

Tests the improved query rewriter's ability to:
1. Fix typos and expand acronyms
2. Extract metadata filters using field=value syntax
3. Generate sub-queries for complex requests
4. Handle edge cases gracefully
"""

import pytest
from unittest.mock import Mock, AsyncMock

from src.agents.query_rewriter import QueryRewriterAgent


@pytest.fixture
def mock_llm():
    """Create a mock LLMClient with generate_text."""
    llm = Mock()
    llm.generate_text = AsyncMock()
    llm.model_main = "test-model"
    llm.model_lite = "test-model-lite"
    return llm


@pytest.fixture
def rewriter(mock_llm):
    """Create a QueryRewriterAgent instance with mocked LLM client."""
    return QueryRewriterAgent(mock_llm, model_name="test-model")


@pytest.mark.asyncio
async def test_typo_correction_and_acronym_expansion(rewriter, mock_llm):
    """Test that the rewriter fixes typos and expands acronyms."""
    mock_llm.generate_text.return_value = (
        '{"rewritten_query": "current market price of REDD+ carbon credits in Brazil", '
        '"sub_queries": ["latest REDD+ credit prices Brazil"], '
        '"detected_intent": "pricing_inquiry", '
        '"corrections_made": ["Fixed typo: currnt -> current", "Expanded: red plus -> REDD+"]}'
    )

    result = await rewriter.rewrite("currnt price of red plus credits in brazil")

    assert result["rewritten_query"] == "current market price of REDD+ carbon credits in Brazil"
    assert "Fixed typo: currnt -> current" in result["corrections_made"]
    assert "Expanded: red plus -> REDD+" in result["corrections_made"]
    assert result["detected_intent"] == "pricing_inquiry"


@pytest.mark.asyncio
async def test_metadata_filter_extraction(rewriter, mock_llm):
    """Test that the rewriter adds field=value filters for structured queries."""
    mock_llm.generate_text.return_value = (
        '{"rewritten_query": "details and requirements of Verra methodology VM0048 document_id=VM0048", '
        '"sub_queries": [], '
        '"detected_intent": "methodology_research", '
        '"corrections_made": ["Added document_id filter for precise retrieval"]}'
    )

    result = await rewriter.rewrite("methodology vm0048 details")

    assert "document_id=VM0048" in result["rewritten_query"]
    assert result["detected_intent"] == "methodology_research"


@pytest.mark.asyncio
async def test_registry_filter_with_quotes(rewriter, mock_llm):
    """Test that the rewriter correctly quotes multi-word filter values."""
    mock_llm.generate_text.return_value = (
        '{"rewritten_query": "Gold Standard certified carbon offset projects in Kenya registry=\\"Gold Standard\\"", '
        '"sub_queries": [], '
        '"detected_intent": "project_search", '
        '"corrections_made": ["Added registry filter", "Expanded GS -> Gold Standard"]}'
    )

    result = await rewriter.rewrite("gold standard projects in kenya")

    assert 'registry="Gold Standard"' in result["rewritten_query"] or 'registry=\\"Gold Standard\\"' in result["rewritten_query"]
    assert "Gold Standard" in result["rewritten_query"]


@pytest.mark.asyncio
async def test_concept_explanation_no_filters(rewriter, mock_llm):
    """Test that concept explanation queries don't add unnecessary filters."""
    mock_llm.generate_text.return_value = (
        '{"rewritten_query": "what is Monitoring, Reporting and Verification (MRV) process in carbon markets", '
        '"sub_queries": [], '
        '"detected_intent": "concept_explanation", '
        '"corrections_made": ["Expanded acronym: MRV -> Monitoring, Reporting and Verification"]}'
    )

    result = await rewriter.rewrite("what is MRV process")

    assert "Monitoring, Reporting and Verification" in result["rewritten_query"]
    assert "=" not in result["rewritten_query"]  # No filters for concept queries
    assert result["detected_intent"] == "concept_explanation"


@pytest.mark.asyncio
async def test_sub_query_generation(rewriter, mock_llm):
    """Test that complex queries generate appropriate sub-queries."""
    mock_llm.generate_text.return_value = (
        '{"rewritten_query": "current market price of REDD+ carbon credits in Brazil", '
        '"sub_queries": ["latest REDD+ credit prices Brazil", "historical REDD+ price trends Brazil"], '
        '"detected_intent": "pricing_inquiry", '
        '"corrections_made": ["Expanded: red plus -> REDD+"]}'
    )

    result = await rewriter.rewrite("red plus prices in brazil")

    assert len(result["sub_queries"]) > 0
    assert any("latest" in sq or "historical" in sq for sq in result["sub_queries"])


@pytest.mark.asyncio
async def test_empty_query_handling(rewriter, mock_llm):
    """Test that empty queries are handled gracefully."""
    result = await rewriter.rewrite("")

    assert result["rewritten_query"] == ""
    assert result["detected_intent"] == "empty query"
    assert result["corrections_made"] == []


@pytest.mark.asyncio
async def test_already_clear_query(rewriter, mock_llm):
    """Test that already clear queries are returned unchanged."""
    mock_llm.generate_text.return_value = (
        '{"rewritten_query": "What are the requirements for Gold Standard certification?", '
        '"sub_queries": [], '
        '"detected_intent": "certification_requirements", '
        '"corrections_made": []}'
    )

    result = await rewriter.rewrite("What are the requirements for Gold Standard certification?")

    assert result["corrections_made"] == []
    assert "Gold Standard" in result["rewritten_query"]


@pytest.mark.asyncio
async def test_fallback_on_llm_error(rewriter, mock_llm):
    """Test that the rewriter falls back gracefully on LLM errors."""
    mock_llm.generate_text.side_effect = Exception("API error")

    original_query = "test query"
    result = await rewriter.rewrite(original_query)

    assert result["rewritten_query"] == original_query
    assert result["detected_intent"] == "unknown"


@pytest.mark.asyncio
async def test_query_rewriter_with_chat_history(rewriter, mock_llm):
    """Test that QueryRewriter can accept and use chat history context."""
    mock_llm.generate_text.return_value = (
        '{"rewritten_query": "How old is Sundar Pichai?", '
        '"sub_queries": [], '
        '"detected_intent": "informational", '
        '"corrections_made": ["Resolved coreference: he -> Sundar Pichai"]}'
    )

    chat_history = [
        {"role": "user", "content": "Who is the CEO of Google?"},
        {"role": "assistant", "content": "Sundar Pichai is the CEO of Google."},
    ]

    result = await rewriter.rewrite("How old is he?", chat_history)

    assert result["rewritten_query"] == "How old is Sundar Pichai?"
    # Verify generate_text was called with a prompt (the contents)
    mock_llm.generate_text.assert_called_once()
    call_args = mock_llm.generate_text.call_args
    # The prompt is the first positional arg
    assert call_args.args[0] is not None or call_args.kwargs.get("prompt") is not None


@pytest.mark.asyncio
async def test_query_rewriter_without_chat_history(rewriter, mock_llm):
    """Test backward compatibility when chat_history is omitted."""
    mock_llm.generate_text.return_value = (
        '{"rewritten_query": "What is the Voluntary Carbon Market?", '
        '"sub_queries": [], '
        '"detected_intent": "concept_explanation", '
        '"corrections_made": ["Expanded: VCM -> Voluntary Carbon Market"]}'
    )

    result = await rewriter.rewrite("What is the VCM?")

    assert result["rewritten_query"] == "What is the Voluntary Carbon Market?"
    assert "Voluntary Carbon Market" in result["rewritten_query"]
