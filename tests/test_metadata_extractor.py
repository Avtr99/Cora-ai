"""
Tests for the flexible metadata extraction system.

Verifies that metadata is correctly extracted from documents
of various carbon registries.
"""
import pytest
from src.document_loader.metadata_extractor import (
    MetadataExtractor,
    RegistryPattern,
    get_metadata_extractor,
)


class TestMetadataExtractor:
    """Test cases for MetadataExtractor."""
    
    @pytest.fixture
    def extractor(self):
        """Create a fresh MetadataExtractor instance."""
        return MetadataExtractor()
    
    # Verra tests
    def test_extract_verra_vm_methodology(self, extractor):
        """Test extraction of Verra VM methodology ID."""
        content = """
        ## VM0007
        ### REDD+ Methodology Framework
        **Version:** 1.8
        """
        result = extractor.extract(content, "VM0007.md")
        
        assert result.get("registry") == "Verra"
        assert result.get("document_id") == "VM0007"
        assert result.get("version_number") == "1.8"
    
    def test_extract_verra_vmr_methodology(self, extractor):
        """Test extraction of Verra VMR methodology ID."""
        content = """
        # VMR0004
        Methodology for Conservation Projects
        Version: 2.0
        """
        result = extractor.extract(content, "VMR0004.md")
        
        assert result.get("registry") == "Verra"
        assert result.get("document_id") == "VMR0004"
        assert result.get("version_number") == "2.0"
    
    def test_extract_verra_vmd_methodology(self, extractor):
        """Test extraction of Verra VMD methodology ID."""
        content = """
        VMD0001 - Module for Baseline Emissions
        VCS Program
        Version 1.0
        """
        result = extractor.extract(content, "VMD0001.md")
        
        assert result.get("registry") == "Verra"
        assert result.get("document_id") == "VMD0001"
    
    # Gold Standard tests
    def test_extract_gold_standard_document(self, extractor):
        """Test extraction of Gold Standard document."""
        content = """
        # GUIDELINE
        ## ELIGIBILITY OF GOLD STANDARD VERS FOR USE UNDER CORSIA
        **VERSION** – 1.0
        The Gold Standard Foundation
        """
        result = extractor.extract(content, "115G_v.1.0_Eligibility.md")
        
        assert result.get("registry") == "Gold Standard"
        assert result.get("document_id") == "115G"
        assert result.get("version_number") == "1.0"
    
    # Article 6.4 tests — now correctly classified as VCM Policy, not a registry
    def test_extract_article_64_document(self, extractor):
        """Test extraction of Article 6.4 document under VCM Policy taxonomy."""
        content = """
        # Standard
        ## Requirements for activities involving removals under the Article 6.4 mechanism
        Version 01.0
        United Nations Framework Convention on Climate Change
        """
        result = extractor.extract(content, "A6.4-SBM014-A06.pdf.md")

        # Article 6.4 is a policy framework, detected via VCM Policy pattern.
        # VCM Policy is a topic classifier, not a registry → stored as "category"
        assert result.get("category") == "VCM Policy"
        assert "registry" not in result or result.get("registry") is None
        assert result.get("document_id") == "A6.4-SBM014-A06"

    def test_extract_article_64_stan_meth(self, extractor):
        """Test extraction of Article 6.4 STAN-METH document under VCM Policy taxonomy."""
        content = """
        Article 6.4 Mechanism
        STAN-METH-001
        Paris Agreement crediting mechanism
        """
        result = extractor.extract(content, "A6.4-STAN-METH-001.pdf.md")

        # Article 6.4 is a policy framework → stored as "category", not "registry"
        assert result.get("category") == "VCM Policy"
        assert "registry" not in result or result.get("registry") is None
    
    # CDM tests
    def test_extract_cdm_acm_methodology(self, extractor):
        """Test extraction of CDM ACM methodology."""
        content = """
        ACM0001 - Consolidated methodology
        Clean Development Mechanism
        Version 18.0
        """
        result = extractor.extract(content, "ACM0001.md")
        
        assert result.get("registry") == "CDM"
        assert result.get("document_id") == "ACM0001"
    
    def test_extract_cdm_ams_methodology(self, extractor):
        """Test extraction of CDM AMS methodology."""
        content = """
        AMS-III.D - Small-scale methodology
        CDM Executive Board
        """
        result = extractor.extract(content, "AMS-III.D.md")
        
        assert result.get("registry") == "CDM"
    
    # ICVCM tests
    def test_extract_icvcm_document(self, extractor):
        """Test extraction of ICVCM document."""
        content = """
        Core Carbon Principles
        ICVCM Assessment Framework
        Integrity Council for the Voluntary Carbon Market
        """
        result = extractor.extract(content, "CCP-Assessment.md")

        # ICVCM is a governance body, not a credit-issuing registry → "category"
        assert result.get("category") == "ICVCM"
        assert "registry" not in result or result.get("registry") is None
    
    # Version extraction tests
    def test_extract_version_various_formats(self, extractor):
        """Test version extraction from various formats."""
        test_cases = [
            ("Version: 1.8", "1.8"),
            ("Version 2.0", "2.0"),
            ("v.1.0", "1.0"),
            ("V3.5", "3.5"),
            ("version 01.0", "01.0"),
        ]
        
        for content, expected_version in test_cases:
            result = extractor.extract(content, "test.md")
            assert result.get("version_number") == expected_version, f"Failed for: {content}"
    
    # Custom pattern tests
    def test_custom_registry_pattern(self):
        """Test adding custom registry patterns."""
        custom_pattern = RegistryPattern(
            name="Custom Registry",
            content_markers=["custom registry", "cr-"],
            id_patterns=[r'\b(CR\d{4})\b'],
            version_patterns=[r'[Vv]ersion[:\s]+(\d+\.?\d*)']
        )
        
        extractor = MetadataExtractor(custom_patterns=[custom_pattern])
        
        content = """
        CR0001 - Custom Methodology
        Custom Registry Standard
        Version 1.0
        """
        result = extractor.extract(content, "CR0001.md")
        
        assert result.get("registry") == "Custom Registry"
        assert result.get("document_id") == "CR0001"
        assert result.get("version_number") == "1.0"
    
    # Edge cases
    def test_no_metadata_found(self, extractor):
        """Test handling of document with no extractable metadata."""
        content = "This is a generic document with no specific metadata."
        result = extractor.extract(content, "generic.md")
        
        # Title extraction is handled by title_utils._ensure_title(); the
        # metadata extractor only returns registry, category, publisher,
        # document_id, and version fields.
        assert "registry" not in result or result.get("registry") is None
        assert "category" not in result or result.get("category") is None
        assert "document_id" not in result or result.get("document_id") is None
    
    def test_multiple_registries_mentioned(self, extractor):
        """Test that highest-scoring registry is selected."""
        content = """
        VM0007 REDD+ Methodology
        Verra VCS Program
        Verified Carbon Standard
        VCU issuance
        """
        result = extractor.extract(content, "VM0007.md")
        
        # Verra should win due to multiple markers
        assert result.get("registry") == "Verra"
        assert result.get("document_id") == "VM0007"

    # Publisher extraction (filename "Publisher - Title vX.Y.ext" convention)
    def test_publisher_from_filename_registry(self, extractor):
        """Filename prefix maps to canonical registry publisher."""
        result = extractor.extract(
            "VCS Methodology content",
            "Verra - VCS Methodology VM0007 for REDD+ Methodology Framework v1.8.md",
        )
        assert result.get("publisher") == "Verra"
        assert result.get("registry") == "Verra"
        assert result.get("document_id") == "VM0007"
        assert result.get("version_number") == "1.8"

    def test_publisher_from_filename_research_org(self, extractor):
        """Research/market orgs are captured as publishers via filename prefix."""
        result = extractor.extract(
            "State of the market analysis.",
            "AlliedOffsets - CDR - State of the Market July 2025.md",
        )
        assert result.get("publisher") == "AlliedOffsets"

    def test_publisher_alias_normalization(self, extractor):
        """Alias variants normalize to the canonical publisher name."""
        result = extractor.extract(
            "Carbon removal analysis.",
            "Allied Offsets - Some Market Report.md",
        )
        assert result.get("publisher") == "AlliedOffsets"

    def test_publisher_unknown_prefix_preserved(self, extractor):
        """Unrecognized but real publisher prefixes are preserved verbatim."""
        result = extractor.extract(
            "Article 6.2 initial report.",
            "Cooperative Republic of Guyana - Article 6.2 Initial Report (Air).txt",
        )
        assert result.get("publisher") == "Cooperative Republic of Guyana"

    def test_no_publisher_without_convention(self, extractor):
        """Legacy filenames without the ' - ' convention yield no filename publisher."""
        result = extractor.extract("Generic content.", "VM0007.md")
        # Publisher falls back to the detected registry (Verra) here.
        assert result.get("publisher") == "Verra"

    def test_version_from_filename_takes_priority(self, extractor):
        """Filename version (vX.Y) is preferred over content version scanning."""
        result = extractor.extract(
            "Some content with Version: 9.9 noise.",
            "Gold Standard - Fee Schedule v3.1.md",
        )
        assert result.get("version_number") == "3.1"

    def test_trees_document_id(self, extractor):
        """ART TREES standard document ID is extracted."""
        content = """
        The REDD+ Environmental Excellence Standard (TREES)
        Architecture for REDD+ Transactions
        TREES 2.0
        """
        result = extractor.extract(content, "ART - The REDD+ Environmental Excellence Standard (TREES) v2.0.md")
        assert result.get("registry") == "ART"
        assert result.get("publisher") == "ART"
        assert result.get("document_id") == "TREES 2.0"


class TestGetMetadataExtractor:
    """Test the singleton getter function."""
    
    def test_returns_same_instance(self):
        """Test that get_metadata_extractor returns singleton."""
        extractor1 = get_metadata_extractor()
        extractor2 = get_metadata_extractor()
        
        assert extractor1 is extractor2
    
    def test_returns_metadata_extractor(self):
        """Test that returned object is MetadataExtractor."""
        extractor = get_metadata_extractor()
        
        assert isinstance(extractor, MetadataExtractor)
