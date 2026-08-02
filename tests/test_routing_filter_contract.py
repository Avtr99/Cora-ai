"""
Regression tests for the three structural defects that caused KB false negatives:

1. **Filter value contract** — categorical filter values (category, registry,
   standard, policy_framework) emitted by the rewriter that don't exist in the
   corpus silently returned zero results. The fix validates values against the
   corpus at the filter boundary and drops unknown values instead of enforcing
   them.

2. **Rewriter prompt contract** — the rewriter prompt must not invent generic
   category values such as ``category="standard"``, ``category="policy"``, or
   ``category="registry"``. Standard and policy-framework fields remain
   available for custom or legacy corpora when exact stored values are known.

3. **Ambiguous routing default** — ambiguous, non-realtime queries now default
   to ``knowledge_base`` so the corpus determines whether the topic is covered.
   The KB route retains its web fallback when retrieval is empty or weak.

These tests pin the fixes so a future edit cannot silently reintroduce the
silent-zero-result trap or the web-only-by-default routing for unknown topics.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.router import RouteDecision, RouterAgent
from src.retrieval.filter_builder import QdrantFilterBuilder
from src.retrieval.schema_discovery import (
    CATEGORICAL_FILTER_FIELDS,
    discover_categorical_values_from_payloads,
    invalidate_categorical_values_cache,
    remember_categorical_value,
)


# ---------------------------------------------------------------------------
# Fix 1: categorical value validation at the filter boundary
# ---------------------------------------------------------------------------


@pytest.fixture
def filter_builder():
    """A QdrantFilterBuilder with a mocked vector_store and collection name."""
    vs = MagicMock()
    vs.client = MagicMock()
    return QdrantFilterBuilder(vector_store=vs, collection_name="test_collection")


@pytest.fixture(autouse=True)
def _clear_categorical_cache():
    """Ensure each test starts with an empty categorical-values cache."""
    invalidate_categorical_values_cache("test_collection")
    invalidate_categorical_values_cache("cora_dense_only")
    yield
    invalidate_categorical_values_cache("test_collection")
    invalidate_categorical_values_cache("cora_dense_only")


class TestCategoricalValueValidation:
    """The filter boundary must drop categorical values that don't exist in the
    corpus rather than enforcing them and silently returning zero results."""

    @pytest.mark.asyncio
    async def test_unknown_category_value_is_dropped(self, filter_builder):
        """category="standard" (a value ingestion never stores) must be dropped,
        not enforced. This is the exact SBTi false-negative trap."""
        # Indexed fields include "category" so it passes field validation.
        filter_builder._indexed_filter_fields = {"category", "registry"}

        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={"category": {"SBTi", "ICVCM", "VCM Policy"}, "registry": set()},
        ):
            # Targeted check confirms "standard" does NOT exist in the corpus.
            with patch.object(filter_builder, "_check_value_exists", return_value=False):
                qfilter, supported = await filter_builder.build_validated_filter(
                    {"category": "standard"}, allow_unfiltered_fallback=True
                )

        # The unknown value must be dropped → no filter enforced.
        assert qfilter is None
        assert supported == {}

    @pytest.mark.asyncio
    async def test_known_category_value_is_enforced(self, filter_builder):
        """category="SBTi" (a real stored value) must be enforced."""
        filter_builder._indexed_filter_fields = {"category", "registry"}

        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={"category": {"SBTi", "ICVCM"}, "registry": set()},
        ):
            qfilter, supported = await filter_builder.build_validated_filter(
                {"category": "SBTi"}, allow_unfiltered_fallback=True
            )

        assert qfilter is not None
        assert supported == {"category": "SBTi"}

    @pytest.mark.asyncio
    async def test_unknown_policy_framework_value_is_dropped(self, filter_builder):
        """policy_framework="Article 6.4" must be dropped when the field has no
        values in the corpus (ingestion does not populate it)."""
        filter_builder._indexed_filter_fields = {"category", "policy_framework"}

        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={"category": set(), "policy_framework": set()},
        ):
            # Field is indexed but has no values in the sample → fail open.
            qfilter, supported = await filter_builder.build_validated_filter(
                {"policy_framework": "Article 6.4"}, allow_unfiltered_fallback=True
            )

        # Field has no values in sample → cannot validate → fail open (enforced).
        # This is acceptable: an empty field never matches, so Qdrant returns 0,
        # and the KB handler's zero-result → web fallback catches it. The trap
        # we're fixing is when the field HAS values but the query value isn't one.
        assert qfilter is not None
        assert "policy_framework" in supported

    @pytest.mark.asyncio
    async def test_unknown_value_raises_when_fallback_disabled(self, filter_builder):
        """When allow_unfiltered_fallback=False, an unknown categorical value
        must raise (fail-closed) rather than silently return zero results."""
        filter_builder._indexed_filter_fields = {"category"}

        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={"category": {"SBTi"}},
        ):
            with patch.object(filter_builder, "_check_value_exists", return_value=False):
                with pytest.raises(ValueError, match="unknown categorical values"):
                    await filter_builder.build_validated_filter(
                        {"category": "standard"}, allow_unfiltered_fallback=False
                    )

    @pytest.mark.asyncio
    async def test_mixed_known_and_unknown_values(self, filter_builder):
        """A multi-filter query with one known and one unknown categorical value:
        the unknown is dropped, the known is enforced."""
        filter_builder._indexed_filter_fields = {"category", "registry", "document_id"}

        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={
                "category": {"SBTi", "VCM Policy"},
                "registry": {"Verra", "Gold Standard"},
            },
        ):
            # "standard" not in sample → targeted check confirms it doesn't exist.
            with patch.object(filter_builder, "_check_value_exists", return_value=False):
                qfilter, supported = await filter_builder.build_validated_filter(
                    {"category": "standard", "registry": "Verra", "document_id": "VM0048"},
                    allow_unfiltered_fallback=True,
                )

        # Unknown category dropped; known registry and document_id enforced.
        assert qfilter is not None
        assert supported == {"registry": "Verra", "document_id": "VM0048"}
        assert "category" not in supported

    @pytest.mark.asyncio
    async def test_discovery_failure_fails_open(self, filter_builder):
        """If categorical value discovery fails, validation is skipped (fail open)
        — a transient Qdrant error must not block retrieval."""
        filter_builder._indexed_filter_fields = {"category"}

        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={},  # discovery failed
        ):
            qfilter, supported = await filter_builder.build_validated_filter(
                {"category": "standard"}, allow_unfiltered_fallback=True
            )

        # Failed discovery → fail open → filter enforced (KB zero-result fallback handles it).
        assert qfilter is not None
        assert supported == {"category": "standard"}

    @pytest.mark.asyncio
    async def test_non_categorical_field_not_validated(self, filter_builder):
        """Non-categorical fields (document_id, version_number) are not subject
        to value validation — only categorical fields are."""
        filter_builder._indexed_filter_fields = {"document_id", "version_number"}

        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={f: set() for f in CATEGORICAL_FILTER_FIELDS},
        ):
            qfilter, supported = await filter_builder.build_validated_filter(
                {"document_id": "VM0048", "version_number": "2.0"},
                allow_unfiltered_fallback=True,
            )

        assert qfilter is not None
        assert supported == {"document_id": "VM0048", "version_number": "2.0"}

    @pytest.mark.asyncio
    async def test_rare_category_not_in_sample_is_kept(self, filter_builder):
        """A legitimate category that the 1000-point sample missed (rare in a
        large collection) must NOT be dropped. The targeted existence check
        confirms the value exists before dropping it.

        Without the targeted check, this would be a false positive: the sample
        has other category values but not "SBTi", so "SBTi" would be wrongly
        dropped — even though SBTi documents exist in the collection.
        """
        filter_builder._indexed_filter_fields = {"category"}

        # Sample found other categories but missed "SBTi" (rare category).
        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={"category": {"Market Intelligence", "VCM Policy"}},
        ):
            # Targeted check confirms SBTi DOES exist → keep the filter.
            with patch.object(
                filter_builder, "_check_value_exists", return_value=True
            ):
                qfilter, supported = await filter_builder.build_validated_filter(
                    {"category": "SBTi"}, allow_unfiltered_fallback=True
                )

        assert qfilter is not None
        assert supported == {"category": "SBTi"}

    @pytest.mark.asyncio
    async def test_genuinely_invalid_value_confirmed_by_targeted_check(self, filter_builder):
        """A value not in the sample AND not confirmed by the targeted check is
        genuinely invalid → dropped. This is the SBTi trap: category="standard"
        doesn't exist in the corpus."""
        filter_builder._indexed_filter_fields = {"category"}

        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={"category": {"SBTi", "ICVCM"}},
        ):
            # Targeted check confirms "standard" does NOT exist → drop.
            with patch.object(
                filter_builder, "_check_value_exists", return_value=False
            ):
                qfilter, supported = await filter_builder.build_validated_filter(
                    {"category": "standard"}, allow_unfiltered_fallback=True
                )

        assert qfilter is None
        assert supported == {}

    def test_categorical_discovery_cache_remembers_confirmed_values(self):
        """A rare value confirmed by targeted lookup is added to the cache so
        subsequent requests do not repeat the targeted lookup."""
        client = MagicMock()
        client.scroll.return_value = ([], None)

        with patch(
            "src.retrieval.schema_discovery._get_qdrant_client",
            return_value=client,
        ):
            assert discover_categorical_values_from_payloads("test_collection")
            remember_categorical_value("test_collection", "category", "Rare Topic")
            values = discover_categorical_values_from_payloads("test_collection")

        assert "Rare Topic" in values["category"]
        client.scroll.assert_called_once()

    def test_categorical_discovery_failure_is_temporarily_cached(self):
        """A discovery outage must not trigger a full sample scan on every
        query, while the short TTL still allows recovery without restart."""
        client = MagicMock()
        client.scroll.side_effect = RuntimeError("Qdrant unavailable")

        with patch(
            "src.retrieval.schema_discovery._get_qdrant_client",
            return_value=client,
        ):
            assert discover_categorical_values_from_payloads("test_collection") == {}
            assert discover_categorical_values_from_payloads("test_collection") == {}

        client.scroll.assert_called_once()

    @pytest.mark.asyncio
    async def test_targeted_check_failure_fails_open(self, filter_builder):
        """If the targeted existence check itself fails (Qdrant error), the
        filter is kept (fail open) — a transient error must not drop a
        legitimate filter."""
        filter_builder._indexed_filter_fields = {"category"}

        with patch(
            "src.retrieval.filter_builder.discover_categorical_values_from_payloads",
            return_value={"category": {"Market Intelligence"}},
        ):
            # Targeted check raises → _check_value_exists returns True (fail open).
            with patch.object(
                filter_builder, "_check_value_exists", return_value=True
            ):
                qfilter, supported = await filter_builder.build_validated_filter(
                    {"category": "SBTi"}, allow_unfiltered_fallback=True
                )

        # Fail open → filter kept (KB zero-result fallback handles it if truly invalid).
        assert qfilter is not None
        assert supported == {"category": "SBTi"}


class TestFilterRelaxation:
    """Metadata filters must improve precision without becoming hard recall
    requirements when they produce no candidates."""

    @pytest.mark.asyncio
    async def test_single_filter_relaxes_to_unfiltered_search(self):
        vector_store = MagicMock()
        vector_store.similarity_search_with_score.return_value = [("doc", 0.9)]
        builder = QdrantFilterBuilder(vector_store, "test_collection")

        result = await builder.relax_and_retry(
            query="carbon methodology",
            supported_filters={"standard": "Custom Standard"},
            candidates_count=5,
        )

        assert result == ([("doc", 0.9)], ["standard"])
        vector_store.similarity_search_with_score.assert_called_once()
        assert vector_store.similarity_search_with_score.call_args.kwargs["filter"] is None

    @pytest.mark.asyncio
    async def test_multiple_filters_can_fully_relax_to_unfiltered_search(self):
        """A zero-result conjunction can recover by dropping all metadata
        filters when neither filter matches the same document."""
        vector_store = MagicMock()
        vector_store.similarity_search_with_score.side_effect = [
            [],
            [],
            [("doc", 0.9)],
        ]
        builder = QdrantFilterBuilder(vector_store, "test_collection")

        result = await builder.relax_and_retry(
            query="carbon methodology",
            supported_filters={"category": "REDD+ / NBS", "registry": "Verra"},
            candidates_count=5,
        )

        assert result == ([("doc", 0.9)], ["category", "registry"])
        assert vector_store.similarity_search_with_score.call_args.kwargs["filter"] is None

    @pytest.mark.asyncio
    async def test_document_id_is_preserved_while_other_filters_relax(self):
        vector_store = MagicMock()
        vector_store.similarity_search_with_score.return_value = [("doc", 0.9)]
        builder = QdrantFilterBuilder(vector_store, "test_collection")

        result = await builder.relax_and_retry(
            query="carbon methodology",
            supported_filters={"document_id": "VM0048", "standard": "Custom Standard"},
            candidates_count=5,
        )

        assert result == ([("doc", 0.9)], ["standard"])
        relaxed_filter = vector_store.similarity_search_with_score.call_args.kwargs["filter"]
        assert relaxed_filter is not None
        assert relaxed_filter.must[0].key == "metadata.document_id"


# ---------------------------------------------------------------------------
# Fix 2: rewriter prompt no longer emits invalid filter values
# ---------------------------------------------------------------------------


class TestRewriterPromptContract:
    """The rewriter prompt must not emit generic category type words as values.

    ``standard`` and ``policy_framework`` remain supported fields because
    custom or legacy corpora may populate them. The prompt must therefore teach
    exact-value matching rather than banning those fields globally.
    """

    def _examples_section(self):
        from src.agents.query_rewriter import REWRITE_PROMPT

        start = REWRITE_PROMPT.find("<examples>")
        end = REWRITE_PROMPT.find("</examples>")
        assert start != -1 and end != -1, "Prompt must have an <examples> section"
        return REWRITE_PROMPT[start:end]

    def test_examples_do_not_emit_category_standard(self):
        examples = self._examples_section()
        assert 'category="standard"' not in examples
        assert 'category=\\"standard\\"' not in examples

    def test_examples_do_not_emit_category_policy(self):
        examples = self._examples_section()
        assert 'category="policy"' not in examples
        assert 'category=\\"policy\\"' not in examples

    def test_examples_do_not_emit_category_registry(self):
        examples = self._examples_section()
        assert 'category="registry"' not in examples
        assert 'category=\\"registry\\"' not in examples

    def test_examples_do_not_demonstrate_policy_framework_filter(self):
        """No example should show policy_framework="..." as a filter."""
        examples = self._examples_section()
        assert 'policy_framework="Article 6.4"' not in examples
        assert 'policy_framework=\\"Article 6.4\\"' not in examples

    def test_prompt_warns_against_generic_category_values(self):
        """The prompt must explicitly warn that generic category values like
        'standard', 'policy', 'registry' are never valid."""
        from src.agents.query_rewriter import REWRITE_PROMPT

        prompt_lower = REWRITE_PROMPT.lower()
        assert "standard" in prompt_lower
        assert "never" in prompt_lower or "do not" in prompt_lower

    def test_prompt_preserves_custom_standard_fields(self):
        """The prompt must not globally ban standard or policy_framework fields,
        because custom and legacy corpora may populate them."""
        from src.agents.query_rewriter import REWRITE_PROMPT

        prompt_lower = REWRITE_PROMPT.lower()
        assert "custom or legacy corpora" in prompt_lower
        assert "policy_framework" in prompt_lower

    def test_prompt_does_not_hardcode_specific_category_names(self):
        """The prompt must NOT list specific category names (like 'SBTi',
        'ICVCM', 'VCM Policy') as 'correct' or 'real stored' values. The KB
        is extensible — users can ingest docs from any organisation. Hardcoding
        specific names would make the rewriter assume unknown orgs are invalid.
        The validation at the filter boundary (corpus-driven) handles correctness."""
        from src.agents.query_rewriter import REWRITE_PROMPT

        # The taxonomy note must not present a fixed list of "real stored values"
        # that includes specific org names as examples of valid category values.
        taxonomy_start = REWRITE_PROMPT.find("<taxonomy_note>")
        taxonomy_end = REWRITE_PROMPT.find("</taxonomy_note>")
        assert taxonomy_start != -1 and taxonomy_end != -1
        taxonomy = REWRITE_PROMPT[taxonomy_start:taxonomy_end]

        # Must NOT contain hardcoded "real stored values" examples with specific
        # category names — this would bias the rewriter against new orgs.
        assert 'category="SBTi"' not in taxonomy
        assert 'category="ICVCM"' not in taxonomy
        assert 'category="VCM Policy"' not in taxonomy
        assert 'category="Market Intelligence"' not in taxonomy

    def test_prompt_acknowledges_kb_is_extensible(self):
        """The prompt must tell the LLM that the KB is not limited to the
        listed acronyms — users can ingest documents from any organisation."""
        from src.agents.query_rewriter import REWRITE_PROMPT

        prompt_lower = REWRITE_PROMPT.lower()
        assert "not limited" in prompt_lower or "any organisation" in prompt_lower

    def test_examples_use_real_stored_registry_values(self):
        """Examples that demonstrate registry filters must use real stored
        registry names (e.g. 'Verra', 'Gold Standard'), not 'VCS'."""
        examples = self._examples_section()
        # The VCS example must now use registry="Verra" (the stored value),
        # not registry="VCS" (a value ingestion never stores in `registry`).
        assert 'registry="Verra"' in examples or 'registry=\\"Verra\\"' in examples
        assert 'registry="VCS"' not in examples


# ---------------------------------------------------------------------------
# Fix 3: ambiguous routing falls back to the lite LLM
# ---------------------------------------------------------------------------


@pytest.fixture
def router():
    """A RouterAgent with a mocked LLM client for ambiguous-query fallback tests."""
    llm = MagicMock()
    llm.model_lite = "mock-lite-model"
    llm.generate_text = AsyncMock(return_value='{"route": "knowledge_base", "confidence": 0.8, "reasoning": "test"}')
    return RouterAgent(llm)


class TestAmbiguousRoutingLLMFallback:
    """Ambiguous queries (no heuristic signal matched) must fall back to the
    lite LLM for domain-agnostic routing. The heuristic pass returns None so
    the LLM can infer the correct route for non-VCM queries that no keyword
    matches (e.g. "scope 3 emissions accounting", "EU Electrification Action
    Plan"). If the LLM call fails, the router falls back to KB-first (which
    has its own zero-result → web fallback)."""

    def test_ambiguous_query_returns_none_from_heuristic(self, router):
        """A query with no KB keywords and no web keywords must return None
        from the heuristic pass so the LLM fallback is triggered."""
        result = router._quick_route("What is the EU Electrification Action Plan?")
        assert result is None

    def test_unknown_topic_query_returns_none_from_heuristic(self, router):
        """A query about a topic not in the VCM taxonomy must return None
        from the heuristic pass — the LLM decides, not the static taxonomy."""
        result = router._quick_route("Tell me about the Just Transition Mechanism")
        assert result is None

    def test_explicit_web_keyword_still_routes_to_web(self, router):
        """Real-time/news queries must still route to web_search from the
        heuristic pass — the LLM is only for ambiguous queries."""
        result = router._quick_route("latest news about carbon credits")
        assert result is not None
        assert result[0] == RouteDecision.WEB_SEARCH

    def test_post_cutoff_market_year_still_routes_to_web(self, router):
        """Post-cutoff market data queries must still route to web_search."""
        result = router._quick_route("carbon credit price forecast 2027")
        assert result is not None
        assert result[0] == RouteDecision.WEB_SEARCH

    def test_strong_kb_signal_still_routes_to_kb(self, router):
        """Strong VCM KB signals must still route to knowledge_base from the
        heuristic pass — no LLM call needed."""
        result = router._quick_route("What are the VM0048 REDD+ methodology requirements?")
        assert result is not None
        assert result[0] == RouteDecision.KNOWLEDGE_BASE

    def test_document_id_still_routes_to_kb(self, router):
        """Document ID detection must still route to knowledge_base."""
        result = router._quick_route("Show me VM0048")
        assert result is not None
        assert result[0] == RouteDecision.KNOWLEDGE_BASE

    @pytest.mark.asyncio
    async def test_ambiguous_query_calls_llm(self, router):
        """An ambiguous query must call the LLM (lite model) for routing."""
        await router.route("What is the Just Transition Mechanism?")
        router.llm.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_ambiguous_query_uses_lite_model(self, router):
        """The LLM call must use the client's lite model when model_name is None."""
        await router.route("What is the Just Transition Mechanism?")
        call_kwargs = router.llm.generate_text.call_args.kwargs
        assert call_kwargs["model"] == "mock-lite-model"

    @pytest.mark.asyncio
    async def test_ambiguous_query_respects_explicit_model_name(self):
        """When an explicit model_name is passed, it overrides the lite model."""
        llm = MagicMock()
        llm.model_lite = "mock-lite-model"
        llm.generate_text = AsyncMock(return_value='{"route": "knowledge_base", "confidence": 0.8, "reasoning": "test"}')
        router = RouterAgent(llm, model_name="custom-model")
        await router.route("What is the Just Transition Mechanism?")
        call_kwargs = llm.generate_text.call_args.kwargs
        assert call_kwargs["model"] == "custom-model"

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_kb(self):
        """If the LLM call fails, the router must fall back to knowledge_base
        (which has its own zero-result → web fallback) rather than crashing."""
        llm = MagicMock()
        llm.model_lite = "mock-lite-model"
        llm.generate_text = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
        router = RouterAgent(llm)
        result = await router.route("What is the Just Transition Mechanism?")
        assert result[0] == RouteDecision.KNOWLEDGE_BASE
        assert "LLM routing failed" in result[2]

    @pytest.mark.asyncio
    async def test_llm_response_is_parsed_correctly(self):
        """The LLM's JSON response must be parsed into a RouteDecision."""
        llm = MagicMock()
        llm.model_lite = "mock-lite-model"
        llm.generate_text = AsyncMock(return_value='{"route": "web_search", "confidence": 0.9, "reasoning": "real-time query"}')
        router = RouterAgent(llm)
        result = await router.route("What is the Just Transition Mechanism?")
        assert result[0] == RouteDecision.WEB_SEARCH
        assert result[1] == 0.9

    @pytest.mark.asyncio
    async def test_clear_kb_query_does_not_call_llm(self, router):
        """A query with strong KB signals must NOT call the LLM — the heuristic
        pass handles it directly."""
        await router.route("What are the VM0048 REDD+ methodology requirements?")
        router.llm.generate_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_clear_web_query_does_not_call_llm(self, router):
        """A query with strong web signals must NOT call the LLM."""
        await router.route("latest news about carbon credits")
        router.llm.generate_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_lite_model_falls_back_to_main_model(self):
        """When a provider has no dedicated lite model (e.g. OpenAI without
        OPENAI_MODEL_LITE set), the client's model_lite returns the main model.
        The router must use whatever model_lite returns — routing still works,
        just with the main model instead of a cheaper lite one."""
        llm = MagicMock()
        # Simulate OpenAI with no lite model configured: model_lite == model_main
        llm.model_lite = "gpt-4.1-mini"
        llm.model_main = "gpt-4.1-mini"
        llm.generate_text = AsyncMock(return_value='{"route": "knowledge_base", "confidence": 0.8, "reasoning": "test"}')
        router = RouterAgent(llm, model_name=None)
        await router.route("What is the Just Transition Mechanism?")
        call_kwargs = llm.generate_text.call_args.kwargs
        # model_lite returned the main model — router used it correctly.
        assert call_kwargs["model"] == "gpt-4.1-mini"

    @pytest.mark.asyncio
    async def test_client_without_model_lite_attribute_falls_back_gracefully(self):
        """If a custom LLM client doesn't implement model_lite, the router
        must not crash — generate_text(model=None) resolves to model_main
        inside the client."""
        llm = MagicMock()
        # No model_lite attribute — simulates a custom client
        del llm.model_lite
        llm.generate_text = AsyncMock(return_value='{"route": "knowledge_base", "confidence": 0.8, "reasoning": "test"}')
        router = RouterAgent(llm, model_name=None)
        result = await router.route("What is the Just Transition Mechanism?")
        # Router fell back to model=None → client used its main model.
        assert result[0] == RouteDecision.KNOWLEDGE_BASE
        call_kwargs = llm.generate_text.call_args.kwargs
        assert call_kwargs["model"] is None


# ---------------------------------------------------------------------------
# Fix 4: hybrid route retains web retrieval when KB is sufficient
# ---------------------------------------------------------------------------


class TestHybridRetrievalSources:
    """Hybrid retrieval must query both KB and web sources.

    A high KB relevance score does not establish freshness or answer
    completeness, so it must not suppress the web leg.
    """

    def _make_handler(self, kb_results, kb_min_top=0.4, parallel=False):
        """Build a HybridRouteHandler with mocked dependencies."""
        from src.agents.hybrid_route_handler import HybridRouteHandler

        retriever = MagicMock()
        retriever.retrieve = AsyncMock(return_value=kb_results)

        web_search = MagicMock()
        web_search.search = AsyncMock(return_value={"answer": "web answer", "sources": [], "grounded": True})

        answer_gen = MagicMock()
        answer_gen.search_and_process = AsyncMock(return_value={"answer": "kb answer", "sources": []})

        citation_manager = MagicMock()

        config = MagicMock()
        config.parallel_retrieval = parallel
        config.kb_min_top_relevance_score = kb_min_top
        config.enable_web_search = True
        config.enable_web_supplement_relevance_check = True

        return HybridRouteHandler(
            retriever=retriever,
            answer_generator=answer_gen,
            web_search=web_search,
            citation_manager=citation_manager,
            config=config,
        )

    @pytest.mark.asyncio
    async def test_hybrid_calls_web_when_kb_sufficient(self):
        """High KB relevance must not suppress web retrieval."""
        kb_results = {
            "documents": ["doc1", "doc2"],
            "metadatas": [{"source": "s1"}, {"source": "s2"}],
            "ids": ["1", "2"],
            "distances": [0.1, 0.2],
            "scores": [0.9, 0.8],  # Above 0.4 threshold
        }
        handler = self._make_handler(kb_results, kb_min_top=0.4)

        vector_results, web_results = await handler._sequential_retrieval(
            query="test", metadata_filters=None, web_timeout_ms=5000
        )

        assert len(vector_results["documents"]) == 2
        # Web search remains part of hybrid retrieval even when KB is strong.
        handler.web_search.search.assert_called_once_with("test", timeout_ms=5000)
        assert web_results["answer"] == "web answer"

    @pytest.mark.asyncio
    async def test_hybrid_calls_web_when_kb_low_relevance(self):
        """When KB results are below the relevance threshold, web search must run."""
        kb_results = {
            "documents": ["doc1"],
            "metadatas": [{"source": "s1"}],
            "ids": ["1"],
            "distances": [0.8],
            "scores": [0.2],  # Below 0.4 threshold
        }
        handler = self._make_handler(kb_results, kb_min_top=0.4)

        vector_results, web_results = await handler._sequential_retrieval(
            query="test", metadata_filters=None, web_timeout_ms=5000
        )

        assert len(vector_results["documents"]) == 1
        # Web search MUST have been called.
        handler.web_search.search.assert_called_once()
        assert web_results["answer"] == "web answer"

    @pytest.mark.asyncio
    async def test_hybrid_calls_web_when_kb_empty(self):
        """When KB returns zero results, web search must run."""
        kb_results = {"documents": [], "metadatas": [], "ids": [], "distances": []}
        handler = self._make_handler(kb_results, kb_min_top=0.4)

        vector_results, web_results = await handler._sequential_retrieval(
            query="test", metadata_filters=None, web_timeout_ms=5000
        )

        assert len(vector_results["documents"]) == 0
        handler.web_search.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_calls_web_when_threshold_disabled_and_kb_has_docs(self):
        """Disabling the KB threshold must not disable web retrieval."""
        kb_results = {
            "documents": ["doc1"],
            "metadatas": [{"source": "s1"}],
            "ids": ["1"],
            "distances": [0.5],
            "scores": [0.1],  # Low, but threshold is disabled
        }
        handler = self._make_handler(kb_results, kb_min_top=0.0)

        vector_results, web_results = await handler._sequential_retrieval(
            query="test", metadata_filters=None, web_timeout_ms=5000
        )

        assert len(vector_results["documents"]) == 1
        # A disabled relevance threshold only disables the KB gate; it does not
        # change hybrid's contract to omit web retrieval.
        handler.web_search.search.assert_called_once_with("test", timeout_ms=5000)
        assert web_results["answer"] == "web answer"


# ---------------------------------------------------------------------------
# Fix 5: Market Intelligence category no longer matches on "carbon market"
# ---------------------------------------------------------------------------


class TestMarketIntelligenceMarkerFix:
    """The 'Market Intelligence' category must NOT match on the generic phrase
    'carbon market' or 'voluntary carbon market' — these are domain-level terms
    that appear in nearly every VCM document, causing widespread
    misclassification. A document needs specific market-report markers
    (e.g. 'state of the market', 'price forecast') to qualify."""

    def test_carbon_market_marker_removed(self):
        from src.registry_config._categories import CATEGORY_PATTERNS

        mi_pattern = next(
            (p for p in CATEGORY_PATTERNS if p.name == "Market Intelligence"), None
        )
        assert mi_pattern is not None
        assert "carbon market" not in mi_pattern.content_markers
        assert "voluntary carbon market" not in mi_pattern.content_markers

    def test_specific_markers_retained(self):
        from src.registry_config._categories import CATEGORY_PATTERNS

        mi_pattern = next(
            (p for p in CATEGORY_PATTERNS if p.name == "Market Intelligence"), None
        )
        assert mi_pattern is not None
        # Specific market-report markers must still be present.
        assert "state of the market" in mi_pattern.content_markers
        assert "price forecast" in mi_pattern.content_markers
        assert "market report" in mi_pattern.content_markers

    def test_broad_domain_terms_remain_router_signals(self):
        """Broad VCM terms remain KB signals without being category markers."""
        router = RouterAgent(MagicMock())

        result = router._quick_route("What is the voluntary carbon market?")

        assert result[0] == RouteDecision.KNOWLEDGE_BASE

    def test_generic_vcm_doc_not_classified_as_market_intelligence(self):
        """A VCM methodology document that mentions 'carbon market' once should
        NOT be classified as 'Market Intelligence' — it has no market-report
        markers."""
        from src.document_loader.metadata_extractor import MetadataExtractor

        extractor = MetadataExtractor()
        # A methodology doc that mentions "carbon market" but no market-report terms.
        content = """
        VM0048 Methodology for REDD+ Projects
        This methodology applies to carbon market projects in the voluntary carbon market.
        Baseline emissions are calculated using the additionality tool.
        """
        result = extractor.extract(content, "VM0048.md")
        # Should be classified as Verra (registry), not Market Intelligence (category).
        assert result.get("registry") == "Verra"
        assert result.get("category") != "Market Intelligence"
