"""Tests for the canonical citation pipeline.

Prompt indices are canonical: the number in ``<source index="N">`` is the
number the model cites and the number used to pick the displayed citation.
No renumbering happens anywhere downstream.
"""

from typing import Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.search_providers import SearchResult
from src.agents.web_search import WebSearchAgent, _hybrid_failure_result, parse_citations
from src.citations.check import check_citations
from src.citations.context import build_kb_context, citations_from_result
from src.citations.markers import deduplicate_inline_citations
from src.citations.citation_manager import CitationManager
from src.citations.models import Citation
from src.query_processing.base_rag_client import BaseRAGClient
from src.query_processing.fallback_answers import (
    NO_ANSWER_FOUND,
    SCOPE_REFUSAL_ANSWER,
    is_refusal,
)
from src.query_processing.post_processor import enforce_word_limit
from src.query_processing.streaming_rag_wrapper import StreamingRAGWrapper
from src.utils.cache import QueryCache


def _vector_results(names: List[str], scores: Optional[List[float]] = None) -> Dict:
    """Build vector_results with one document per name."""
    n = len(names)
    distances = [1.0 - s for s in scores] if scores else [0.2] * n
    return {
        "documents": [f"Chunk text for {name}." for name in names],
        "metadatas": [{"file_name": f"{name}.pdf"} for name in names],
        "distances": distances,
    }


# ---------------------------------------------------------------------------
# Canonical context builder
# ---------------------------------------------------------------------------


class TestBuildKBContext:
    def test_per_chunk_numbering_and_source_tags(self):
        ctx = build_kb_context(_vector_results(["a_doc", "b_doc", "c_doc"]))

        for i in (1, 2, 3):
            assert f'<source index="{i}"' in ctx.text
        assert [c.index for c in ctx.citations] == [1, 2, 3]
        assert all(c.marker_type == "knowledge_base" for c in ctx.citations)

    def test_snippet_is_the_chunks_own_text(self):
        ctx = build_kb_context(_vector_results(["a_doc", "b_doc"]))
        assert ctx.citations[1].content_snippet == "Chunk text for b_doc."

    def test_snippet_strips_legacy_title_header(self):
        """Legacy chunks prepend ``title\\n\\n`` — the snippet must lead with
        the body, not the repeated title."""
        vector_results = {
            "documents": ["VM0048: Monitoring\n\nThe methodology defines X."],
            "metadatas": [{"title": "VM0048: Monitoring", "file_name": "a.pdf"}],
            "distances": [0.2],
        }
        ctx = build_kb_context(vector_results)
        assert ctx.citations[0].content_snippet == "The methodology defines X."

    def test_snippet_strips_filename_header(self):
        """Heading-less chunks fall back to ``original_filename\\n\\n``."""
        vector_results = {
            "documents": ["report.pdf\n\nBody text here."],
            "metadatas": [{"original_filename": "report.pdf"}],
            "distances": [0.2],
        }
        ctx = build_kb_context(vector_results)
        assert ctx.citations[0].content_snippet == "Body text here."

    def test_snippet_strips_contextualized_heading_ancestry(self):
        """New chunks carry the heading ancestry (``title\\nsection\\nbody``);
        ``section`` metadata holds the same path joined by ``" / "``."""
        vector_results = {
            "documents": [
                "VM0015: Avoided Deforestation\nParameters\n\nparameter 0, Unit = t."
            ],
            "metadatas": [
                {
                    "title": "VM0015: Avoided Deforestation",
                    "section": "VM0015: Avoided Deforestation / Parameters",
                }
            ],
            "distances": [0.2],
        }
        ctx = build_kb_context(vector_results)
        assert ctx.citations[0].content_snippet == "parameter 0, Unit = t."

    def test_snippet_keeps_leading_text_that_is_not_the_header(self):
        """Body text that merely shares words with the title is untouched."""
        vector_results = {
            "documents": ["VM0048 is widely used.\n\nMore detail."],
            "metadatas": [{"title": "VM0048: Monitoring"}],
            "distances": [0.2],
        }
        ctx = build_kb_context(vector_results)
        assert ctx.citations[0].content_snippet.startswith("VM0048 is widely used.")

    def test_empty_documents_consume_no_index(self):
        vector_results = {
            "documents": ["Real content", "", "Other content"],
            "metadatas": [{"file_name": "a.pdf"}, {"file_name": "b.pdf"}, {"file_name": "c.pdf"}],
            "distances": [0.2, 0.2, 0.2],
        }
        ctx = build_kb_context(vector_results)
        assert [c.index for c in ctx.citations] == [1, 2]

    def test_duplicate_names_keep_distinct_indices(self):
        ctx = build_kb_context(_vector_results(["same_doc", "same_doc"]))
        assert [c.index for c in ctx.citations] == [1, 2]

    def test_structured_mode_citation_has_no_index(self):
        vector_results = {
            "documents": ["dataset payload"],
            "metadatas": [{"file_name": "dataset.csv", "title": "Credit Dataset"}],
            "distances": [0.1],
            "structured_mode": "enumerate",
        }
        ctx = build_kb_context(vector_results)
        assert len(ctx.citations) == 1
        assert ctx.citations[0].index is None
        assert ctx.text == "dataset payload"


# ---------------------------------------------------------------------------
# check_citations
# ---------------------------------------------------------------------------


class TestCheckCitations:
    def test_out_of_range_id(self):
        errors = check_citations("See [cite_kb: 9].", {"knowledge_base": {1, 2, 3}})
        assert errors == ["[cite_kb: 9] is not a source in the reference data."]

    def test_web_out_of_range_message(self):
        errors = check_citations("See [Web, cite: 7].", {"web": {1, 2}})
        assert errors == ["[Web, cite: 7] is not a source in the search results."]

    def test_fenced_code_ignored(self):
        answer = "Example:\n```\n[cite_kb: 9]\n```\nDone."
        errors = check_citations(answer, {"knowledge_base": {1}})
        assert errors == ["The answer has no citations."]

    def test_inline_code_ignored(self):
        answer = "Write `[cite_kb: 9]` to cite."
        errors = check_citations(answer, {"knowledge_base": {1}})
        assert errors == ["The answer has no citations."]

    def test_markdown_link_is_not_a_marker(self):
        answer = "See the [Verra registry](https://verra.org) [cite_kb: 1]."
        assert check_citations(answer, {"knowledge_base": {1}}) == []

    def test_no_citations_is_an_error(self):
        errors = check_citations("Plain text.", {"knowledge_base": {1}})
        assert errors == ["The answer has no citations."]

    def test_non_answer_returns_no_errors(self):
        assert check_citations(NO_ANSWER_FOUND, {"knowledge_base": {1}}) == []

    def test_scope_refusal_returns_no_errors(self):
        # A refusal must not be retried into NO_ANSWER_FOUND — that would
        # trigger web supplementation and answer the off-scope question.
        assert check_citations(SCOPE_REFUSAL_ANSWER, {"knowledge_base": {1}}) == []

    def test_valid_multi_marker(self):
        assert check_citations("x [cite_kb: 1, 2].", {"knowledge_base": {1, 2}}) == []


# ---------------------------------------------------------------------------
# search_and_process: marker preservation and retry
# ---------------------------------------------------------------------------


class _StubCache:
    def __init__(self):
        self.stored: List[Dict] = []

    async def get_result(self, query, context_fingerprint=None):
        return None

    async def set_result(self, query, result, context_fingerprint=None, ttl=None):
        self.stored.append(result)

    async def invalidate(self, query, context_fingerprint=None):
        return True


class _StubRAGClient(BaseRAGClient):
    """BaseRAGClient stub whose generations come from a canned answer list."""

    def __init__(self, answers: List[str]):
        super().__init__()
        self._answers = list(answers)
        self.prompts: List[str] = []

    @property
    def circuit(self):
        return None

    @property
    def model_main(self) -> str:
        return "stub-main"

    @property
    def model_lite(self) -> str:
        return "stub-lite"

    @property
    def model_relevance(self) -> str:
        return "stub-lite"

    async def _generate_for_rag(self, prompt: str) -> Tuple[str, Dict[str, int]]:
        self.prompts.append(prompt)
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        return answer, {"tokens_in": 10, "tokens_out": 5}

    async def generate_text(self, prompt: str, **kwargs) -> str:
        self.prompts.append(prompt)
        answer = self._answers.pop(0) if len(self._answers) > 1 else self._answers[0]
        return answer


@pytest.fixture()
def stub_query_cache(monkeypatch):
    cache = _StubCache()
    monkeypatch.setattr(
        "src.query_processing.base_rag_client.query_cache", cache
    )
    monkeypatch.setattr(
        "src.query_processing.streaming_rag_wrapper.query_cache", cache
    )
    return cache


class TestSearchAndProcessMarkers:
    """Answers that pass the citation check come back byte-for-byte."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "answer",
        [
            "Credits were deducted [cite_kb: 1, 2].",
            "Credits were deducted [Knowledge Base, cite: 1].",
            "See the [Verra registry](https://verra.org) [cite_kb: 1].",
            "The module [VM0007] text applies [cite_kb: 1].",
        ],
    )
    async def test_valid_answers_return_unchanged(self, stub_query_cache, answer):
        client = _StubRAGClient([answer])
        result = await client.search_and_process(
            "carbon credits", _vector_results(["doc_a", "doc_b"])
        )

        assert result["answer"] == answer
        assert len(client.prompts) == 1

    @pytest.mark.asyncio
    async def test_context_citations_attached_to_result(self, stub_query_cache):
        client = _StubRAGClient(["Cited [cite_kb: 2]."])
        result = await client.search_and_process(
            "carbon credits", _vector_results(["doc_a", "doc_b", "doc_c"])
        )

        assert result["context_citations"][1]["index"] == 2
        ctx_citations = citations_from_result(result)
        assert [c.index for c in ctx_citations] == [1, 2, 3]
        # context_citations is popped by the helper
        assert "context_citations" not in result

    @pytest.mark.asyncio
    async def test_cached_result_served_without_generation(self, stub_query_cache):
        first_client = _StubRAGClient(["Cited [cite_kb: 1]."])
        await first_client.search_and_process(
            "carbon credits", _vector_results(["doc_a"])
        )
        cached = stub_query_cache.stored[0]

        class _HitCache(_StubCache):
            async def get_result(self, query, context_fingerprint=None):
                return cached

        second_client = _StubRAGClient(["never generated"])
        import src.query_processing.base_rag_client as brc

        original = brc.query_cache
        brc.query_cache = _HitCache()
        try:
            result = await second_client.search_and_process(
                "carbon credits", _vector_results(["doc_a"])
            )
        finally:
            brc.query_cache = original

        assert len(second_client.prompts) == 0
        assert result["answer"] == "Cited [cite_kb: 1]."
        assert result["context_citations"][0]["index"] == 1


class TestCitationRetry:
    @pytest.mark.asyncio
    async def test_retry_once_on_invalid_marker(self, stub_query_cache):
        client = _StubRAGClient([
            "Bad cite [cite_kb: 9].",
            "Good cite [cite_kb: 2].",
        ])
        result = await client.search_and_process(
            "carbon credits", _vector_results(["a", "b", "c"])
        )

        assert result["answer"] == "Good cite [cite_kb: 2]."
        assert len(client.prompts) == 2
        assert "<citation_correction>" in client.prompts[1]
        # Usage from both calls is summed.
        assert result["meta"]["tokens_in"] == 20
        assert result["meta"]["tokens_out"] == 10

    @pytest.mark.asyncio
    async def test_both_attempts_invalid_returns_no_answer(self, stub_query_cache):
        client = _StubRAGClient([
            "Bad cite [cite_kb: 9].",
            "Still bad [cite_kb: 8].",
        ])
        result = await client.search_and_process(
            "carbon credits", _vector_results(["a", "b", "c"])
        )

        assert result["answer"] == NO_ANSWER_FOUND
        assert len(client.prompts) == 2

    @pytest.mark.asyncio
    async def test_no_citations_triggers_retry(self, stub_query_cache):
        client = _StubRAGClient([
            "No markers here.",
            "Fixed [cite_kb: 1].",
        ])
        result = await client.search_and_process(
            "carbon credits", _vector_results(["a"])
        )

        assert result["answer"] == "Fixed [cite_kb: 1]."
        assert len(client.prompts) == 2


# ---------------------------------------------------------------------------
# Streaming wrapper: drop invalid ids, no retry
# ---------------------------------------------------------------------------


class _StubStreamClient(BaseRAGClient):
    def __init__(self, chunks: List[str]):
        super().__init__()
        self._chunks = chunks
        self.calls = 0

    @property
    def circuit(self):
        return None

    @property
    def model_main(self) -> str:
        return "stub-main"

    @property
    def model_lite(self) -> str:
        return "stub-lite"

    @property
    def model_relevance(self) -> str:
        return "stub-lite"

    async def generate_text_stream(self, prompt: str):
        self.calls += 1
        for chunk in self._chunks:
            yield chunk

    async def generate_text(self, prompt: str, **kwargs) -> str:
        return ""

    async def _generate_for_rag(self, prompt: str):
        raise NotImplementedError


async def _collect_stream(wrapper, query, vector_results) -> Tuple[List[str], Dict]:
    tokens: List[str] = []
    final: Dict = {}
    async for event in wrapper.search_and_process_stream(query, vector_results):
        if event["type"] == "token":
            tokens.append(event["chunk"])
        elif event["type"] == "final":
            final = event["result"]
    return tokens, final


class TestStreamingWrapper:
    @pytest.mark.asyncio
    async def test_invalid_ids_dropped_no_retry(self, stub_query_cache):
        chunks = ["Part one [cite_kb: 1] ", "and bad [cite_kb: 9] end."]
        client = _StubStreamClient(chunks)
        wrapper = StreamingRAGWrapper(base_client=client)

        tokens, result = await _collect_stream(
            wrapper, "carbon credits", _vector_results(["doc_a", "doc_b"])
        )

        assert client.calls == 1  # no retry — tokens were already sent
        assert tokens == chunks  # streamed text is untouched
        assert "[cite_kb: 1]" in result["answer"]
        assert "[cite_kb: 9]" not in result["answer"]

    @pytest.mark.asyncio
    async def test_stream_result_carries_context_citations(self, stub_query_cache):
        client = _StubStreamClient(["Answer [cite_kb: 1]."])
        wrapper = StreamingRAGWrapper(base_client=client)

        _, result = await _collect_stream(
            wrapper, "carbon credits", _vector_results(["doc_a"])
        )

        assert result["context_citations"][0]["index"] == 1


# ---------------------------------------------------------------------------
# Web search agent
# ---------------------------------------------------------------------------


def _web_results(n: int) -> List[SearchResult]:
    return [
        SearchResult(
            id=f"source_{i}",
            title=f"Web Result {i}",
            url=f"https://example.com/{i}",
            content=f"Web content {i}",
        )
        for i in range(1, n + 1)
    ]


# JSON the scope gate returns for an in-domain query — every test below
# prepends it because _in_scope() consumes the first generate_text call.
_IN_SCOPE = '{"in_scope": true, "reasoning": "sustainability"}'


class TestWebSearchAgent:
    @pytest.mark.asyncio
    async def test_retry_once_on_invalid_web_marker(self):
        llm = MagicMock()
        llm.generate_text = AsyncMock(
            side_effect=[_IN_SCOPE, "Bad [Web, cite: 9].", "Good [Web, cite: 2]."]
        )
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(3))
        agent = WebSearchAgent(llm, search_provider=provider)

        result = await agent.search("market news")

        assert result["answer"] == "Good [Web, cite: 2]."
        assert result["grounded"] is True
        assert llm.generate_text.await_count == 3
        assert "<citation_correction>" in llm.generate_text.await_args_list[2].args[0]

    @pytest.mark.asyncio
    async def test_both_attempts_invalid_returns_no_answer(self):
        llm = MagicMock()
        llm.generate_text = AsyncMock(
            side_effect=[_IN_SCOPE, "Bad [Web, cite: 9].", "Still bad [Web, cite: 8]."]
        )
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(3))
        agent = WebSearchAgent(llm, search_provider=provider)

        result = await agent.search("market news")

        assert result["answer"] == NO_ANSWER_FOUND
        assert result["sources"] == []
        assert result["grounded"] is False
        assert llm.generate_text.await_count == 3

    @pytest.mark.asyncio
    async def test_hybrid_retry_then_failure_result(self):
        llm = MagicMock()
        llm.generate_text = AsyncMock(
            side_effect=[_IN_SCOPE, "Bad [cite_kb: 9].", "Still bad [cite_kb: 9]."]
        )
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(2))
        agent = WebSearchAgent(llm, search_provider=provider)

        kb = build_kb_context(_vector_results(["kb_doc"]))
        result = await agent.search_with_kb_context("market news", kb=kb)

        expected = _hybrid_failure_result(kb.sources)
        assert result == expected
        assert llm.generate_text.await_count == 3

    @pytest.mark.asyncio
    async def test_hybrid_prompt_has_full_tagged_kb_context(self):
        llm = MagicMock()
        llm.generate_text = AsyncMock(
            side_effect=[_IN_SCOPE, "Hybrid answer [Web, cite: 1] [cite_kb: 1]."]
        )
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(1))
        agent = WebSearchAgent(llm, search_provider=provider)

        # A long KB context must not be truncated to 2000 chars.
        long_doc = "kb body " * 600  # ~4200 chars
        vector_results = {
            "documents": [long_doc, "second chunk"],
            "metadatas": [{"file_name": "kb1.pdf"}, {"file_name": "kb2.pdf"}],
            "distances": [0.2, 0.3],
        }
        kb = build_kb_context(vector_results)

        result = await agent.search_with_kb_context("market news", kb=kb)

        prompt = llm.generate_text.await_args_list[1].args[0]
        assert '<source index="1"' in prompt
        assert '<source index="2"' in prompt
        assert long_doc in prompt  # full context, no 2000-char cut
        assert result["grounded"] is True


# ---------------------------------------------------------------------------
# Scope gate: out-of-domain queries are refused before the provider is called
# ---------------------------------------------------------------------------


class TestScopeGate:
    @pytest.mark.asyncio
    async def test_out_of_scope_query_refused_without_web_search(self):
        llm = MagicMock()
        llm.generate_text = AsyncMock(
            return_value='{"in_scope": false, "reasoning": "recipe"}'
        )
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(3))
        agent = WebSearchAgent(llm, search_provider=provider)

        result = await agent.search("best chocolate cake recipe")

        assert is_refusal(result["answer"])
        assert result["answer"] == SCOPE_REFUSAL_ANSWER
        assert result["grounded"] is False
        provider.search.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_refusal_is_cached_for_repeat_queries(self):
        llm = MagicMock()
        llm.generate_text = AsyncMock(return_value='{"in_scope": false}')
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(3))
        agent = WebSearchAgent(llm, search_provider=provider)

        first = await agent.search("best chocolate cake recipe")
        second = await agent.search("best chocolate cake recipe")

        assert is_refusal(second["answer"])
        assert first["answer"] == second["answer"]
        assert llm.generate_text.await_count == 1

    @pytest.mark.asyncio
    async def test_sustainability_query_outside_vcm_is_in_scope(self):
        llm = MagicMock()
        llm.generate_text = AsyncMock(
            side_effect=[_IN_SCOPE, "Scope 3 covers value-chain emissions [Web, cite: 1]."]
        )
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(1))
        agent = WebSearchAgent(llm, search_provider=provider)

        result = await agent.search("what are scope 3 emissions?")

        assert result["answer"] == "Scope 3 covers value-chain emissions [Web, cite: 1]."
        provider.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_gate_exception_fails_open(self):
        llm = MagicMock()
        llm.generate_text = AsyncMock(
            side_effect=[RuntimeError("lite model down"), "OK [Web, cite: 1]."]
        )
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(1))
        agent = WebSearchAgent(llm, search_provider=provider)

        result = await agent.search("carbon market news")

        assert result["answer"] == "OK [Web, cite: 1]."
        provider.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_gate_unparseable_fails_open(self):
        llm = MagicMock()
        llm.generate_text = AsyncMock(
            side_effect=["not json at all", "OK [Web, cite: 1]."]
        )
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(1))
        agent = WebSearchAgent(llm, search_provider=provider)

        result = await agent.search("carbon market news")

        assert result["answer"] == "OK [Web, cite: 1]."
        provider.search.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kb_context_path_is_also_gated(self):
        """The supplement path reaches search_with_kb_context directly —
        it must apply the same domain gate."""
        llm = MagicMock()
        llm.generate_text = AsyncMock(return_value='{"in_scope": false}')
        provider = MagicMock()
        provider.search = AsyncMock(return_value=_web_results(2))
        agent = WebSearchAgent(llm, search_provider=provider)

        kb = build_kb_context(_vector_results(["kb_doc"]))
        result = await agent.search_with_kb_context("chocolate cake recipe", kb=kb)

        assert is_refusal(result["answer"])
        provider.search.assert_not_awaited()


# ---------------------------------------------------------------------------
# Web route: deliberate non-answer is not a failure
# ---------------------------------------------------------------------------


class TestWebRouteNonAnswer:
    @staticmethod
    def _handler(web_result):
        from src.agents.web_route_handler import WebRouteHandler

        web_search = MagicMock()
        web_search.search = AsyncMock(return_value=web_result)
        config = MagicMock()
        config.enable_web_search = True
        config.retrieval_threshold = 0.0
        config.retrieval_k = 5
        return WebRouteHandler(
            web_search=web_search,
            retriever=MagicMock(),
            answer_generator=MagicMock(),
            citation_manager=CitationManager(),
            config=config,
        )

    @pytest.mark.asyncio
    async def test_no_answer_found_is_not_error_fallback(self):
        handler = self._handler(
            {"answer": NO_ANSWER_FOUND, "sources": [], "grounded": False, "truncated": False}
        )

        result = await handler.process("obscure query", steps=[])

        assert result["answer"] == NO_ANSWER_FOUND
        assert "error_fallback" not in result["sources"]

    @pytest.mark.asyncio
    async def test_timeout_still_marks_error_fallback(self):
        handler = self._handler(
            {
                "answer": "Web search timed out. Please try again.",
                "sources": [],
                "grounded": False,
                "truncated": True,
                "timed_out": True,
            }
        )

        result = await handler.process("obscure query", steps=[])

        assert result["sources"] == ["error_fallback"]

    @staticmethod
    def _supplement_handler(web_result):
        from src.agents.web_route_handler import WebRouteHandler

        web_search = MagicMock()
        web_search.search_with_kb_context = AsyncMock(return_value=web_result)
        config = MagicMock()
        config.enable_web_search = True
        config.retrieval_threshold = 0.0
        config.retrieval_k = 5
        return WebRouteHandler(
            web_search=web_search,
            retriever=MagicMock(),
            answer_generator=MagicMock(),
            citation_manager=CitationManager(),
            config=config,
        )

    @pytest.mark.asyncio
    async def test_scope_refusal_surfaces_over_kb_non_answer(self):
        """Off-domain query + no KB answer → the refusal is the final answer,
        not the generic non-answer."""
        handler = self._supplement_handler(
            {
                "answer": SCOPE_REFUSAL_ANSWER,
                "sources": [],
                "kb_sources": [],
                "web_sources": [],
                "grounded": False,
                "hybrid": False,
                "truncated": False,
            }
        )
        kb_result = {"answer": NO_ANSWER_FOUND, "sources": [], "citations": []}

        result = await handler.supplement(
            "chocolate cake recipe", kb_result, _vector_results(["kb_doc"]), steps=[]
        )

        assert result["answer"] == SCOPE_REFUSAL_ANSWER

    @pytest.mark.asyncio
    async def test_scope_refusal_does_not_override_real_kb_answer(self):
        """If the KB produced a real answer, a misfired gate refusal must not
        erase it."""
        kb_answer = "Verified units must be serialized [cite_kb: 1]."
        handler = self._supplement_handler(
            {
                "answer": SCOPE_REFUSAL_ANSWER,
                "sources": [],
                "kb_sources": [],
                "web_sources": [],
                "grounded": False,
                "hybrid": False,
                "truncated": False,
            }
        )
        kb_result = {"answer": kb_answer, "sources": ["kb_doc.pdf"], "citations": []}

        result = await handler.supplement(
            "borderline query", kb_result, _vector_results(["kb_doc"]), steps=[]
        )

        assert result["answer"] == kb_answer


# ---------------------------------------------------------------------------
# Word-limit truncation
# ---------------------------------------------------------------------------


class TestEnforceWordLimit:
    def test_cut_prefers_paragraph_boundary_and_keeps_markers(self):
        # Each paragraph ends with a citation marker; the word cut would land
        # mid-paragraph-3, so the result must stop at the paragraph-2 break.
        para1 = "First paragraph about carbon markets. " * 8 + "[cite_kb: 1]"
        para2 = "Second paragraph about registries. " * 8 + "[cite_kb: 2]"
        para3 = "Third paragraph about pricing. " * 8 + "[cite_kb: 3]"
        answer = f"{para1}\n\n{para2}\n\n{para3}"

        max_words = len((para1 + " " + para2).split()) + 5
        truncated, was_truncated = enforce_word_limit(answer, max_words)

        assert was_truncated
        assert truncated.endswith("[cite_kb: 2]")
        assert "[cite_kb: 1]" in truncated
        assert "[cite_kb: 3]" not in truncated

    def test_kept_paragraphs_never_lose_trailing_marker(self):
        paras = []
        for i in range(1, 6):
            paras.append(f"Paragraph {i} body text here. " * 4 + f"[cite_kb: {i}]")
        answer = "\n\n".join(paras)

        max_words = len(answer.split()) // 2
        truncated, was_truncated = enforce_word_limit(answer, max_words)

        assert was_truncated
        kept = [p for p in paras if p in truncated]
        assert kept
        for p in kept:
            assert p.endswith(f"[cite_kb: {paras.index(p) + 1}]")
        # Output ends at a paragraph break (last kept paragraph's marker).
        assert truncated == "\n\n".join(kept)

    def test_short_answer_unchanged(self):
        answer = "Short answer [cite_kb: 1]."
        assert enforce_word_limit(answer, 100) == (answer, False)


# ---------------------------------------------------------------------------
# Cache schema version
# ---------------------------------------------------------------------------


class TestCacheSchemaVersion:
    def test_schema_version_changes_cache_key(self, monkeypatch):
        import src.utils.cache as cache_module

        cache = QueryCache()
        monkeypatch.setattr(cache_module, "QUERY_CACHE_SCHEMA_VERSION", 2)
        key_v2 = cache.build_cache_key("carbon credits", context_fingerprint="fp")
        monkeypatch.setattr(cache_module, "QUERY_CACHE_SCHEMA_VERSION", 3)
        key_v3 = cache.build_cache_key("carbon credits", context_fingerprint="fp")

        assert key_v2 != key_v3


# ---------------------------------------------------------------------------
# Structured mode: dataset citation shown without markers
# ---------------------------------------------------------------------------


class TestStructuredMode:
    def test_dataset_citation_shown_without_markers(self):
        citation = Citation(
            source_id="dataset_1",
            source_name="Credit Dataset",
            source_type="structured",
            marker_type="knowledge_base",
            content_snippet="rows",
            relevance_score=1.0,
            index=None,
        )
        result = {"answer": "There are 42 records.", "citations": [citation]}

        CitationManager().finalize(result, "how many records?")

        assert result["citations"] == [citation]
        assert result["sources"] == ["Credit Dataset"]


# ---------------------------------------------------------------------------
# parse_citations: only [source_N] markers convert, bare [N] is literal text
# ---------------------------------------------------------------------------


class TestParseCitations:
    def test_bare_year_is_not_a_citation(self):
        text = parse_citations("In [2024] prices rose [source_1].", ["source_1"])
        assert text == "In [2024] prices rose [Web, cite: 1]."

    def test_source_list_citation_converted(self):
        text = parse_citations("See [source_1, source_2].", ["source_1", "source_2"])
        assert text == "See [Web, cite: 1, 2]."


class TestDeduplicateInlineCitations:
    def test_bare_years_left_untouched(self):
        answer = "Since [2024] a. And [2024] b."
        assert deduplicate_inline_citations(answer) == answer

    def test_duplicate_markers_still_collapse(self):
        answer = "A [cite_kb: 1]. B [cite_kb: 1]."
        assert deduplicate_inline_citations(answer) == "A [cite_kb: 1]. B."


# ---------------------------------------------------------------------------
# document_key: document identity used to merge chunk badges on the frontend
# ---------------------------------------------------------------------------


class TestDocumentKey:
    def test_kb_chunks_carry_doc_store_id(self):
        vector_results = {
            "documents": ["Chunk a1.", "Chunk a2.", "Chunk b.", "Chunk c."],
            "metadatas": [
                {"file_name": "a.pdf", "doc_store_id": "abc"},
                {"file_name": "a.pdf", "doc_store_id": "abc"},
                {"file_name": "b.pdf", "doc_store_id": "def"},
                {"file_name": "c.pdf"},
            ],
            "distances": [0.2, 0.2, 0.2, 0.2],
        }
        ctx = build_kb_context(vector_results)

        assert [c.index for c in ctx.citations] == [1, 2, 3, 4]
        assert [c.document_key for c in ctx.citations] == ["abc", "abc", "def", None]

    def test_formatter_emits_document_key_only_when_set(self):
        vector_results = {
            "documents": ["Chunk a.", "Chunk c."],
            "metadatas": [
                {"file_name": "a.pdf", "doc_store_id": "abc"},
                {"file_name": "c.pdf"},
            ],
            "distances": [0.2, 0.2],
        }
        ctx = build_kb_context(vector_results)

        details = CitationManager().format_citations_for_response(ctx.citations)["details"]
        assert details[0]["document_key"] == "abc"
        assert "document_key" not in details[1]

    def test_document_key_round_trips_through_dict(self):
        vector_results = {
            "documents": ["Chunk a."],
            "metadatas": [{"file_name": "a.pdf", "doc_store_id": "abc"}],
            "distances": [0.2],
        }
        citation = build_kb_context(vector_results).citations[0]
        assert Citation.from_dict(citation.to_dict()).document_key == "abc"

    def test_web_citation_document_key_is_the_result_url(self):
        web_results = {
            "sources": [
                {"title": "Report", "url": "https://example.com/report", "snippet": "s"}
            ]
        }
        citations = CitationManager().extract_citations_from_web_results(web_results)
        assert citations[0].document_key == "https://example.com/report"

    def test_file_like_web_source_still_groups_by_url(self):
        # source_type resolves to knowledge_base and `url` stays None, but the
        # document identity must still be the result URL.
        web_results = {
            "sources": [
                {"title": "Standard", "url": "https://example.com/std.pdf", "snippet": "s"}
            ]
        }
        citations = CitationManager().extract_citations_from_web_results(web_results)
        assert citations[0].source_type == "knowledge_base"
        assert citations[0].url is None
        assert citations[0].document_key == "https://example.com/std.pdf"
