"""
Tests for CitationManager - Phase 1: Source Type Classification
Phase 2: Source Name Cleaning
"""

import pytest
from types import SimpleNamespace

from src.agents.route_processors import RouteProcessor
from src.citations.citation_manager import (
    CitationManager,
    Citation,
    _ALL_KB_EXTENSIONS,
)
from src.citations.config import _EXTENSION_STRIP_RE


class TestSourceTypeClassification:
    """Test that source_type is correctly set for KB and web sources."""
    
    def setup_method(self):
        self.manager = CitationManager(min_relevance_score=0.3)
    
    def test_kb_citations_use_knowledge_base_type(self):
        """KB citations from vector results should use 'knowledge_base' as source_type."""
        vector_results = {
            "documents": ["Document content about carbon pricing."],
            "metadatas": [{"file_name": "carbon_pricing.md", "id": "doc_1"}],
            "distances": [0.2]  # High relevance
        }
        
        citations = self.manager.extract_citations_from_vector_results(vector_results)
        
        assert len(citations) == 1
        assert citations[0].source_type == "knowledge_base"
    
    def test_web_citations_default_to_web_type(self):
        """Web citations without explicit type should default to 'web'."""
        web_results = {
            "sources": [
                {"title": "Climate News", "url": "https://example.com", "snippet": "News article"}
            ]
        }
        
        citations = self.manager.extract_citations_from_web_results(web_results)
        
        assert len(citations) == 1
        assert citations[0].source_type == "web"

    def test_file_like_web_source_classified_as_knowledge_base(self):
        """File-like sources in web flow should still be classified as knowledge_base."""
        web_results = {
            "sources": [
                {
                    "title": "icvcm%20a%20framework.jsonl",
                    "url": "",
                    "snippet": "Framework content"
                }
            ]
        }

        citations = self.manager.extract_citations_from_web_results(web_results)

        assert len(citations) == 1
        assert citations[0].source_type == "knowledge_base"
        assert citations[0].url is None

    def test_hybrid_kb_sources_keep_knowledge_base_type(self):
        """KB sources passed through hybrid routes should keep 'knowledge_base' type."""
        # Simulates what web_search.py returns for KB sources in hybrid routes
        web_results = {
            "sources": [
                {"title": "Internal Doc", "url": "", "snippet": "", "type": "knowledge_base"},
                {"title": "Web Result", "url": "https://example.com", "snippet": "Web content", "type": "web"}
            ]
        }
        
        citations = self.manager.extract_citations_from_web_results(web_results)
        
        assert len(citations) == 2
        assert citations[0].source_type == "knowledge_base"
        assert citations[1].source_type == "web"
    
    def test_string_sources_default_to_web(self):
        """String sources (legacy format) should default to 'web' type."""
        web_results = {
            "sources": ["Just a string title"]
        }
        
        citations = self.manager.extract_citations_from_web_results(web_results)
        
        assert len(citations) == 1
        assert citations[0].source_type == "web"
    
    def test_merged_citations_preserve_source_types(self):
        """Merged citations should preserve their original source types."""
        kb_citations = [
            Citation(
                source_id="kb_1",
                source_name="KB Document",
                source_type="knowledge_base",
                content_snippet="KB content",
                relevance_score=0.9
            )
        ]
        
        web_citations = [
            Citation(
                source_id="web_1",
                source_name="Web Article",
                source_type="web",
                content_snippet="Web content",
                relevance_score=0.8,
                url="https://example.com"
            )
        ]
        
        merged = self.manager.merge_citations(kb_citations, web_citations)
        
        assert len(merged) == 2
        source_types = {c.source_name: c.source_type for c in merged}
        assert source_types["KB Document"] == "knowledge_base"
        assert source_types["Web Article"] == "web"

    def test_web_source_explicit_score_preferred(self):
        """When provided, source relevance_score should be used over rank heuristic."""
        web_results = {
            "sources": [
                {"title": "Result A", "url": "https://a.example", "snippet": "A", "relevance_score": 0.42},
                {"title": "Result B", "url": "https://b.example", "snippet": "B", "score": 0.87},
            ]
        }

        citations = self.manager.extract_citations_from_web_results(web_results, max_citations=5)

        assert len(citations) == 2
        assert citations[0].relevance_score == 0.42
        assert citations[1].relevance_score == 0.87


class TestCitationDisplay:
    """Test citation display formatting edge cases."""

    def test_page_number_zero_preserved_in_display(self):
        """Display format should include page 0 explicitly."""
        citation = Citation(
            source_id="doc_1",
            source_name="Sample Doc",
            source_type="knowledge_base",
            content_snippet="Content",
            relevance_score=0.8,
            page_number=0,
        )

        display = citation.to_display_format()
        assert "p. 0" in display


class TestSnippetSanitization:
    """Test snippet sanitization behavior for sensitive-content redaction."""

    def setup_method(self):
        self.manager = CitationManager()

    def test_prefixed_secret_like_token_redacted(self):
        """Secret-like tokens with common prefixes should be redacted."""
        snippet = "Use api_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 for this integration."
        sanitized = self.manager._sanitize_snippet(snippet)
        assert "[REDACTED]" in sanitized
        assert "api_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890" not in sanitized

    def test_uuid_not_over_redacted(self):
        """UUIDs should not be redacted by the generic secret regex."""
        snippet = "Document id is 550e8400-e29b-41d4-a716-446655440000 for audit traceability."
        sanitized = self.manager._sanitize_snippet(snippet)
        assert "550e8400-e29b-41d4-a716-446655440000" in sanitized

    def test_technical_equals_content_not_redacted_as_env(self):
        """Technical definitions should not be redacted as ENV assignments."""
        snippet = "CO2=400ppm is a measurement, and UNFCCC=United Nations convention is a definition."
        sanitized = self.manager._sanitize_snippet(snippet)
        assert "CO2=400ppm" in sanitized
        assert "UNFCCC=United Nations" in sanitized


class TestCitationExtraction:
    """Test basic citation extraction functionality."""
    
    def setup_method(self):
        self.manager = CitationManager(min_relevance_score=0.3)
    
    def test_relevance_score_filter(self):
        """Citations below min_relevance_score should be filtered out."""
        # With normalize_score: score = 1 - (distance / 2)
        # distance=0.2 → score=0.9 (pass), distance=1.6 → score=0.2 (filtered, < 0.3)
        vector_results = {
            "documents": ["Good content", "Bad content"],
            "metadatas": [{"file_name": "good.md"}, {"file_name": "bad.md"}],
            "distances": [0.2, 1.6]  # First is high relevance, second is low
        }
        
        citations = self.manager.extract_citations_from_vector_results(vector_results)
        
        assert len(citations) == 1
        assert "Good" in citations[0].source_name  # cleaned: extension stripped, title-cased
    
    def test_max_citations_limit(self):
        """Should respect max_citations parameter."""
        vector_results = {
            "documents": ["Doc 1", "Doc 2", "Doc 3", "Doc 4", "Doc 5"],
            "metadatas": [{"file_name": f"doc_{i}.md"} for i in range(5)],
            "distances": [0.1] * 5
        }
        
        citations = self.manager.extract_citations_from_vector_results(vector_results, max_citations=3)
        
        assert len(citations) == 3


class TestFormatCitationsForResponse:
    """Test citation formatting for API response."""
    
    def setup_method(self):
        self.manager = CitationManager()
    
    def test_source_type_in_formatted_response(self):
        """Formatted response should include source_type in details."""
        citations = [
            Citation(
                source_id="kb_1",
                source_name="KB Doc",
                source_type="knowledge_base",
                content_snippet="Content",
                relevance_score=0.9
            ),
            Citation(
                source_id="web_1",
                source_name="Web Article",
                source_type="web",
                content_snippet="Web content",
                relevance_score=0.8,
                url="https://example.com"
            )
        ]
        
        formatted = self.manager.format_citations_for_response(citations)
        
        assert formatted["count"] == 2
        assert len(formatted["details"]) == 2
        
        # Check source types are preserved in details
        # Note: source_name is cleaned (title-cased) in formatted output
        source_types = {d["source_type"] for d in formatted["details"]}
        assert "knowledge_base" in source_types
        assert "web" in source_types

    def test_formatted_response_exact_payload_shape(self):
        """Formatted response should match expected API payload shape."""
        citations = [
            Citation(
                source_id="kb_1",
                source_name="data\\icvcm%20a%20framework.jsonl",
                source_type="knowledge_base",
                content_snippet="This contains INTERNAL_TOKEN=abc123 and contact test@example.com",
                relevance_score=0.91,
                page_number=12,
                section="2.1"
            ),
            Citation(
                source_id="web_1",
                source_name="Climate News",
                source_type="web",
                content_snippet="Public web snippet",
                relevance_score=0.83,
                url="https://example.com/article"
            )
        ]

        formatted = self.manager.format_citations_for_response(citations, include_snippets=True)

        assert formatted == {
            "count": 2,
            "sources": ["Icvcm a Framework", "Climate News"],
            "details": [
                {
                    "source_name": "Icvcm a Framework",
                    "source_type": "knowledge_base",
                    "relevance_score": 0.91,
                    "page_number": 12,
                    "section": "2.1",
                    "snippet": "This contains INTERNAL_TOKEN=abc123 and contact [EMAIL]"
                },
                {
                    "source_name": "Climate News",
                    "source_type": "web",
                    "relevance_score": 0.83,
                    "url": "https://example.com/article",
                    "snippet": "Public web snippet"
                }
            ]
        }

    def test_page_number_zero_preserved_in_response(self):
        """Page number 0 should be preserved in API payload."""
        citations = [
            Citation(
                source_id="kb_1",
                source_name="Doc Zero",
                source_type="knowledge_base",
                content_snippet="Snippet",
                relevance_score=0.9,
                page_number=0,
            )
        ]

        formatted = self.manager.format_citations_for_response(citations)
        assert formatted["details"][0]["page_number"] == 0


class TestCleanSourceName:
    """Test clean_source_name() function for Phase 2."""
    
    def setup_method(self):
        self.manager = CitationManager()
    
    def test_url_decoding(self):
        """Percent-encoded characters should be decoded."""
        result = self.manager.clean_source_name("icvcm%20a%20framework.jsonl")
        assert result == "Icvcm a Framework"
    
    def test_jsonl_extension_stripped(self):
        """ .jsonl extension should be stripped like other extensions."""
        result = self.manager.clean_source_name("document.jsonl")
        assert result == "Document"
    
    def test_version_prefix_stripped(self):
        """Version prefixes like 431_v1.2_ should be stripped."""
        result = self.manager.clean_source_name("431_v1.2_ee_rules.txt")
        assert result == "Ee Rules"
    
    def test_underscores_replaced_with_spaces(self):
        """Underscores should be replaced with spaces."""
        result = self.manager.clean_source_name("my_document_name.md")
        assert result == "My Document Name"
    
    def test_hyphens_replaced_with_spaces(self):
        """Hyphens should be replaced with spaces."""
        result = self.manager.clean_source_name("trees-2.0-august-2021.md")
        assert result == "Trees 2.0 August 2021"
    
    def test_path_prefix_stripped(self):
        """Path prefixes like data\\ should be stripped."""
        result = self.manager.clean_source_name("data\\State and Trends.md")
        assert result == "State and Trends"

    def test_minor_words_lowercased_in_title_case(self):
        """Minor words should be lowercased except when first token."""
        result = self.manager.clean_source_name("state_and_trends_of_carbon_pricing_2025.md")
        assert result == "State and Trends of Carbon Pricing 2025"
    
    def test_title_casing(self):
        """Result should be title-cased for readability."""
        result = self.manager.clean_source_name("carbon_pricing_guide.md")
        assert result == "Carbon Pricing Guide"
    
    def test_version_numbers_preserved(self):
        """Version numbers like 2.0 should be preserved, not title-cased."""
        result = self.manager.clean_source_name("vm0048_v2.0_methodology.txt")
        assert "2.0" in result
        assert "V2.0" not in result  # Should not become "V2.0" with capital V
    
    def test_empty_string(self):
        """Empty string should return empty string."""
        result = self.manager.clean_source_name("")
        assert result == ""
    
    def test_multiple_special_chars(self):
        """Multiple special characters should be cleaned up."""
        result = self.manager.clean_source_name("my_file___name--test.md")
        assert result == "My File Name Test"
    
    def test_known_acronyms_uppercased_from_lowercase(self):
        """Known acronyms should be normalized to uppercase for readability."""
        result = self.manager.clean_source_name("ar6 wg3 report.md")
        assert result == "AR6 WG3 Report"

    def test_expanded_known_acronyms_uppercased(self):
        """Expanded domain acronyms should be normalized to uppercase."""
        result = self.manager.clean_source_name("ndc mrv ets guidance.md")
        assert result == "NDC MRV ETS Guidance"


class TestCitationFiltering:
    """Test filter_citations_by_answer() for Phase 3."""
    
    def setup_method(self):
        self.manager = CitationManager()
    
    def test_filter_by_source_name_match(self):
        """Citations with source name in answer should be kept."""
        citations = [
            Citation(
                source_id="doc_1",
                source_name="Carbon Pricing Guide",
                source_type="knowledge_base",
                content_snippet="Information about carbon pricing mechanisms.",
                relevance_score=0.9
            ),
            Citation(
                source_id="doc_2",
                source_name="Unrelated Document",
                source_type="knowledge_base",
                content_snippet="Completely different topic.",
                relevance_score=0.8
            )
        ]
        answer = "According to the Carbon Pricing Guide, there are several mechanisms..."
        
        filtered = self.manager.filter_citations_by_answer(citations, answer)
        
        assert len(filtered) == 1
        assert filtered[0].source_name == "Carbon Pricing Guide"
    
    def test_filter_by_snippet_terms(self):
        """Citations with matching snippet terms should be kept."""
        citations = [
            Citation(
                source_id="doc_1",
                source_name="Climate Report",
                source_type="knowledge_base",
                content_snippet="The renewable energy sector has seen significant growth in wind and solar power.",
                relevance_score=0.9
            ),
            Citation(
                source_id="doc_2",
                source_name="Other Report",
                source_type="knowledge_base",
                content_snippet="Unrelated content about cooking recipes.",
                relevance_score=0.8
            )
        ]
        answer = "The renewable energy sector including wind and solar power has grown significantly."
        
        filtered = self.manager.filter_citations_by_answer(citations, answer)
        
        # First citation should pass due to matching terms
        assert any(c.source_name == "Climate Report" for c in filtered)

    def test_ratio_filter_rejects_long_boilerplate_with_few_overlaps(self):
        """Long domain boilerplate snippets should not pass on a few shared terms."""
        citations = [
            Citation(
                source_id="doc_1",
                source_name="Boilerplate",
                source_type="knowledge_base",
                content_snippet=(
                    "carbon project methodology protocol verification baseline additional guidance "
                    "registry issuance reductions permanence monitoring leakage quantification "
                    "conservative assumptions uncertainty boundaries eligibility validation "
                    "auditor accreditation assurance framework governance implementation details"
                ),
                relevance_score=0.9,
            )
        ]
        answer = "This answer only mentions carbon protocol verification in passing."

        filtered = self.manager.filter_citations_by_answer(citations, answer)
        assert filtered == []

    def test_ratio_filter_keeps_dense_short_overlap(self):
        """Short focused snippets with dense overlap should pass."""
        citations = [
            Citation(
                source_id="doc_1",
                source_name="Focused Snippet",
                source_type="knowledge_base",
                content_snippet="verification workflow requires baseline monitoring and leakage checks",
                relevance_score=0.9,
            )
        ]
        answer = "The baseline monitoring and leakage checks are part of the verification workflow."

        filtered = self.manager.filter_citations_by_answer(citations, answer)
        assert len(filtered) == 1
        assert filtered[0].source_name == "Focused Snippet"
    
    def test_no_fallback_when_no_matches(self):
        """Should return empty list when no citations match answer evidence."""
        citations = [
            Citation(
                source_id="doc_1",
                source_name="Document A",
                source_type="knowledge_base",
                content_snippet="Content about topic A.",
                relevance_score=0.9
            ),
            Citation(
                source_id="doc_2",
                source_name="Document B",
                source_type="knowledge_base",
                content_snippet="Content about topic B.",
                relevance_score=0.7
            ),
            Citation(
                source_id="doc_3",
                source_name="Document C",
                source_type="knowledge_base",
                content_snippet="Content about topic C.",
                relevance_score=0.5
            )
        ]
        answer = "This answer mentions nothing from any document."
        
        filtered = self.manager.filter_citations_by_answer(citations, answer)
        
        assert filtered == []
    
    def test_empty_citations_returns_empty(self):
        """Empty citations list should return empty list."""
        filtered = self.manager.filter_citations_by_answer([], "Some answer")
        assert filtered == []
    
    def test_empty_answer_returns_empty(self):
        """Empty answer should return empty list (no evidence to support citations)."""
        citations = [
            Citation(
                source_id="doc_1",
                source_name="Doc",
                source_type="knowledge_base",
                content_snippet="Content",
                relevance_score=0.9
            )
        ]
        filtered = self.manager.filter_citations_by_answer(citations, "")
        assert filtered == []
    
    def test_multiple_matching_citations(self):
        """All matching citations should be returned."""
        citations = [
            Citation(
                source_id="doc_1",
                source_name="Report A",
                source_type="knowledge_base",
                content_snippet="Carbon credits and offsets are important mechanisms.",
                relevance_score=0.9
            ),
            Citation(
                source_id="doc_2",
                source_name="Report B",
                source_type="knowledge_base",
                content_snippet="Carbon credits trading has increased.",
                relevance_score=0.8
            ),
            Citation(
                source_id="doc_3",
                source_name="Unrelated",
                source_type="knowledge_base",
                content_snippet="Cooking recipes and food.",
                relevance_score=0.7
            )
        ]
        answer = "According to Report A and Report B, carbon credits are essential."
        
        filtered = self.manager.filter_citations_by_answer(citations, answer)
        
        assert len(filtered) == 2
        source_names = {c.source_name for c in filtered}
        assert "Report A" in source_names
        assert "Report B" in source_names
        assert "Unrelated" not in source_names


class TestCitationSuppression:
    """Test citation suppression for conversational queries - Phase 4."""
    
    def setup_method(self):
        self.manager = CitationManager()
    
    def test_greeting_detected_short(self):
        """Short greetings should be detected."""
        assert self.manager.is_conversational_query("hi")
        assert self.manager.is_conversational_query("hello")
        assert self.manager.is_conversational_query("hey")
        assert self.manager.is_conversational_query("thanks")
        assert self.manager.is_conversational_query("hiii")
        assert self.manager.is_conversational_query("heyyy")

    def test_healthcheck_style_noise_detected(self):
        """Low-information probe queries should be detected as conversational."""
        assert self.manager.is_conversational_query("test")
        assert self.manager.is_conversational_query("asdf")
        assert self.manager.is_conversational_query("can you hear me")
    
    def test_greeting_detected_with_name(self):
        """Greetings with names should be detected."""
        assert self.manager.is_conversational_query("Hi there")
        assert self.manager.is_conversational_query("Hello, Cora")
        assert self.manager.is_conversational_query("Hey assistant")
    
    def test_meta_questions_detected(self):
        """Meta questions about the assistant should be detected."""
        assert self.manager.is_conversational_query("What can you do?")
        assert self.manager.is_conversational_query("Who are you?")
        assert self.manager.is_conversational_query("How can you help me?")

    def test_meta_phrase_with_substantive_remainder_not_detected(self):
        """Meta phrase should not trigger conversational mode when followed by a real query."""
        assert not self.manager.is_conversational_query("Help me understand carbon pricing rules")

    def test_greeting_prefix_with_real_question_not_detected(self):
        """Greeting prefix + substantive question should go through RAG."""
        assert not self.manager.is_conversational_query("Hi, what is VCS?")

    def test_over_length_query_not_detected_as_conversational(self):
        """Long queries should bypass greeting suppression and go to retrieval."""
        long_query = (
            "Hi there can you explain with examples the methodology boundaries, monitoring periods, "
            "baselines, leakage treatment, permanence buffers, and verification workflow for VCS projects?"
        )
        assert not self.manager.is_conversational_query(long_query)
    
    def test_normal_query_not_detected(self):
        """Normal queries should NOT be detected as conversational."""
        assert not self.manager.is_conversational_query("What is carbon pricing?")
        assert not self.manager.is_conversational_query("Tell me about VM0048")
        assert not self.manager.is_conversational_query("How do carbon credits work?")
    
    def test_suppress_for_greeting_query(self):
        """Should suppress citations for greeting queries."""
        citations = [
            Citation(
                source_id="doc_1",
                source_name="Some Doc",
                source_type="knowledge_base",
                content_snippet="Content",
                relevance_score=0.9
            )
        ]
        should_suppress = self.manager.should_suppress_citations(
            query="Hi there!",
            answer="Hello! How can I help you today?",
            citations=citations,
            coverage_score=0.5
        )
        assert should_suppress
    
    def test_suppress_for_low_coverage_no_citations(self):
        """Should suppress when coverage is low and no citations matched."""
        should_suppress = self.manager.should_suppress_citations(
            query="What is X?",
            answer="I don't have information about X.",
            citations=[],  # No citations after filtering
            coverage_score=0.1
        )
        assert should_suppress
    
    def test_suppress_for_short_greeting_response(self):
        """Should suppress for short greeting-like responses."""
        should_suppress = self.manager.should_suppress_citations(
            query="Hello",
            answer="Hi! I'm happy to help with any questions.",
            citations=[],
            coverage_score=0.5
        )
        assert should_suppress
    
    def test_no_suppress_for_normal_query(self):
        """Should NOT suppress citations for normal queries with relevant content."""
        citations = [
            Citation(
                source_id="doc_1",
                source_name="Carbon Guide",
                source_type="knowledge_base",
                content_snippet="Carbon pricing information",
                relevance_score=0.9
            )
        ]
        should_suppress = self.manager.should_suppress_citations(
            query="What is carbon pricing?",
            answer="According to the Carbon Guide, carbon pricing is...",
            citations=citations,
            coverage_score=0.8
        )
        assert not should_suppress
    
    def test_empty_query_not_conversational(self):
        """Empty query should return False (not conversational)."""
        assert not self.manager.is_conversational_query("")
        assert not self.manager.is_conversational_query(None)

    def test_greeting_with_self_introduction_detected(self):
        """Greeting + self-introduction should be detected as conversational (regression)."""
        assert self.manager.is_conversational_query("Hi, My name is Elon")
        assert self.manager.is_conversational_query("Hello, my name is Alice")
        assert self.manager.is_conversational_query("Hey I am Bob")
        assert self.manager.is_conversational_query("Hi I'm Sarah")
        assert self.manager.is_conversational_query("Hello, call me Dave")

    def test_standalone_self_introduction_detected(self):
        """Standalone self-introductions should be detected as conversational."""
        assert self.manager.is_conversational_query("My name is Elon")
        assert self.manager.is_conversational_query("I am John")
        assert self.manager.is_conversational_query("Call me Bob")

    def test_self_introduction_with_question_not_detected(self):
        """Self-introduction followed by a real question should NOT be conversational."""
        assert not self.manager.is_conversational_query(
            "Hi, my name is Elon, what is the release of VM0048?"
        )


class TestCitationFixRegressions:
    """Merged bug-fix regressions from test_citation_fixes.py."""

    def setup_method(self):
        self.manager = CitationManager()

    def test_all_extensions_in_module_constant(self):
        expected = {
            ".pdf", ".doc", ".docx", ".txt", ".md", ".csv", ".json", ".jsonl",
            ".xml", ".yaml", ".yml", ".xlsx", ".xls", ".ppt", ".pptx", ".parquet",
            ".rst",
        }
        assert _ALL_KB_EXTENSIONS == expected

    def test_kb_extensions_uses_module_constant(self):
        assert self.manager._kb_extensions is _ALL_KB_EXTENSIONS

    def test_extension_regex_matches_all(self):
        for ext in _ALL_KB_EXTENSIONS:
            name = f"document{ext}"
            result = _EXTENSION_STRIP_RE.sub("", name)
            assert result == "document", f"Regex failed to strip {ext}"

    def test_kb_source_with_url_still_cleaned(self):
        citation = Citation(
            source_id="1",
            source_name="data/431_v1.2_methodology.pdf",
            source_type="knowledge_base",
            content_snippet="test",
            relevance_score=0.8,
            url="https://example.com/docs/methodology.pdf",
        )
        result = self.manager.format_citations_for_response([citation])
        assert result["sources"][0] == "Methodology"

    def test_short_answer_with_hi_not_suppressed(self):
        citations = [
            Citation(
                source_id="1",
                source_name="Test",
                source_type="knowledge_base",
                content_snippet="test",
                relevance_score=0.8,
            )
        ]
        result = self.manager.should_suppress_citations(
            query="What is the answer?",
            answer="Hi — the answer is 42.",
            citations=citations,
            coverage_score=0.5,
        )
        assert result is False


class _DummyRetriever:
    def __init__(self, vector_results):
        self._vector_results = vector_results

    async def retrieve(self, query, where=None, **kwargs):
        return self._vector_results


class _DummyAnswerGenerator:
    def __init__(self, result):
        self._result = result

    async def search_and_process(self, query, vector_results):
        return dict(self._result)

    async def check_query_cache(self, query):
        return None


class _DummyWebSearch:
    def __init__(self, search_result, hybrid_result=None):
        self._search_result = search_result
        self._hybrid_result = hybrid_result or search_result

    async def search(self, query, timeout_ms=None):
        return dict(self._search_result)

    async def search_with_kb_context(self, query, kb_context, kb_sources, timeout_ms=None):
        return dict(self._hybrid_result)


def _build_route_processor_config(**overrides):
    base = {
        "retrieval_threshold": 0.3,
        "enable_web_search": False,
        "retrieval_k": 5,
        "parallel_retrieval": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestRouteProcessorCitationRegressions:
    """Merged route-level citation behavior regressions."""

    @pytest.mark.asyncio
    async def test_process_kb_route_supplements_on_explicit_non_answer_fallback(self):
        vector_results = {
            "documents": [
                "ICVCM sets integrity standards for voluntary carbon markets.",
                "ICVCM developed the Core Carbon Principles framework.",
                "ICVCM works with registries and standard setters.",
                "ICVCM guidance helps assess high-integrity credits.",
                "ICVCM governance includes independent council oversight.",
            ],
            "metadatas": [
                {"file_name": f"icvcm_{i}.md"} for i in range(5)
            ],
            "distances": [0.1, 0.15, 0.2, 0.25, 0.3],
        }
        answer_result = {
            "answer": "Information not found, try rephrasing your question again.",
            "sources": ["icvcm_0.md"],
            "coverage_score": 1.0,
        }
        hybrid_result = {
            "answer": "ICVCM is the Integrity Council for the Voluntary Carbon Market.",
            "sources": [
                {
                    "title": "ICVCM Overview",
                    "url": "https://example.com/icvcm-overview",
                    "snippet": "Integrity Council for the Voluntary Carbon Market overview.",
                }
            ],
            "timed_out": False,
            "budget_exceeded": False,
        }

        processor = RouteProcessor(
            retriever=_DummyRetriever(vector_results),
            answer_generator=_DummyAnswerGenerator(answer_result),
            web_search=_DummyWebSearch(search_result={"answer": "", "sources": []}, hybrid_result=hybrid_result),
            citation_manager=CitationManager(min_relevance_score=0.0),
            config=_build_route_processor_config(
                enable_web_search=True,
                retrieval_k=5,
            ),
        )

        steps = []
        result = await processor.process_kb_route(
            query="What is ICVCM?",
            original_query="What is ICVCM?",
            metadata_filters=None,
            steps=steps,
        )

        assert "Integrity Council for the Voluntary Carbon Market" in result["answer"]
        assert any(step.name == "Web Supplementation" for step in steps)

    @pytest.mark.asyncio
    async def test_process_kb_route_filters_irrelevant_citations_and_sources(self):
        vector_results = {
            "documents": ["carbon credit verification methodology standard"],
            "metadatas": [{"file_name": "data/431_v1.2_methodology.pdf"}],
            "distances": [0.1],
        }
        answer_result = {
            "answer": "This answer intentionally avoids matching document terms.",
            "sources": ["data/431_v1.2_methodology.pdf"],
            "coverage_score": 0.9,
        }

        processor = RouteProcessor(
            retriever=_DummyRetriever(vector_results),
            answer_generator=_DummyAnswerGenerator(answer_result),
            web_search=_DummyWebSearch(search_result={"answer": "", "sources": []}),
            citation_manager=CitationManager(min_relevance_score=0.0),
            config=_build_route_processor_config(enable_web_search=False),
        )

        result = await processor.process_kb_route(
            query="methodology details",
            original_query="methodology details",
            metadata_filters=None,
            steps=[],
        )

        assert result["citations"] == []
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_process_web_route_suppresses_citations_for_greeting_query(self):
        web_result = {
            "answer": "How can I assist you today?",
            "sources": [
                {
                    "title": "Assistant Greeting",
                    "url": "https://example.com/greeting",
                    "snippet": "General greeting",
                }
            ],
            "timed_out": False,
            "budget_exceeded": False,
            "grounded": True,
        }

        processor = RouteProcessor(
            retriever=_DummyRetriever({"documents": [], "metadatas": [], "distances": []}),
            answer_generator=_DummyAnswerGenerator({"answer": "", "sources": []}),
            web_search=_DummyWebSearch(search_result=web_result),
            citation_manager=CitationManager(min_relevance_score=0.0),
            config=_build_route_processor_config(enable_web_search=True),
        )

        result = await processor.process_web_route(
            query="hi",
            original_query="hi",
            steps=[],
        )

        assert result["citations"] == []
        assert result["sources"] == []

    @pytest.mark.asyncio
    async def test_process_hybrid_route_aligns_sources_with_filtered_citations(self):
        vector_results = {
            "documents": ["carbon credit verification methodology integrity"],
            "metadatas": [{"file_name": "data/431_v1.2_methodology.pdf"}],
            "distances": [0.1],
        }
        web_search_result = {
            "answer": "Found web results",
            "sources": [
                {
                    "title": "External Article",
                    "url": "https://example.com/article",
                    "snippet": "news snippet",
                }
            ],
            "timed_out": False,
            "budget_exceeded": False,
        }
        hybrid_synthesis_result = {
            "answer": "The carbon credit verification methodology supports integrity.",
            "sources": [
                {
                    "title": "data/431_v1.2_methodology.pdf",
                    "url": "https://example.com/docs/methodology.pdf",
                    "snippet": "carbon credit verification methodology",
                }
            ],
        }

        processor = RouteProcessor(
            retriever=_DummyRetriever(vector_results),
            answer_generator=_DummyAnswerGenerator({"answer": "", "sources": []}),
            web_search=_DummyWebSearch(search_result=web_search_result, hybrid_result=hybrid_synthesis_result),
            citation_manager=CitationManager(min_relevance_score=0.0),
            config=_build_route_processor_config(enable_web_search=True, parallel_retrieval=False),
        )

        result = await processor.process_hybrid_route(
            query="verification methodology",
            original_query="verification methodology",
            metadata_filters=None,
            steps=[],
        )

        assert len(result["citations"]) >= 1
        # Web citations with URLs now survive filter_by_answer (grounded search
        # sources are inherently answer-referenced), so both appear in sources.
        assert "Methodology" in result["sources"]
        assert "External Article" in result["sources"]


class TestCitationScoreNormalization:
    """Test metric-aware score normalization in citation extraction."""

    def setup_method(self):
        from src.retrieval.score_utils import DistanceMetric
        self.metric = DistanceMetric.COSINE_DISTANCE

    def test_citation_uses_normalized_score_not_naive(self):
        """Citation relevance_score should use normalize_score (1 - d/2) not naive (1 - d)."""
        from src.citations.extractor import CitationExtractor
        from src.citations.config import CitationConfig

        config = CitationConfig(min_relevance_score=0.0)
        extractor = CitationExtractor(
            config=config,
            safe_metadata_fields={"file_name"},
        )

        # distance=0.4 should give score=0.8 with normalization (1 - 0.4/2)
        # not 0.6 with naive (1 - 0.4)
        vector_results = {
            "documents": ["Carbon credit methodology content"],
            "metadatas": [{"file_name": "methodology.pdf"}],
            "distances": [0.4],
        }

        citations = extractor.extract_from_vector_results(vector_results)
        assert len(citations) == 1
        # Normalized score: 1 - 0.4/2 = 0.8
        assert citations[0].relevance_score == 0.8

    def test_citation_score_clamps_low_distance_to_one(self):
        """Distance=0 (identical) should give score=1.0."""
        from src.citations.extractor import CitationExtractor
        from src.citations.config import CitationConfig

        config = CitationConfig(min_relevance_score=0.0)
        extractor = CitationExtractor(config=config, safe_metadata_fields={"file_name"})

        vector_results = {
            "documents": ["Perfect match content"],
            "metadatas": [{"file_name": "perfect.pdf"}],
            "distances": [0.0],
        }

        citations = extractor.extract_from_vector_results(vector_results)
        assert citations[0].relevance_score == 1.0

    def test_citation_score_clamps_high_distance_to_zero(self):
        """Distance=2.0 (opposite for cosine) should give score≈0."""
        from src.citations.extractor import CitationExtractor
        from src.citations.config import CitationConfig

        config = CitationConfig(min_relevance_score=0.0)
        extractor = CitationExtractor(config=config, safe_metadata_fields={"file_name"})

        vector_results = {
            "documents": ["Opposite content"],
            "metadatas": [{"file_name": "opposite.pdf"}],
            "distances": [2.0],
        }

        citations = extractor.extract_from_vector_results(vector_results)
        # Normalized: 1 - 2.0/2 = 0.0
        assert citations[0].relevance_score == 0.0

    def test_citation_format_includes_all_fields(self):
        """Citation should include all expected fields with correct types."""
        from src.citations.extractor import CitationExtractor
        from src.citations.config import CitationConfig

        config = CitationConfig(min_relevance_score=0.0)
        extractor = CitationExtractor(
            config=config,
            safe_metadata_fields={"file_name", "page_number", "document_id"},
        )

        vector_results = {
            "documents": ["VM0007 REDD+ Methodology Framework content"],
            "metadatas": [{
                "file_name": "VM0007.pdf",
                "page_number": 5,
                "document_id": "VM0007",
                "section": "Introduction",
            }],
            "distances": [0.3],  # score = 0.85
        }

        citations = extractor.extract_from_vector_results(vector_results)
        assert len(citations) == 1
        c = citations[0]

        # Check all fields exist and are correct types
        assert isinstance(c.source_id, str)
        assert isinstance(c.source_name, str)
        assert c.source_type == "knowledge_base"
        assert isinstance(c.content_snippet, str)
        assert isinstance(c.relevance_score, float)
        assert c.page_number == 5
        assert c.section == "Introduction"
        assert c.metadata.get("document_id") == "VM0007"

    def test_citation_source_name_fallback_chain(self):
        """Source name should fallback through file_name -> parent_doc -> source -> default."""
        from src.citations.extractor import CitationExtractor
        from src.citations.config import CitationConfig

        config = CitationConfig(min_relevance_score=0.0)
        extractor = CitationExtractor(
            config=config,
            safe_metadata_fields={"file_name", "parent_doc", "source"},
        )

        # Case 1: file_name present
        results1 = {
            "documents": ["Content"],
            "metadatas": [{"file_name": "explicit_name.pdf", "parent_doc": "ignored.pdf"}],
            "distances": [0.5],
        }
        c1 = extractor.extract_from_vector_results(results1)[0]
        assert "Explicit" in c1.source_name  # cleaned at extraction: extension stripped

        # Case 2: only parent_doc
        results2 = {
            "documents": ["Content"],
            "metadatas": [{"parent_doc": "parent_name.pdf"}],
            "distances": [0.5],
        }
        c2 = extractor.extract_from_vector_results(results2)[0]
        assert "Parent" in c2.source_name  # cleaned at extraction: extension stripped

        # Case 3: only source
        results3 = {
            "documents": ["Content"],
            "metadatas": [{"source": "source_name.txt"}],
            "distances": [0.5],
        }
        c3 = extractor.extract_from_vector_results(results3)[0]
        assert "Source" in c3.source_name  # cleaned at extraction: extension stripped

        # Case 4: none present - default naming
        results4 = {
            "documents": ["Content"],
            "metadatas": [{}],
            "distances": [0.5],
        }
        c4 = extractor.extract_from_vector_results(results4)[0]
        assert "Document 1" in c4.source_name
