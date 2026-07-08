"""Unit tests for title extraction and citation verification heuristics.

Tests are organized around structural properties (repetition, position,
identifier patterns) rather than specific domain terms, reflecting the
domain-agnostic design of title_utils.py.
"""

from src.document_store.converter import _ensure_title
from src.document_store.title_utils import (
    _build_display_title,
    _clean_display_name,
    _count_heading_occurrences,
    _extract_content_title,
    _extract_first_heading,
    _is_copyright_line,
    _is_filename_meaningful,
    _is_short_identifier,
    _parse_heading,
)
from src.query_processing.citation_verifier import verify_citations


# ---------------------------------------------------------------------------
# _parse_heading
# ---------------------------------------------------------------------------


class TestParseHeading:
    def test_h1(self):
        assert _parse_heading("# Title") == "Title"

    def test_h2(self):
        assert _parse_heading("## Section") == "Section"

    def test_h3(self):
        assert _parse_heading("### Subsection") == "Subsection"

    def test_bold_as_title(self):
        assert _parse_heading("**Bold Title**") == "Bold Title"

    def test_bold_strips_trailing_asterisks(self):
        """**Bold Title** should extract 'Bold Title' without trailing **."""
        assert _parse_heading("**VM0007 Methodology**") == "VM0007 Methodology"

    def test_plain_text_returns_none(self):
        assert _parse_heading("Just plain text.") is None

    def test_empty_returns_none(self):
        assert _parse_heading("") is None


# ---------------------------------------------------------------------------
# _clean_display_name
# ---------------------------------------------------------------------------


class TestCleanDisplayName:
    def test_strips_path_prefix(self):
        assert _clean_display_name("data/uploads/report.pdf") == "report"

    def test_strips_windows_path(self):
        assert _clean_display_name("C:\\docs\\My Report.pdf") == "My Report"

    def test_strips_extension(self):
        assert _clean_display_name("document.docx") == "document"

    def test_replaces_underscores_and_hyphens(self):
        assert _clean_display_name("A6.4_STAN_METH_001.pdf") == "A6.4 STAN METH 001"

    def test_collapses_multiple_spaces(self):
        assert _clean_display_name("My   Report   2024.pdf") == "My Report 2024"

    def test_empty_input(self):
        assert _clean_display_name("") == ""


# ---------------------------------------------------------------------------
# _is_filename_meaningful
# ---------------------------------------------------------------------------


class TestIsFilenameMeaningful:
    def test_meaningful_filename(self):
        assert _is_filename_meaningful("Verra_VCS_Methodology_v4.1.pdf") is True

    def test_generic_filename_rejected(self):
        assert _is_filename_meaningful("document.pdf") is False

    def test_all_generic_words_rejected(self):
        assert _is_filename_meaningful("Final Report PDF.pdf") is False

    def test_partial_generic_accepted(self):
        """Final Report 2024.pdf has 'final' and 'report' as generic but '2024' is meaningful."""
        assert _is_filename_meaningful("Final Report 2024.pdf") is True

    def test_too_short_rejected(self):
        assert _is_filename_meaningful("ab.pdf") is False

    def test_empty_rejected(self):
        assert _is_filename_meaningful("") is False


# ---------------------------------------------------------------------------
# _is_short_identifier (adaptive, not domain-specific)
# ---------------------------------------------------------------------------


class TestIsShortIdentifier:
    def test_vcm_id_with_hyphens(self):
        assert _is_short_identifier("A6.4-STAN-METH-001") is True

    def test_cdm_id_no_hyphen(self):
        assert _is_short_identifier("ACM0001") is True

    def test_trees_with_space(self):
        assert _is_short_identifier("TREES 2.0") is True

    def test_iso_standard(self):
        assert _is_short_identifier("ISO 14064-2") is True

    def test_generic_word_rejected(self):
        assert _is_short_identifier("Standard") is False

    def test_no_digit_rejected(self):
        assert _is_short_identifier("Methodology") is False

    def test_too_long_rejected(self):
        assert _is_short_identifier("This is a very long heading that exceeds the 40 char limit 1234567890") is False

    def test_plain_text_rejected(self):
        assert _is_short_identifier("Carbon Market Overview") is False

    def test_four_word_title_with_year_not_identifier(self):
        """A 4-word title containing a year should NOT be classified as an identifier."""
        assert _is_short_identifier("Carbon Market Trends 2024") is False


# ---------------------------------------------------------------------------
# _is_copyright_line
# ---------------------------------------------------------------------------


class TestIsCopyrightLine:
    def test_copyright_symbol(self):
        assert _is_copyright_line("© 2024 UNFCCC. All rights reserved.") is True

    def test_copyright_word(self):
        assert _is_copyright_line("Copyright 2024 by Verra") is True

    def test_all_rights_reserved(self):
        assert _is_copyright_line("All rights reserved. No part of this publication...") is True

    def test_normal_text(self):
        assert _is_copyright_line("This methodology applies to renewable energy projects.") is False

    def test_disclaimer(self):
        assert _is_copyright_line("Disclaimer: The information provided...") is True


# ---------------------------------------------------------------------------
# _extract_first_heading
# ---------------------------------------------------------------------------


class TestExtractFirstHeading:
    def test_simple_heading(self):
        assert _extract_first_heading("# My Title\n\nContent") == "My Title"

    def test_no_heading(self):
        assert _extract_first_heading("Just plain text.") is None

    def test_heading_not_on_first_line(self):
        assert _extract_first_heading("\n\n## Some content\n\n# Real Title") == "Real Title"

    def test_subheading_skipped(self):
        assert _extract_first_heading("## Subheading\n\n# Top Title") == "Top Title"


# ---------------------------------------------------------------------------
# _count_heading_occurrences
# ---------------------------------------------------------------------------


class TestCountHeadingOccurrences:
    def test_single_occurrence(self):
        lines = ["# Title", "", "## Section", "", "Content"]
        counts = _count_heading_occurrences(lines)
        assert counts["title"] == 1
        assert counts["section"] == 1

    def test_repeated_heading(self):
        """A section heading that appears multiple times."""
        lines = [
            "# Monitoring", "",
            "## Monitoring", "Content", "",
            "## Monitoring", "More content", "",
            "## Monitoring", "Even more",
        ]
        counts = _count_heading_occurrences(lines)
        assert counts["monitoring"] == 4

    def test_ignores_code_blocks(self):
        lines = ["# Title", "", "```python", "# Not a heading", "```", "", "## Section"]
        counts = _count_heading_occurrences(lines)
        assert counts["not a heading"] == 0
        assert counts["title"] == 1
        assert counts["section"] == 1

    def test_case_insensitive(self):
        lines = ["# Monitoring", "", "## monitoring", "", "### MONITORING"]
        counts = _count_heading_occurrences(lines)
        assert counts["monitoring"] == 3

    def test_empty_document(self):
        counts = _count_heading_occurrences([])
        assert len(counts) == 0


# ---------------------------------------------------------------------------
# _extract_content_title — universal front-matter filter
# ---------------------------------------------------------------------------


class TestUniversalFrontMatterSkipped:
    """Universal front-matter words (abstract, introduction, etc.) are always
    skipped regardless of repetition, because they appear in ALL document types."""

    def test_abstract_skipped(self):
        markdown = "# Abstract\n\n## VM0007\n\nReducing Emissions from Deforestation."
        title = _extract_content_title(markdown)
        assert title is not None
        assert title != "Abstract"

    def test_introduction_skipped(self):
        markdown = "# Introduction\n\n## VM0007\n\nReducing Emissions from Deforestation."
        title = _extract_content_title(markdown)
        assert title is not None
        assert title != "Introduction"

    def test_summary_skipped(self):
        markdown = "# Summary\n\n## VM0007\n\nReducing Emissions from Deforestation."
        title = _extract_content_title(markdown)
        assert title is not None
        assert title != "Summary"

    def test_overview_skipped(self):
        markdown = "# Overview\n\n## VM0007\n\nReducing Emissions from Deforestation."
        title = _extract_content_title(markdown)
        assert title is not None
        assert title != "Overview"

    def test_methodology_skipped(self):
        markdown = "# Methodology\n\n## VM0007\n\nReducing Emissions from Deforestation."
        title = _extract_content_title(markdown)
        assert title is not None
        assert title != "Methodology"

    def test_references_skipped(self):
        markdown = "# References\n\n## VM0007\n\nReducing Emissions from Deforestation."
        title = _extract_content_title(markdown)
        assert title is not None
        assert title != "References"


# ---------------------------------------------------------------------------
# _extract_content_title — repetition detection (core domain-agnostic signal)
# ---------------------------------------------------------------------------


class TestRepetitionDetection:
    """A heading that appears multiple times is a section label, not the title.
    A heading that appears only once is likely the title."""

    def test_repeated_section_heading_skipped(self):
        """'Monitoring' appears as H1 once and H2 three times → section, not title.
        The unique heading 'VM0007 REDD+ Methodology' is preferred."""
        markdown = (
            "# Monitoring\n\n"
            "## VM0007 REDD+ Methodology\n\n"
            "Reducing emissions from deforestation.\n\n"
            "## Monitoring\n\nContent about monitoring.\n\n"
            "## Monitoring\n\nMore monitoring details.\n\n"
            "## Monitoring\n\nFinal monitoring section."
        )
        title = _extract_content_title(markdown)
        assert title is not None
        assert "monitoring" not in title.lower()
        assert "VM0007" in title or "REDD+" in title

    def test_domain_term_skipped_via_repetition(self):
        """'Additionality' appears 3 times → section, not title.
        The unique heading is preferred. This replaces hardcoded domain terms."""
        markdown = (
            "# Additionality\n\n"
            "## VM0007: REDD+ Methodology Framework\n\n"
            "Content about the methodology.\n\n"
            "## Additionality\n\nAdditionality requirements.\n\n"
            "## Additionality\n\nAdditionality assessment."
        )
        title = _extract_content_title(markdown)
        assert title is not None
        assert title != "Additionality"
        assert "VM0007" in title or "REDD+" in title

    def test_unique_heading_preferred_over_repeated(self):
        """When multiple headings exist, the one that appears only once wins."""
        markdown = (
            "# Baseline\n\n"
            "## VM0048: Improved Forest Management\n\n"
            "Content.\n\n"
            "## Baseline\n\nBaseline scenario.\n\n"
            "## Baseline\n\nBaseline methodology."
        )
        title = _extract_content_title(markdown)
        assert title is not None
        assert "baseline" not in title.lower()
        assert "VM0048" in title or "Improved Forest" in title

    def test_all_headings_repeat_falls_back_to_first(self):
        """If ALL headings repeat (e.g. title in running headers), fall back
        to the first heading rather than returning None."""
        markdown = (
            "# Carbon Market Report 2024\n\n"
            "Content.\n\n"
            "# Carbon Market Report 2024\n\n"
            "More content."
        )
        title = _extract_content_title(markdown)
        assert title is not None
        # Falls back to the first heading since all repeat
        assert "Carbon Market Report 2024" in title

    def test_single_heading_returned(self):
        """A heading that appears only once and is the only heading is returned."""
        markdown = "# Carbon Market Trends 2024\n\nExecutive summary of the report."
        title = _extract_content_title(markdown)
        assert title == "Carbon Market Trends 2024"

    def test_no_headings_returns_none(self):
        assert _extract_content_title("Just plain text with no headings.") is None


# ---------------------------------------------------------------------------
# _extract_content_title — short identifier combination
# ---------------------------------------------------------------------------


class TestShortIdentifierCombination:
    def test_identifier_combined_with_next_heading(self):
        markdown = "# A6.4-STAN-METH-001\n\n## Standard\n\n## Application of the Requirements of Chapter V.B\n\nContent here."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "A6.4-STAN-METH-001" in title
        assert "Application" in title

    def test_cdm_identifier_combined(self):
        markdown = "# ACM0001\n\n## Consolidated Methodology for Renewable Energy\n\nThis consolidated methodology applies."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "ACM0001" in title

    def test_verra_identifier_combined(self):
        markdown = "# VM0007\n\n## REDD+ Methodology Module\n\nReducing Emissions from Deforestation in Developing Countries."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "VM0007" in title
        assert "REDD+" in title

    def test_gold_standard_identifier_combined(self):
        markdown = "# 115G\n\n## Methodology for Switchgrass to Biogas\n\nThis methodology applies to biogas projects."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "115G" in title

    def test_art_trees_identifier_with_version(self):
        markdown = "# TREES 2.0\n\n## The REDD+ Environmental Excellence Standard\n\nThe standard defines requirements."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "TREES 2.0" in title

    def test_puro_earth_identifier(self):
        markdown = "# PUR-001\n\n## Enhanced Weathering Methodology\n\nThis methodology quantifies carbon removal."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "PUR-001" in title

    def test_icvcm_identifier(self):
        markdown = "# CCP-001\n\n## Core Carbon Principles Assessment Procedure\n\nThe assessment procedure evaluates."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "CCP-001" in title


# ---------------------------------------------------------------------------
# _extract_content_title — doc_id matching
# ---------------------------------------------------------------------------


class TestDocIdMatching:
    def test_doc_id_locates_heading(self):
        markdown = "# Cover Page\n\n## Some preamble\n\n## A6.4-STAN-METH-001\n\nApplication of the requirements of Chapter V.B for the development of methodologies."
        title = _extract_content_title(markdown, doc_id="A6.4-STAN-METH-001")
        assert title is not None
        assert "A6.4-STAN-METH-001" in title
        assert "Application" in title

    def test_doc_id_with_spaces_matches_heading_without_spaces(self):
        """doc_id 'VM0007' should match heading 'VM 0007'."""
        markdown = "# Cover\n\n## VM 0007\n\nReducing Emissions from Deforestation in Developing Countries."
        title = _extract_content_title(markdown, doc_id="VM0007")
        assert title is not None
        assert "VM 0007" in title
        assert "Reducing Emissions" in title

    def test_doc_id_with_hyphens_matches_heading_with_spaces(self):
        """doc_id 'A6.4-STAN-METH-001' should match heading 'A6.4 STAN METH 001'."""
        markdown = "# Cover\n\n## A6.4 STAN METH 001\n\nApplication of the requirements for methodologies."
        title = _extract_content_title(markdown, doc_id="A6.4-STAN-METH-001")
        assert title is not None
        assert "A6.4 STAN METH 001" in title

    def test_doc_id_skips_repeated_heading_as_subtitle(self):
        """Bug A2: doc_id path must use repetition detection — a heading that
        repeats multiple times is a section label, not a subtitle."""
        markdown = (
            "# Cover\n\n"
            "## A6.4-SBM014-A06\n\n"
            "## Additionality Requirements\n\n"
            "## Additionality Requirements\n\n"
            "## Additionality Requirements\n\n"
            "Real content here."
        )
        title = _extract_content_title(markdown, doc_id="A6.4-SBM014-A06")
        assert title is not None
        assert "Additionality Requirements" not in title


# ---------------------------------------------------------------------------
# _extract_content_title — short identifier edge cases (Bug B)
# ---------------------------------------------------------------------------


class TestShortIdentifierEdgeCases:
    def test_two_identifiers_not_combined(self):
        """Bug B: two different coded identifiers should not be combined as
        title:subtitle. The second ID is a reference to another document."""
        markdown = "# VM0007\n\n## VM0008\n\n## VM0009\n\nContent here."
        title = _extract_content_title(markdown)
        assert title == "VM0007"

    def test_identifier_plus_real_title_still_combined(self):
        """Ensure the fix doesn't break the normal case: identifier + real
        multi-word title."""
        markdown = "# VM0007\n\n## REDD+ Methodology Framework\n\nContent."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "VM0007" in title
        assert "REDD+" in title

    def test_identifier_with_no_subtitle_returns_id(self):
        """If the only headings are short identifiers (all with digits), return
        the first one without combining."""
        markdown = "# ACM0001\n\n## ACM0002\n\n## ACM0003\n\nContent."
        title = _extract_content_title(markdown)
        assert title == "ACM0001"


class TestCopyrightSkipping:
    def test_copyright_line_skipped_as_substantial_paragraph(self):
        markdown = "# A6.4-SBM014-A06\n\n© 2024 UNFCCC. All rights reserved.\n\nRequirements for activities involving removals."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "©" not in title
        assert "rights reserved" not in title


# ---------------------------------------------------------------------------
# _extract_content_title — wide scan window
# ---------------------------------------------------------------------------


class TestWideScanWindow:
    def test_title_found_after_boilerplate(self):
        """Title appears after 100+ lines of cover page / TOC boilerplate."""
        boilerplate = "\n".join(f"## Page {i}\n\nBoilerplate text line {i}." for i in range(1, 60))
        markdown = f"{boilerplate}\n\n# ACM0001\n\n## Real Methodology Title About Renewable Energy\n\nContent."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "ACM0001" in title


# ---------------------------------------------------------------------------
# _extract_content_title — real titles are NOT skipped
# ---------------------------------------------------------------------------


class TestRealTitlesNotSkipped:
    """Multi-word titles containing domain terms should NOT be skipped —
    only bare topic labels (detected via repetition) are skipped."""

    def test_carbon_market_trends_2024_not_skipped(self):
        markdown = "# Carbon Market Trends 2024\n\nExecutive summary of the annual report."
        title = _extract_content_title(markdown)
        assert title == "Carbon Market Trends 2024"

    def test_eu_ets_directive_not_skipped(self):
        markdown = "# EU ETS Directive 2023/959\n\nMonitoring and reporting of greenhouse gas emissions."
        title = _extract_content_title(markdown)
        assert title == "EU ETS Directive 2023/959"

    def test_biochar_methodology_not_skipped(self):
        markdown = "# Biochar Carbon Removal Methodology\n\nThis methodology quantifies biochar carbon removal."
        title = _extract_content_title(markdown)
        assert title == "Biochar Carbon Removal Methodology"

    def test_blue_carbon_framework_not_skipped(self):
        markdown = "# Blue Carbon Restoration Framework\n\nThe framework for blue carbon restoration projects."
        title = _extract_content_title(markdown)
        assert title == "Blue Carbon Restoration Framework"

    def test_non_vcm_document(self):
        """The heuristics should work for non-VCM documents too."""
        markdown = "# ISO 14064-2\n\n## Quantification and Reporting of GHG Emissions\n\nThis standard specifies requirements."
        title = _extract_content_title(markdown)
        assert title is not None
        assert "ISO 14064-2" in title


# ---------------------------------------------------------------------------
# _build_display_title
# ---------------------------------------------------------------------------


class TestBuildDisplayTitle:
    def test_full_metadata(self):
        metadata = {
            "publisher": "Verra",
            "document_id": "VCS-001",
            "version_number": "4.1",
        }
        title = _build_display_title(metadata, "Reducing Emissions from Deforestation", "document.pdf")
        assert "Verra" in title
        assert "VCS-001" in title
        assert "Reducing Emissions" in title
        assert "v4.1" in title

    def test_no_publisher_omits_prefix(self):
        """When publisher is None, no prefix is added (category is a topic classifier)."""
        metadata = {"category": "VCM Policy", "document_id": "A6.4-STAN-METH-001"}
        title = _build_display_title(metadata, "Application of Requirements", "doc.pdf")
        assert "VCM Policy" not in title
        assert "A6.4-STAN-METH-001" in title

    def test_doc_id_already_in_content_title(self):
        """If the content title already contains the doc ID, don't duplicate it."""
        metadata = {"document_id": "ACM0001"}
        title = _build_display_title(metadata, "ACM0001: Renewable Energy Methodology", "file.pdf")
        assert title.count("ACM0001") == 1

    def test_filename_fallback_when_no_content_title(self):
        metadata = {}
        title = _build_display_title(metadata, None, "Verra_VCS_Methodology.pdf")
        assert "Verra VCS Methodology" in title

    def test_generic_filename_with_doc_id(self):
        metadata = {"document_id": "A6.4-SBM014-A06"}
        title = _build_display_title(metadata, None, "document.pdf")
        assert "A6.4-SBM014-A06" in title

    def test_truncation_at_200_chars(self):
        metadata = {"document_id": "X" * 300}
        title = _build_display_title(metadata, None, "file.pdf")
        assert len(title) <= 200

    def test_version_not_duplicated(self):
        metadata = {"document_id": "VCS-001", "version_number": "4.1"}
        title = _build_display_title(metadata, "VCS-001 v4.1 Methodology", "file.pdf")
        assert title.count("v4.1") == 1


# ---------------------------------------------------------------------------
# citation_verifier: verify_citations
# ---------------------------------------------------------------------------


class TestVerifyCitations:
    def test_exact_match_kept(self):
        sources = ["Verra VCS Methodology v4.1"]
        answer = "The methodology applies to forest projects [Verra VCS Methodology v4.1]."
        result, unmatched = verify_citations(answer, sources)
        assert "[Verra VCS Methodology v4.1]" in result
        assert unmatched == []

    def test_hallucinated_citation_removed(self):
        sources = ["Verra VCS Methodology v4.1"]
        answer = "The methodology applies [Some Random Source That Does Not Exist]."
        result, unmatched = verify_citations(answer, sources)
        assert "[Some Random Source" not in result
        assert len(unmatched) == 1

    def test_fuzzy_match_repaired(self):
        sources = ["Verra VCS Methodology v4.1"]
        answer = "The methodology applies [Verra VCS Methodology]."
        result, unmatched = verify_citations(answer, sources)
        assert "Verra VCS Methodology" in result
        assert unmatched == []

    def test_multiple_citations(self):
        sources = ["Verra VCS Methodology v4.1", "Gold Standard Toolkit v2.0"]
        answer = (
            "Projects must follow the rules [Verra VCS Methodology v4.1]. "
            "Additional guidance is available [Gold Standard Toolkit v2.0]."
        )
        result, unmatched = verify_citations(answer, sources)
        assert "[Verra VCS Methodology v4.1]" in result
        assert "[Gold Standard Toolkit v2.0]" in result
        assert unmatched == []

    def test_numeric_reference_not_treated_as_citation(self):
        sources = ["Some Source"]
        answer = "See reference [1] for details."
        result, unmatched = verify_citations(answer, sources)
        assert "[1]" in result
        assert unmatched == []

    def test_empty_sources_returns_unchanged(self):
        answer = "Some text [citation]."
        result, unmatched = verify_citations(answer, [])
        assert result == answer

    def test_empty_answer(self):
        result, unmatched = verify_citations("", ["source"])
        assert result == ""
        assert unmatched == []

    def test_no_citations_in_answer(self):
        sources = ["Verra VCS Methodology v4.1"]
        answer = "This is a plain answer with no citations at all."
        result, unmatched = verify_citations(answer, sources)
        assert result == answer
        assert unmatched == []

    def test_mixed_valid_and_invalid(self):
        sources = ["Verra VCS Methodology v4.1"]
        answer = (
            "Rules apply [Verra VCS Methodology v4.1]. "
            "Also see [Hallucinated Source XYZ]."
        )
        result, unmatched = verify_citations(answer, sources)
        assert "[Verra VCS Methodology v4.1]" in result
        assert "[Hallucinated Source XYZ]" not in result
        assert len(unmatched) == 1

    def test_repaired_citation_preserves_sentence_structure(self):
        sources = ["UNFCC Application of the Requirements v1.0"]
        answer = "The requirements are strict [UNFCC Application of the Requirements]."
        result, unmatched = verify_citations(answer, sources)
        assert unmatched == []
        assert "UNFCC Application of the Requirements" in result

    # --- Containment check for abbreviated citations ---

    def test_abbreviated_citation_repaired_via_containment(self):
        """[Verra] should match 'Verra VCS Methodology v4.1' via containment."""
        sources = ["Verra VCS Methodology v4.1"]
        answer = "Projects must follow the rules [Verra]."
        result, unmatched = verify_citations(answer, sources)
        assert unmatched == []
        assert "[Verra VCS Methodology v4.1]" in result

    def test_partial_name_citation_repaired_via_containment(self):
        """[VCS Methodology] should match 'Verra VCS Methodology v4.1'."""
        sources = ["Verra VCS Methodology v4.1"]
        answer = "The standard applies [VCS Methodology]."
        result, unmatched = verify_citations(answer, sources)
        assert unmatched == []
        assert "Verra VCS Methodology" in result

    def test_publisher_abbreviation_not_removed(self):
        """[Gold Standard] should match 'Gold Standard Toolkit v2.0'."""
        sources = ["Gold Standard Toolkit v2.0"]
        answer = "The toolkit covers project types [Gold Standard]."
        result, unmatched = verify_citations(answer, sources)
        assert unmatched == []
        assert "Gold Standard Toolkit" in result

    def test_containment_does_not_false_positive_on_short_strings(self):
        """Very short citations like [v1] should not match via containment."""
        sources = ["Verra VCS Methodology v4.1"]
        answer = "See version [v1] for details."
        result, unmatched = verify_citations(answer, sources)
        assert "[v1]" in result  # kept as-is (too short for containment)

    def test_reverse_containment_not_degraded_to_short_source(self):
        """Bug D: a detailed citation should not be repaired to a very short
        source name via reverse containment. The citation 'Verra VCS Methodology
        v4.1' should NOT become '[Verra]' when the source is just 'Verra'."""
        sources = ["Verra"]
        answer = "The rules apply [Verra VCS Methodology v4.1]."
        result, unmatched = verify_citations(answer, sources)
        # The citation should not be degraded to the short source name.
        assert "[Verra]" not in result

    def test_reverse_containment_works_with_long_source(self):
        """Bug D: reverse containment should still work when the source is long
        enough — citation with extra text gets repaired to the real source."""
        sources = ["Verra VCS Methodology v4.1"]
        answer = "The rules apply [Verra VCS Methodology v4.1 Additional Rules]."
        result, unmatched = verify_citations(answer, sources)
        assert "[Verra VCS Methodology v4.1]" in result


# ---------------------------------------------------------------------------
# _ensure_title integration
# ---------------------------------------------------------------------------


class TestEnsureTitle:
    """Verify _ensure_title in converter.py handles Markdown files specially."""

    def test_md_with_h1_preserves_single_heading(self):
        """Issue 3: uploaded Markdown files with an H1 keep that H1; do not
        prepend a second H1."""
        markdown = "# User Written Title\n\nSome content."
        metadata = {"document_id": "VM0007", "publisher": "Verra"}
        result = _ensure_title(markdown, "test.md", metadata, extension=".md")
        assert "User Written Title" in result
        assert result.count("User Written Title") == 1
        assert result.count("# ") == 1
        assert metadata["title"] == "Verra - VM0007: User Written Title"

    def test_md_without_h1_gets_title_prepended(self):
        """Issue 3: Markdown files without an H1 get the extracted title prepended."""
        markdown = "Some content without heading."
        metadata = {"document_id": "VM0007", "publisher": "Verra"}
        result = _ensure_title(markdown, "test.md", metadata, extension=".md")
        assert result.startswith("# Verra")

    def test_non_md_replaces_placeholder_h1(self):
        """Issue 3: non-Markdown files have converter-injected placeholder H1s
        replaced with the extracted title."""
        markdown = "# test\n\nSome content."
        metadata = {"document_id": "VM0007", "publisher": "Verra"}
        result = _ensure_title(markdown, "test.pdf", metadata, extension=".pdf")
        assert "# test" not in result
        assert result.startswith("# Verra")
