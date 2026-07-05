"""Tests for citation marker renumbering after filtering.

When ``filter_citations_by_answer`` removes citations that aren't grounded in
the answer, the inline ``[cite_kb: N]`` / ``[Web, cite: N]`` markers in the
answer text still reference the *original* source indices. The
``renumber_citation_markers`` function rewrites them so ``N`` refers to the
position in the filtered list — which is what the frontend displays.
"""


from src.citations.citation_manager import Citation
from src.query_processing.citation_verifier import renumber_citation_markers


def _kb(name: str, score: float = 0.9) -> Citation:
    return Citation(
        source_id=f"doc_{name}",
        source_name=name,
        source_type="knowledge_base",
        content_snippet="",
        relevance_score=score,
    )


def _web(name: str, url: str, score: float = 0.8) -> Citation:
    return Citation(
        source_id=f"web_{name}",
        source_name=name,
        source_type="web",
        content_snippet="",
        relevance_score=score,
        url=url,
    )


class TestRenumberCitationMarkers:
    """Verify renumbering logic for KB, Web, and mixed citations."""

    def test_no_change_when_nothing_filtered(self):
        """All citations retained → markers unchanged."""
        original = [_kb("Doc A"), _kb("Doc B")]
        filtered = list(original)
        answer = "Claim [cite_kb: 1] and claim [cite_kb: 2]."

        result = renumber_citation_markers(answer, original, filtered)

        assert result == answer

    def test_renumbers_kb_after_middle_removal(self):
        """Removing the 2nd of 3 KB sources shifts index 3 → 2."""
        original = [_kb("Doc A"), _kb("Doc B"), _kb("Doc C")]
        filtered = [_kb("Doc A"), _kb("Doc C")]
        answer = "A [cite_kb: 1] B [cite_kb: 2] C [cite_kb: 3]."

        result = renumber_citation_markers(answer, original, filtered)

        # Doc A stays 1, Doc B (index 2) removed, Doc C (index 3) → 2
        assert "[cite_kb: 1]" in result
        assert "[cite_kb: 2]" in result  # was [cite_kb: 3]
        assert "[cite_kb: 3]" not in result
        # The old [cite_kb: 2] (Doc B, filtered out) should be removed
        assert "B  C" in result or "B C" in result

    def test_renumbers_web_after_removal(self):
        """Web citations are renumbered independently."""
        original = [_web("Site A", "https://a.com"), _web("Site B", "https://b.com")]
        filtered = [_web("Site B", "https://b.com")]
        answer = "From [Web, cite: 1] and [Web, cite: 2]."

        result = renumber_citation_markers(answer, original, filtered)

        # Site A (index 1) removed, Site B (index 2) → 1
        assert "[Web, cite: 1]" in result
        assert "[Web, cite: 2]" not in result

    def test_removes_markers_for_filtered_out_sources(self):
        """Markers referencing removed sources are stripped entirely."""
        original = [_kb("Doc A"), _kb("Doc B")]
        filtered = [_kb("Doc A")]
        answer = "Keep [cite_kb: 1] drop [cite_kb: 2]."

        result = renumber_citation_markers(answer, original, filtered)

        assert "[cite_kb: 1]" in result
        assert "[cite_kb: 2]" not in result

    def test_handles_multi_number_markers(self):
        """[cite_kb: 1, 3] with Doc B removed → [cite_kb: 1, 2]."""
        original = [_kb("Doc A"), _kb("Doc B"), _kb("Doc C")]
        filtered = [_kb("Doc A"), _kb("Doc C")]
        answer = "Both [cite_kb: 1, 3]."

        result = renumber_citation_markers(answer, original, filtered)

        assert "[cite_kb: 1, 2]" in result

    def test_knowledge_base_long_form_renumbered(self):
        """[Knowledge Base, cite: N] format is also renumbered."""
        original = [_kb("Doc A"), _kb("Doc B")]
        filtered = [_kb("Doc B")]
        answer = "Ref [Knowledge Base, cite: 2]."

        result = renumber_citation_markers(answer, original, filtered)

        assert "[Knowledge Base, cite: 1]" in result

    def test_mixed_kb_and_web_renumbered_independently(self):
        """KB and Web numbering are independent."""
        original = [_kb("Doc A"), _web("Site A", "https://a.com")]
        filtered = [_web("Site A", "https://a.com")]
        answer = "KB [cite_kb: 1] and Web [Web, cite: 1]."

        result = renumber_citation_markers(answer, original, filtered)

        # KB citation filtered out → [cite_kb: 1] removed
        assert "[cite_kb: 1]" not in result
        # Web citation retained → [Web, cite: 1] stays
        assert "[Web, cite: 1]" in result

    def test_empty_answer_returns_empty(self):
        assert renumber_citation_markers("", [_kb("A")], [_kb("A")]) == ""

    def test_no_markers_unchanged(self):
        """Answer without citation markers is returned as-is."""
        answer = "Just plain text with no citations."
        result = renumber_citation_markers(answer, [_kb("A")], [_kb("A")])
        assert result == answer

    def test_all_filtered_out_removes_all_markers(self):
        """When all citations are filtered, all markers are removed."""
        original = [_kb("Doc A"), _kb("Doc B")]
        filtered: list = []
        answer = "A [cite_kb: 1] B [cite_kb: 2]."

        result = renumber_citation_markers(answer, original, filtered)

        assert "[cite_kb:" not in result
        assert "[Knowledge Base" not in result

    def test_duplicate_source_names_deduplicated(self):
        """Multiple chunks from same source share one index."""
        original = [_kb("Doc A"), _kb("Doc A"), _kb("Doc B")]
        filtered = [_kb("Doc A"), _kb("Doc B")]
        answer = "A [cite_kb: 1] B [cite_kb: 2]."

        result = renumber_citation_markers(answer, original, filtered)

        # Doc A is index 1 in both, Doc B is index 2 in both
        assert "[cite_kb: 1]" in result
        assert "[cite_kb: 2]" in result

    def test_cleans_up_spacing_after_removal(self):
        """Removed markers don't leave double spaces or dangling punctuation."""
        original = [_kb("Doc A"), _kb("Doc B")]
        filtered = [_kb("Doc A")]
        answer = "Text [cite_kb: 2] , more."

        result = renumber_citation_markers(answer, original, filtered)

        # The marker is removed, spacing is cleaned up
        assert "  " not in result
        assert " ," not in result
