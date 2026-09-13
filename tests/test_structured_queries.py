"""Tests for complete dataset query detection and formatting."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from qdrant_client.http.exceptions import ResponseHandlingException

import src.query_processing.prompts as prompt_module
from src.agents.route_processor_utils import kb_top_relevance, retrieve_kb_results
from src.query_processing.prompts import build_query_prompt
from src.retrieval.langchain_retriever import LangChainRetriever, _MAX_ENUMERATE_SCROLL, _SCROLL_BATCH
from src.retrieval.structured_context import SAMPLE_ROW_COUNT
from src.retrieval.structured_queries import (
    StructuredListSpec,
    build_structured_context,
    detect_structured_list_query,
    detect_structured_list_query_any,
)


# ---------------------------------------------------------------------------
# ICVCM / CCP detection (backward-compatible)
# ---------------------------------------------------------------------------

def test_detects_ccp_program_list():
    spec = detect_structured_list_query("List all CCP approved programs")
    assert spec is not None
    assert spec.record_type == "program"
    assert spec.status == "CCP-Eligible"


def test_detects_ccp_methodology_list_from_rewritten_query():
    spec = detect_structured_list_query(
        "Integrity Council Core Carbon Principles approved methodologies"
    )
    assert spec is not None
    assert spec.record_type == "methodology"
    assert spec.status == "CCP-Approved"


def test_does_not_treat_general_ccp_question_as_structured_list():
    assert detect_structured_list_query("What are the CCP requirements?") is None


def test_build_structured_context_includes_every_unique_record():
    spec = detect_structured_list_query("List CCP approved methodologies")
    assert spec is not None
    context, count = build_structured_context(
        [
            {
                "json_index": 2,
                "metadata": {
                    "program_name": "Isometric",
                    "methodology_name": "Biochar Production and Storage - 1.0",
                    "category": "Biochar",
                    "status": "CCP-Approved",
                },
            },
            {
                "json_index": 1,
                "metadata": {
                    "program_name": "ACR",
                    "methodology_name": "ACR Afforestation - 1.0",
                    "category": "ARR",
                    "status": "CCP-Approved",
                },
            },
        ],
        spec,
    )
    assert count == 2
    assert context.index("ACR Afforestation - 1.0") < context.index("Biochar Production")
    assert "Complete dataset" in context


# ---------------------------------------------------------------------------
# Generalized registry detection
# ---------------------------------------------------------------------------

def test_detects_verra_methodology_list():
    spec = detect_structured_list_query("List all Verra methodologies")
    assert spec is not None
    assert spec.record_type == "methodology"
    assert spec.qdrant_filter.get("registry") == "Verra"


def test_does_not_detect_gold_standard_project_list():
    """Project trackers are datasets, not doc_type=project records."""
    assert detect_structured_list_query("Show me all Gold Standard projects") is None


def test_detects_sbti_standard_list():
    spec = detect_structured_list_query("List all SBTi standards")
    assert spec is not None
    assert spec.record_type == "standard"
    assert spec.qdrant_filter.get("standard") == "SBTi"


def test_does_not_detect_verra_registry_list():
    """The corpus has registry metadata, not a registry entity collection."""
    assert detect_structured_list_query("List all Verra registries") is None


# ---------------------------------------------------------------------------
# Non-enumeration queries (should NOT be detected)
# ---------------------------------------------------------------------------

def test_does_not_detect_semantic_query():
    assert detect_structured_list_query("Tell me about carbon credits") is None


def test_does_not_detect_definition_query():
    assert detect_structured_list_query("What is VM0048?") is None


def test_does_not_detect_unknown_registry():
    assert detect_structured_list_query("List all FakeRegistry programs") is None


def test_does_not_detect_no_entity_type():
    assert detect_structured_list_query("Give me all Verra") is None


def test_empty_query_returns_none():
    assert detect_structured_list_query("") is None
    assert detect_structured_list_query("   ") is None


def test_custom_system_instruction_preserves_shared_rules(monkeypatch):
    monkeypatch.setattr(
        prompt_module,
        "get_settings",
        lambda: SimpleNamespace(COLLECTION_SYSTEM_INSTRUCTION="An expert assistant for financial filings."),
    )

    instruction = prompt_module.get_system_instruction()

    assert "An expert assistant for financial filings." in instruction
    assert "<security_protocol>" in instruction
    assert "NEVER disclose API keys" in instruction
    assert "<output_rules>" in instruction
    assert "voluntary carbon markets" not in instruction.lower()


def test_custom_registry_patterns_refresh_detection_tables(tmp_path, monkeypatch):
    from src.registry_config import registry_patterns

    custom_path = tmp_path / "registry-patterns.json"
    custom_path.write_text(
        json.dumps([{
            "name": "Acme Registry",
            "content_markers": ["acme registry"],
            "id_patterns": [r"\b(ACME\d+)\b"],
            "version_patterns": [],
            "row_entity": "certificate",
            "row_entity_plural": "certificates",
        }]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        registry_patterns,
        "get_settings",
        lambda: SimpleNamespace(CUSTOM_REGISTRY_PATTERNS=str(custom_path)),
    )
    registry_patterns.clear_registry_cache()

    try:
        spec = detect_structured_list_query("List all Acme Registry methodologies")
        assert spec is not None
        assert spec.qdrant_filter == {"doc_type": "methodology", "registry": "Acme Registry"}
        assert registry_patterns.find_document_codes("ACME1234") == ["ACME1234"]
    finally:
        monkeypatch.undo()
        registry_patterns.clear_registry_cache()


def test_does_not_detect_predicate_all():
    """Standalone 'all' in a question is a quantifier, not an enumeration."""
    assert detect_structured_list_query("Are all Verra standards required to be verified?") is None
    assert detect_structured_list_query("Do all Verra methodologies need a methodology deviation?") is None
    assert detect_structured_list_query("Must all Gold Standard methodologies be additional?") is None


def test_does_not_detect_predicate_every():
    """Standalone 'every' in a question is a quantifier, not an enumeration."""
    assert detect_structured_list_query("Is every Verra standard independently audited?") is None


def test_detect_structured_list_query_any_checks_original_separately():
    """A yes-no original must not combine with a rewritten enumeration phrase."""
    assert detect_structured_list_query_any(
        "Are all Verra standards required to be verified?",
        "Verra standards",
    ) is None


def test_generic_registry_list_falls_through():
    assert detect_structured_list_query("What are all the carbon registries?") is None


# ---------------------------------------------------------------------------
# Project-census detection (methodology-anchored dataset scrolls)
# ---------------------------------------------------------------------------

def test_detects_project_census_count_query():
    spec = detect_structured_list_query("how many VM0047 projects are registered with VCS?")
    assert spec is not None
    assert spec.record_type == "project"
    assert spec.mode == "aggregate"
    assert spec.qdrant_filter == {"methodology_codes": "VM0047", "doc_type": "dataset"}


def test_census_filters_on_methodology_codes_not_document_id():
    """document_id is the document's own identity, not the row's methodology.

    On the registry offsets database it is frequently the row's Project ID, so
    filtering on it returns 6 rows for ACM0002 where 1474 actually reference it.
    """
    spec = detect_structured_list_query("how many ACM0002 projects are there?")
    assert spec is not None
    assert "document_id" not in spec.qdrant_filter
    assert spec.qdrant_filter["methodology_codes"] == "ACM0002"


def test_detects_project_census_list_query():
    # Even "list all" for project rows is large; treat as an aggregation:
    # lead with the exact count and status breakdown, then 10 examples.
    spec = detect_structured_list_query("list all registered VM0047 projects")
    assert spec is not None
    assert spec.record_type == "project"
    assert spec.mode == "aggregate"


def test_project_census_normalizes_code_case():
    spec = detect_structured_list_query("how many vm0047 projects are under validation?")
    assert spec is not None
    assert spec.qdrant_filter["methodology_codes"] == "VM0047"


@pytest.mark.parametrize("query", [
    "are there clear signals for vm0047 prices now that 5 projects are registered with vcs?",
    "what is the market value of VM0047 project credits?",
    "which VM0047 projects have issued credits?",
    "what is the status of the Paracel VM0047 project?",
])
def test_row_context_queries_only_supplement(query):
    """These need the methodology document too, so facts are appended to it."""
    spec = detect_structured_list_query(query)
    assert spec is not None
    assert spec.record_type == "project"
    assert spec.mode == "supplement"


@pytest.mark.parametrize("query", [
    "Explain the credit issuance process for VM0047 projects",
    "Summarize the additionality requirements for VM0047 projects and their credits",
    "How are credits issued under a VM0047 project?",
])
def test_conceptual_methodology_questions_never_replace_retrieval(query):
    """A census must not answer a methodology question from the wrong corpus."""
    spec = detect_structured_list_query(query)
    assert spec is None or spec.mode == "supplement"


def test_project_query_without_row_intent_not_detected():
    assert detect_structured_list_query("what are the risks of VM0047 projects?") is None
    assert detect_structured_list_query("can a VM0047 project use dynamic baselines?") is None


def test_census_intent_without_project_entity_not_detected():
    assert detect_structured_list_query("how many VM0047 credits exist?") is None


def test_project_query_without_methodology_code_not_detected():
    assert detect_structured_list_query("how many VCS projects are registered?") is None


# ---------------------------------------------------------------------------
# build_structured_context — project rows
# ---------------------------------------------------------------------------

_VROD_ROW = {
    "Project ID": "VCS5511",
    "Project Name": "Brazil Cerrado 1",
    "Voluntary Registry": "VCS",
    "Voluntary Status": "Registered",
    "Total Credits Issued": "230119",
    "Total Credits Retired": "75000",
    "Total Credits Remaining": "155119",
    "Country": "Brazil",
    "Project Registered": "4-20-2026",
}


def _project_spec(mode: str = "enumerate") -> StructuredListSpec:
    return StructuredListSpec(
        source="structured_query", status="", record_type="project",
        display_name="registry projects using VM0047",
        qdrant_filter={"methodology_codes": "VM0047", "doc_type": "dataset"},
        mode=mode,
    )


def test_build_structured_context_project_rows_from_text():
    context, count = build_structured_context(
        [{"json_index": 1, "metadata": {"row_data": _VROD_ROW}}],
        _project_spec(),
    )
    assert count == 1
    assert "Project ID: VCS5511" in context
    assert "Project Name: Brazil Cerrado 1" in context
    assert "Voluntary Status: Registered" in context
    assert "Total Credits Issued: 230119" in context
    # Unlisted row fields are not carried into the compact line
    assert "Voluntary Registry" not in context


def test_build_structured_context_project_rows_deduplicate():
    records = [
        {"json_index": 1, "metadata": {"row_data": _VROD_ROW}},
        {"json_index": 1, "metadata": {"row_data": _VROD_ROW}},
    ]
    context, count = build_structured_context(records, _project_spec())
    assert count == 1
    assert context.count("VCS5511") == 1


def test_build_structured_context_project_rows_skip_empty_documents():
    context, count = build_structured_context(
        [
            {"json_index": 1, "metadata": {}, "document": ""},
            {"json_index": 2, "metadata": {"row_data": _VROD_ROW}},
        ],
        _project_spec(),
    )
    assert count == 1


def test_scroll_cap_makes_counts_lower_bounds():
    context, count = build_structured_context(
        [{"json_index": 1, "metadata": {"program_name": "Alpha"}}],
        StructuredListSpec(
            source="test", status="", record_type="program",
            display_name="Test", qdrant_filter={},
        ),
        hit_scroll_cap=True,
    )
    assert count == 1
    assert "at least" in context
    assert "lower bounds" in context


def test_project_rows_without_project_id_are_excluded():
    """Tracker chunks sharing the document_id are not project rows."""
    records = [
        {"json_index": 1, "metadata": {"row_data": _VROD_ROW}},
        {"json_index": 2, "metadata": {}, "document": "Category: ARR. Program: Verified Carbon Standard. Methodology and Version(s): VM0047 - 1.1."},
        {"json_index": 3, "metadata": {}, "document": "Methodology ID: VM0047\nTitle: Afforestation, Reforestation, and Revegetation"},
    ]
    context, count = build_structured_context(records, _project_spec())
    assert count == 1
    assert "Rows: 1" in context
    assert "Category: ARR" not in context


def test_build_structured_context_size_cap_drops_whole_records_with_note():
    records = [
        {"json_index": i, "metadata": {"program_name": f"Program-{i:03d}"}}
        for i in range(50)
    ]
    spec = StructuredListSpec(
        source="test", status="", record_type="program",
        display_name="Test", qdrant_filter={},
    )
    full_context, full_count = build_structured_context(records, spec)
    assert full_count == 50

    capped_context, capped_count = build_structured_context(
        records, spec, max_chars=len(full_context) // 2,
    )
    # Count reflects all unique records parsed (consistent with any facts
    # header); the row list is cut at a whole-line boundary and annotated.
    assert capped_count == 50
    assert capped_context.count("Program-") < 50
    assert len(capped_context) <= len(full_context) // 2
    assert "partial" in capped_context
    # Every included record is a whole line — never cut mid-record
    for line in capped_context.splitlines()[3:]:
        assert line.endswith(".")


# ---------------------------------------------------------------------------
# Project dataset facts (deterministic aggregates)
# ---------------------------------------------------------------------------

_VROD_ROW_B = {
    "Project ID": "VCS5085",
    "Project Name": "Tond Tenga",
    "Voluntary Registry": "VCS",
    "Voluntary Status": "Registered",
    "Total Credits Issued": "0",
    "Total Credits Retired": "0",
    "Total Credits Remaining": "0",
    "Country": "Burkina Faso",
    "Project Registered": "04-04-2025",
}

_VROD_ROW_C = {
    "Project ID": "VCS3196",
    "Project Name": "Paracel ARR Carbon Forestry Project",
    "Voluntary Status": "Under validation",
    "Total Credits Issued": "0",
    "Total Credits Retired": "0",
    "Total Credits Remaining": "0",
    "Country": "Peru",
}


def test_project_facts_are_computed_over_all_rows():
    records = [
        {"json_index": 1, "metadata": {"row_data": _VROD_ROW}},
        {"json_index": 2, "metadata": {"row_data": _VROD_ROW_B}},
        {"json_index": 3, "metadata": {"row_data": _VROD_ROW_C}},
    ]
    context, count = build_structured_context(records, _project_spec())
    assert count == 3
    assert "Rows: 3" in context
    assert "Registered=2" in context
    assert "Under validation=1" in context
    assert "Projects with credits issued: 1" in context
    assert "total issued=230119" in context
    assert "retired=75000" in context


def test_project_facts_do_not_invent_absent_numeric_columns():
    row = {
        "Project ID": "VCS1",
        "Total Credits Issued": "0",
        "Voluntary Status": "Registered",
    }
    context, count = build_structured_context(
        [{"json_index": 1, "metadata": {"row_data": row}}],
        _project_spec(),
    )
    assert count == 1
    assert "total issued=0" in context
    assert "retired=" not in context
    assert "remaining=" not in context


def test_project_facts_dedupe_before_aggregating():
    records = [
        {"json_index": 1, "metadata": {"row_data": _VROD_ROW}},
        {"json_index": 1, "metadata": {"row_data": _VROD_ROW}},
    ]
    context, count = build_structured_context(records, _project_spec())
    assert count == 1
    assert "Rows: 1" in context
    assert "total issued=230119" in context  # not doubled


def test_project_facts_survive_row_truncation():
    """Aggregates are exact even when the char budget cuts row lines."""
    records = [
        {"json_index": i, "metadata": {"row_data": _VROD_ROW}}
        for i in range(30)
    ]
    # Distinct json_index per copy: 30 unique rows, all Registered.
    context, count = build_structured_context(records, _project_spec(), max_chars=800)
    assert count == 30
    assert "Rows: 30" in context
    assert "Registered=30" in context
    assert "total issued=" + str(230119 * 30) in context
    assert "partial" in context


def test_supplement_mode_returns_facts_without_rows():
    records = [
        {"json_index": 1, "metadata": {"row_data": _VROD_ROW}},
        {"json_index": 2, "metadata": {"row_data": _VROD_ROW_C}},
    ]
    context, count = build_structured_context(records, _project_spec("supplement"))
    assert count == 2
    assert "Rows: 2" in context
    assert "Registered=1" in context
    assert "Project ID:" not in context  # no row lines


def test_aggregate_mode_caps_rows_at_a_bounded_sample():
    """A count question gets the exact number, not a multi-thousand-row dump."""
    records = [
        {"json_index": i, "metadata": {"row_data": {**_VROD_ROW, "Project ID": f"VCS{i:05d}"}}}
        for i in range(200)
    ]
    context, count = build_structured_context(records, _project_spec("aggregate"))
    assert count == 200
    assert "Rows: 200" in context
    assert "Registered=200" in context
    # Facts are computed over all 200; only a sample of rows is shown.
    assert context.count("Project ID:") == SAMPLE_ROW_COUNT
    assert len(context) < 3000

    enumerated, _ = build_structured_context(records, _project_spec("enumerate"))
    assert enumerated.count("Project ID:") == 200
    assert len(enumerated) > 10 * len(context)


def test_aggregate_mode_labels_rows_as_illustrative():
    """The model must not recount from the sample instead of using the facts."""
    records = [
        {"json_index": i, "metadata": {"row_data": {**_VROD_ROW, "Project ID": f"VCS{i:05d}"}}}
        for i in range(50)
    ]
    context, _ = build_structured_context(records, _project_spec("aggregate"))
    assert "10 of 50" in context
    assert "the counts above are the answer" in context


# ---------------------------------------------------------------------------
# build_structured_context edge cases
# ---------------------------------------------------------------------------

def test_build_structured_context_deduplicates():
    spec = StructuredListSpec(
        source="test", status="OK", record_type="program",
        display_name="Test", qdrant_filter={},
    )
    context, count = build_structured_context(
        [
            {"json_index": 1, "metadata": {"program_name": "Alpha"}},
            {"json_index": 1, "metadata": {"program_name": "Alpha"}},
            {"json_index": 2, "metadata": {"program_name": "Beta"}},
        ],
        spec,
    )
    assert count == 2
    assert context.count("Alpha") == 1


def test_build_structured_context_skips_empty_names():
    spec = StructuredListSpec(
        source="test", status="OK", record_type="program",
        display_name="Test", qdrant_filter={},
    )
    context, count = build_structured_context(
        [
            {"json_index": 1, "metadata": {"program_name": ""}},
            {"json_index": 2, "metadata": {"program_name": "Valid"}},
        ],
        spec,
    )
    assert count == 1
    assert "Valid" in context


def test_build_structured_context_program_format():
    spec = StructuredListSpec(
        source="test", status="CCP-Eligible", record_type="program",
        display_name="Test", qdrant_filter={},
    )
    context, count = build_structured_context(
        [{"json_index": 1, "metadata": {"program_name": "CAR", "status": "CCP-Eligible"}}],
        spec,
    )
    assert "Program: CAR" in context
    assert "Status: CCP-Eligible" in context
    assert count == 1


def test_build_structured_context_methodology_format():
    spec = StructuredListSpec(
        source="test", status="CCP-Approved", record_type="methodology",
        display_name="Test", qdrant_filter={},
    )
    context, count = build_structured_context(
        [{
            "json_index": 1,
            "metadata": {
                "program_name": "Isometric",
                "methodology_name": "Biochar - 1.0",
                "category": "Biochar",
                "status": "CCP-Approved",
            },
        }],
        spec,
    )
    assert "Program: Isometric" in context
    assert "Methodology: Biochar - 1.0" in context
    assert "Category: Biochar" in context
    assert count == 1


@pytest.mark.parametrize(
    ("record_type", "expected_label"),
    [("registry", "Registry")],
)
def test_build_structured_context_uses_entity_label(record_type, expected_label):
    spec = StructuredListSpec(
        source="test", status="", record_type=record_type,
        display_name="Test", qdrant_filter={},
    )
    context, count = build_structured_context(
        [{"json_index": 1, "metadata": {"title": "Example entity"}}],
        spec,
    )
    assert f"{expected_label}: Example entity" in context
    assert count == 1


def test_enumerate_prompt_is_capped_and_warns(monkeypatch, caplog):
    monkeypatch.setattr(
        prompt_module,
        "get_settings",
        lambda: SimpleNamespace(MAX_COMPLETE_LIST_CHARS=32),
    )
    context = "Z" * 64

    with caplog.at_level("WARNING", logger="src.query_processing.prompts"):
        prompt = build_query_prompt(
            query="List all Verra methodologies",
            context=context,
            summaries=[],
            structured_mode="enumerate",
        )

    assert "Z" * 32 in prompt
    assert "Z" * 33 not in prompt
    assert "MAX_COMPLETE_LIST_CHARS" in caplog.text
    # A truncated enumerate context must be annotated, never silently cut
    assert "partial" in prompt


def test_aggregate_prompt_gets_short_instruction_and_no_quiz():
    prompt = build_query_prompt(
        query="how many VM0047 projects are registered?",
        context="Dataset facts: Rows: 198.",
        summaries=[],
        structured_mode="aggregate",
        record_count=198,
    )
    assert "(198 records)" in prompt
    assert "Those numbers are the answer" in prompt
    # Aggregate answers are short summaries, not full lists.
    assert "Reproduce every record" not in prompt


def test_supplement_facts_do_not_count_as_kb_relevance():
    result = {
        "documents": ["Dataset facts", "Relevant methodology"],
        "metadatas": [
            {"structured_mode": "supplement"},
            {"source": "methodology.md"},
        ],
        "scores": [1.0, 0.35],
        "distances": [0.0, 0.65],
    }
    assert kb_top_relevance(result) == 0.35
    assert kb_top_relevance({
        "documents": ["Dataset facts"],
        "metadatas": [{"structured_mode": "supplement"}],
        "scores": [1.0],
        "distances": [0.0],
    }) == 0.0


# ---------------------------------------------------------------------------
# LangChainRetriever.retrieve_structured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_structured_scroll_formats_complete_dataset():
    retriever = LangChainRetriever(enable_reranking=False)
    retriever._ensure_initialized = lambda: None
    retriever._filter_builder = MagicMock()
    retriever._filter_builder.build_filter.return_value = "qdrant-filter"

    client = MagicMock()
    client.scroll.return_value = (
        [
            SimpleNamespace(
                id="point-1",
                payload={
                    "metadata": {
                        "json_index": 1,
                        "methodology_name": "VM0048",
                    },
                    "page_content": "source text",
                },
            ),
        ],
        None,
    )
    retriever._vector_store = SimpleNamespace(client=client)

    spec = StructuredListSpec(
        source="structured_query",
        status="",
        record_type="methodology",
        display_name="Verra methodologies",
        qdrant_filter={"registry": "Verra"},
    )
    result = await retriever.retrieve_structured(spec)

    assert result["structured_mode"] == "enumerate"
    assert "Complete dataset" in result["documents"][0]
    assert "Methodology: VM0048." in result["documents"][0]
    assert result["metadatas"][0]["structured_record_count"] == 1
    assert result["metadatas"][0]["source"] == "structured_query"
    assert result["metadatas"][0]["title"] == "Verra methodologies"
    client.scroll.assert_called_once_with(
        collection_name="cora_dense_only",
        scroll_filter="qdrant-filter",
        limit=min(_SCROLL_BATCH, _MAX_ENUMERATE_SCROLL),
        offset=None,
        with_payload=True,
        with_vectors=False,
    )


@pytest.mark.asyncio
async def test_retrieve_structured_supplementary_returns_facts_without_complete_list():
    retriever = LangChainRetriever(enable_reranking=False)
    retriever._ensure_initialized = lambda: None
    retriever._filter_builder = MagicMock()
    retriever._filter_builder.build_filter.return_value = "qdrant-filter"

    client = MagicMock()
    client.scroll.return_value = (
        [
            SimpleNamespace(
                id="point-1",
                payload={
                    "metadata": {
                        "json_index": 1,
                        "row_data": _VROD_ROW,
                        "row_id": "point-1",
                    },
                    "page_content": "",
                },
            ),
        ],
        None,
    )
    retriever._vector_store = SimpleNamespace(client=client)

    spec = StructuredListSpec(
        source="structured_query",
        status="",
        record_type="project",
        display_name="registry projects using VM0047",
        qdrant_filter={"methodology_codes": "VM0047", "doc_type": "dataset"},
        mode="supplement",
    )
    result = await retriever.retrieve_structured(spec)

    assert "structured_mode" not in result
    assert "Dataset facts" in result["documents"][0]
    assert "Registered=1" in result["documents"][0]
    assert "total issued=230119" in result["documents"][0]


def test_build_structured_context_hedges_when_source_truncated():
    """A dataset whose source file was cut at the ingestion row limit must not
    be presented as complete: counts become lower bounds with an explicit note."""
    spec = StructuredListSpec(
        source="structured_query",
        status="",
        record_type="project",
        display_name="registry projects using VM0047",
        qdrant_filter={"methodology_codes": "VM0047", "doc_type": "dataset"},
        mode="aggregate",
    )
    context, count = build_structured_context(
        [
            {
                "json_index": 0,
                "metadata": {
                    "row_data": _VROD_ROW,
                    "row_id": "r1",
                    "dataset_truncated": True,
                },
            },
        ],
        spec,
    )
    assert count == 1
    assert "at least 1 matching rows" in context
    assert "ingestion row limit" in context
    assert "lower bounds" in context


@pytest.mark.asyncio
async def test_retrieve_structured_marks_result_partial_when_source_truncated():
    """Truncated-source datasets keep structured formatting but carry
    ``structured_partial`` so coverage is not forced to 1.0 and web
    supplementation is not disabled."""
    retriever = LangChainRetriever(enable_reranking=False)
    retriever._ensure_initialized = lambda: None
    retriever._filter_builder = MagicMock()
    retriever._filter_builder.build_filter.return_value = "qdrant-filter"

    client = MagicMock()
    client.scroll.return_value = (
        [
            SimpleNamespace(
                id="point-1",
                payload={
                    "metadata": {
                        "json_index": 1,
                        "row_data": _VROD_ROW,
                        "row_id": "point-1",
                        "dataset_truncated": True,
                    },
                    "page_content": "",
                },
            ),
        ],
        None,
    )
    retriever._vector_store = SimpleNamespace(client=client)

    spec = StructuredListSpec(
        source="structured_query",
        status="",
        record_type="project",
        display_name="registry projects using VM0047",
        qdrant_filter={"methodology_codes": "VM0047", "doc_type": "dataset"},
        mode="aggregate",
    )
    result = await retriever.retrieve_structured(spec)

    # Formatting stays structured; completeness claims are dropped.
    assert result["structured_mode"] == "aggregate"
    assert result["structured_partial"] is True
    assert result["metadatas"][0]["structured_partial"] is True
    assert "at least" in result["documents"][0]


# ---------------------------------------------------------------------------
# retrieve_kb_results
# ---------------------------------------------------------------------------

def _mock_retriever(structured=None, vector=None, fusion=None):
    """Build a MagicMock retriever with explicitly supported methods."""
    spec = ["retrieve"]
    if structured is not None:
        spec.append("retrieve_structured")
    if fusion is not None:
        spec.append("retrieve_with_fusion")

    retriever = MagicMock(spec=spec)
    retriever.retrieve = AsyncMock(return_value=vector)
    if structured is not None:
        retriever.retrieve_structured = AsyncMock(return_value=structured)
    if fusion is not None:
        retriever.retrieve_with_fusion = AsyncMock(return_value=fusion)
    return retriever


@pytest.mark.asyncio
async def test_retrieve_kb_results_prefers_structured_when_spec_and_method_present():
    retriever = _mock_retriever(structured={"documents": ["struct"]})
    result = await retrieve_kb_results(
        retriever,
        query="List all Verra methodologies",
        original_query="List all Verra methodologies",
    )
    assert result == {"documents": ["struct"]}
    retriever.retrieve_structured.assert_awaited_once()
    retriever.retrieve.assert_not_called()


@pytest.mark.asyncio
async def test_retrieve_kb_results_falls_through_to_vector_on_empty_scroll():
    retriever = _mock_retriever(
        structured={"documents": [], "metadatas": [], "ids": [], "distances": []},
        vector={"documents": ["vector"]},
    )
    result = await retrieve_kb_results(
        retriever,
        query="List all Verra methodologies",
        original_query="List all Verra methodologies",
    )
    assert result == {"documents": ["vector"]}
    retriever.retrieve_structured.assert_awaited_once()
    retriever.retrieve.assert_awaited_once()


@pytest.mark.asyncio
async def test_retrieve_kb_results_uses_fusion_when_sub_queries_available():
    retriever = _mock_retriever(
        structured={"documents": [], "metadatas": [], "ids": [], "distances": []},
        fusion={"documents": ["fusion"]},
    )
    result = await retrieve_kb_results(
        retriever,
        query="List all Verra methodologies",
        original_query="List all Verra methodologies",
        sub_queries=["Verra methodologies", "Verra VM docs"],
    )
    assert result == {"documents": ["fusion"]}
    retriever.retrieve_with_fusion.assert_awaited_once()
    retriever.retrieve.assert_not_called()


@pytest.mark.asyncio
async def test_retrieve_kb_results_uses_vector_when_no_spec():
    retriever = _mock_retriever(vector={"documents": ["vector"]})
    result = await retrieve_kb_results(
        retriever,
        query="What is VM0048?",
        original_query="What is VM0048?",
    )
    assert result == {"documents": ["vector"]}
    assert not hasattr(retriever, "retrieve_structured")
    retriever.retrieve.assert_awaited_once()


@pytest.mark.asyncio
async def test_retrieve_kb_results_preserves_vector_retrieval_contract():
    retriever = _mock_retriever(vector={"documents": ["vector"]})
    await retrieve_kb_results(
        retriever,
        query="What is VM0048?",
        original_query="Can you explain VM0048?",
        metadata_filters={"category": "methodology"},
    )

    retriever.retrieve.assert_awaited_once_with(
        query="What is VM0048?",
        where={"category": "methodology"},
        allow_unfiltered_fallback=True,
        original_query="Can you explain VM0048?",
    )


@pytest.mark.asyncio
async def test_retrieve_kb_results_preserves_fusion_retrieval_contract():
    retriever = _mock_retriever(
        fusion={"documents": ["fusion"]},
    )
    await retrieve_kb_results(
        retriever,
        query="VM0048 methodology requirements",
        original_query="What are the VM0048 methodology requirements?",
        metadata_filters={"category": "methodology"},
        sub_queries=["VM0048 requirements"],
    )

    retriever.retrieve_with_fusion.assert_awaited_once_with(
        query="VM0048 methodology requirements",
        sub_queries=["VM0048 requirements"],
        where={"category": "methodology"},
        allow_unfiltered_fallback=True,
        original_query="What are the VM0048 methodology requirements?",
    )


@pytest.mark.asyncio
async def test_retrieve_kb_results_falls_back_to_vector_on_expected_exception():
    retriever = _mock_retriever(
        structured={"documents": []},
        vector={"documents": ["vector"]},
    )
    retriever.retrieve_structured = AsyncMock(
        side_effect=ResponseHandlingException(RuntimeError("scroll failed"))
    )
    result = await retrieve_kb_results(
        retriever,
        query="List all Verra methodologies",
        original_query="List all Verra methodologies",
    )
    assert result == {"documents": ["vector"]}
    retriever.retrieve.assert_awaited_once()


@pytest.mark.asyncio
async def test_retrieve_kb_results_propagates_programming_errors():
    retriever = _mock_retriever(structured={"documents": []})
    retriever.retrieve_structured = AsyncMock(side_effect=RuntimeError("bug"))

    with pytest.raises(RuntimeError, match="bug"):
        await retrieve_kb_results(
            retriever,
            query="List all Verra methodologies",
            original_query="List all Verra methodologies",
        )

    retriever.retrieve.assert_not_called()


@pytest.mark.asyncio
async def test_retrieve_kb_results_returns_empty_on_total_expected_failure():
    retriever = _mock_retriever(
        structured={"documents": []},
        vector={"documents": []},
    )
    retriever.retrieve_structured = AsyncMock(
        side_effect=ResponseHandlingException(RuntimeError("scroll failed"))
    )
    retriever.retrieve = AsyncMock(
        side_effect=ResponseHandlingException(RuntimeError("vector failed"))
    )
    result = await retrieve_kb_results(
        retriever,
        query="List all Verra methodologies",
        original_query="List all Verra methodologies",
    )
    assert result["documents"] == []
    assert result["metadatas"] == []
    assert result["ids"] == []
    assert result["distances"] == []
    assert "scores" in result


@pytest.mark.asyncio
async def test_retrieve_kb_results_supplement_prepends_facts_to_vector_results():
    """Supplement mode prepends facts so they survive _prepare_context's cap."""
    retriever = _mock_retriever(
        structured={
            "ids": ["fact-1"],
            "documents": ["Dataset facts: Rows: 204, Registered=5"],
            "metadatas": [{
                "source": "Voluntary-Registry-Offsets-Database-v2026-06.jsonl",
                "structured_mode": "supplement",
            }],
            "distances": [0.0],
        },
        vector={
            "ids": ["vec-1"],
            "documents": ["vector doc"],
            "metadatas": [{"source": "some-doc.md"}],
            "distances": [0.4],
        },
    )
    result = await retrieve_kb_results(
        retriever,
        query="vm0047 project prices",
        original_query="are there clear signals for vm0047 prices now that 5 projects are registered with vcs?",
    )
    retriever.retrieve_structured.assert_awaited_once()
    retriever.retrieve.assert_awaited_once()
    # Prepended: facts come first so context preparation keeps them; the
    # result must not be marked structured_mode (web stays available).
    assert result["documents"][0].startswith("Dataset facts")
    assert result["documents"][1] == "vector doc"
    assert "structured_mode" not in result


@pytest.mark.asyncio
async def test_retrieve_kb_results_supplement_skips_prepend_on_empty_scroll():
    retriever = _mock_retriever(
        structured={"documents": [], "metadatas": [], "ids": [], "distances": []},
        vector={"documents": ["vector"], "metadatas": [], "ids": [], "distances": []},
    )
    result = await retrieve_kb_results(
        retriever,
        query="vm0047 project prices",
        original_query="vm0047 project prices",
    )
    retriever.retrieve_structured.assert_awaited_once()
    retriever.retrieve.assert_awaited_once()
    assert result["documents"] == ["vector"]
