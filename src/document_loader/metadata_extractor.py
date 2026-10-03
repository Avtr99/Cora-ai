"""
Flexible metadata extraction for VCM documents.

Extracts registry, document ID, version, and other metadata from document
content and filenames. Designed to be extensible for any carbon registry.
"""
import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from threading import Lock

from ..registry_config.registry_patterns import RegistryPattern, REGISTRY_PATTERNS

logger = logging.getLogger(__name__)


# Canonical publisher names keyed by lowercase filename-prefix / alias.
# The data corpus uses a "Publisher - Title vX.Y.ext" filename convention, so the
# text before the first " - " is the strongest, lowest-risk publisher signal.
# Covers credit registries, standard bodies, AND research/market organisations so
# every detectable source org can be filtered and cited.
PUBLISHER_ALIASES: Dict[str, str] = {
    # Credit registries
    "verra": "Verra",
    "gold standard": "Gold Standard",
    "cdm": "CDM",
    "art": "ART",
    "global carbon council": "Global Carbon Council",
    "american carbon registry": "American Carbon Registry",
    "climate action reserve": "Climate Action Reserve",
    "plan vivo": "Plan Vivo",
    "pacm": "PACM",
    "isometric": "Isometric",
    "puro.earth": "Puro.earth",
    "puro earth": "Puro.earth",
    "puro": "Puro.earth",
    # Standard / governance bodies
    "social carbon": "Social Carbon",
    "socialcarbon": "Social Carbon",
    "carbon standards international": "Carbon Standards International",
    "carbon standards": "Carbon Standards International",
    "csi": "Carbon Standards International",
    "icvcm": "ICVCM",
    "sbti": "SBTi",
    "vcmi": "VCMI",
    "ghg protocol": "GHG Protocol",
    "greenhouse gas protocol": "GHG Protocol",
    "ghgp": "GHG Protocol",
    "ccb": "CCB",
    "climate community biodiversity": "CCB",
    "sd vista": "SD VISta",
    "tcat": "TCAT",
    "taskforce for corporate action transparency": "TCAT",
    # Policy / compliance
    "corsia": "CORSIA",
    # Research, ratings, and market-intelligence organisations
    "alliedoffsets": "AlliedOffsets",
    "allied offsets": "AlliedOffsets",
    "alliedoffsets & artio": "AlliedOffsets",
    "bezero": "BeZero",
    "bezero carbon": "BeZero",
    "berkeley carbon trading project": "Berkeley Carbon Trading Project",
    "carbonplan": "CarbonPlan",
    "ccqi": "CCQI",
    "calyx global": "Calyx Global",
    "forest trends": "Forest Trends",
    "world bank": "World Bank",
    "ecosystem marketplace": "Ecosystem Marketplace",
    "carbon limits": "Carbon Limits",
    "wuppertal institut": "Wuppertal Institute",
    "wuppertal institute": "Wuppertal Institute",
    "wri": "WRI",
    "wbcsd": "WBCSD",
    # Government agencies
    "bureau of energy efficiency": "Bureau of Energy Efficiency",
    # Intentional omissions: non-registry thematic categories in REGISTRY_PATTERNS
    # (VCM Policy, Market Intelligence, REDD+ / NBS, Blue Carbon,
    #  Methodology Concepts, Project Development, SD VISta / SDGs,
    #  CDR / Removals, Cookstoves / Energy, Quality Assessments)
    # are topic classifiers, not publishing organisations, so they have
    # no publisher alias. A warning is logged when publisher is None.
}

# Known file extensions to strip when parsing publisher/version from a filename.
_KNOWN_EXTENSIONS = (".md", ".txt", ".csv", ".json", ".jsonl", ".pdf")

# Version embedded in the filename convention, e.g. "... v2.0.md" -> "2.0".
_FILENAME_VERSION_PATTERN = re.compile(r'(?:^|[\s_])v(\d+(?:\.\d+)?)(?=\b|$)')


def _strip_known_extensions(filename: str) -> str:
    """Remove trailing known extensions (handles doubles like '.pdf.md')."""
    name = filename.strip()
    changed = True
    while changed:
        changed = False
        for ext in _KNOWN_EXTENSIONS:
            if name.lower().endswith(ext):
                name = name[: -len(ext)]
                changed = True
    return name.strip()


class MetadataExtractor:
    """
    Extracts structured metadata from VCM documents.
    
    Designed to be flexible and extensible for any carbon registry.
    Extracts metadata from both content and filename.
    """
    
    def __init__(self, custom_patterns: Optional[List[RegistryPattern]] = None):
        """
        Initialize with optional custom registry patterns.
        
        Args:
            custom_patterns: Additional registry patterns to use
        """
        self.patterns = REGISTRY_PATTERNS.copy()
        if custom_patterns:
            self.patterns.extend(custom_patterns)
    
    def extract(self, content: str, filename: str) -> Dict[str, Any]:
        """
        Extract all available metadata from document.

        Args:
            content: Document text content
            filename: Name of the file

        Returns:
            Dictionary with extracted metadata fields:
            - registry: Name of the carbon registry (only for real registries)
            - category: Document category (for non-registry patterns like
              Market Intelligence, VCM Policy, ICVCM, SBTi, etc.)
            - document_id: Unique document identifier
            - version_number: Document version
            - publisher: Document publisher (from filename prefix or registry
              alias, when available)

            Title extraction is intentionally not performed here; the converter
            calls title_utils._ensure_title() afterwards for a higher-quality,
            content-aware title.
        """
        metadata: Dict[str, Any] = {}

        # Combine filename and first 2000 chars of content for analysis
        analysis_text = f"{filename}\n{content[:2000]}"

        # Publisher comes first — the "Publisher - Title" filename convention
        # is a declared provenance signal and must outrank anything the
        # content merely mentions.
        publisher = self._extract_publisher_from_filename(filename)

        # Detect the best-matching taxonomy pattern for TOPIC classification.
        # Content markers legitimately say what a document is ABOUT — they can
        # never say who published it, so they do not set ``registry``.
        detected = self._detect_registry_pattern(analysis_text)
        matched_pattern = detected[0] if detected else None
        had_id_match = detected[1] if detected else False

        # Registry = provenance, from declared signals only:
        #   1. a recognised registry publisher in the filename convention,
        #   2. a registry name declared in the filename itself,
        #   3. an issuer-scoped document ID (VM0007, 115G) — IDs are assigned
        #      by the issuing registry, so an ID match is authorship evidence.
        # A document that merely mentions a registry gets it as ``category``
        # instead — topically true, provenance-safe.
        registry = self._filename_registry(publisher, filename)
        if (
            registry is None
            and matched_pattern
            and matched_pattern.is_registry
            and had_id_match
        ):
            registry = matched_pattern.name
        if registry:
            metadata["registry"] = registry

        # Category = topic: the best marker-matched pattern, including a
        # registry name when the document is about it but not published by it.
        if matched_pattern and matched_pattern.name != registry:
            metadata["category"] = matched_pattern.name

        # Extract document ID
        doc_id = self._extract_document_id(analysis_text, registry)
        if doc_id:
            metadata["document_id"] = doc_id

        # Extract version — prefer the reliable filename convention (vX.Y),
        # fall back to content/marker patterns for un-renamed legacy files.
        version = self._extract_version_from_filename(filename)
        if not version:
            version = self._extract_version(analysis_text, registry)
        if version:
            metadata["version_number"] = version

        # Note: title extraction is intentionally NOT done here. The converter
        # calls title_utils._ensure_title() after metadata extraction, which
        # produces a far better content-derived title (repetition detection,
        # doc_id matching, identifier combination, and filename fallback).
        # Keeping title extraction here would create a redundant, lower-quality
        # value that gets overwritten immediately.

        # Publisher fallback — when the filename declares no publisher, use
        # the provenance-derived registry/standard org.
        if not publisher and registry:
            publisher = PUBLISHER_ALIASES.get(registry.lower())
            if publisher is None and registry:
                logger.debug(
                    "Registry %r has no PUBLISHER_ALIASES entry; "
                    "publisher metadata will be absent for this document",
                    registry,
                )
        if publisher:
            metadata["publisher"] = publisher

        return metadata

    def _extract_publisher_from_filename(self, filename: str) -> Optional[str]:
        """
        Derive the publishing organisation from the "Publisher - Title" filename
        convention (text before the first ' - ').

        Returns a canonical name via PUBLISHER_ALIASES when recognised, otherwise
        the cleaned prefix as-is (still a valid publisher). Returns None when the
        filename does not follow the convention.
        """
        if not filename:
            return None
        stem = _strip_known_extensions(filename)
        # Real-world filenames vary the separator: "Publisher - Title",
        # "Publisher_-_Title" (download/upload-safe naming). Normalize
        # underscores to spaces before applying the convention.
        stem = re.sub(r"_+", " ", stem)
        if " - " not in stem:
            return None
        prefix = stem.split(" - ", 1)[0].strip()
        if not prefix or len(prefix) > 80:
            return None
        canonical = PUBLISHER_ALIASES.get(prefix.lower())
        if canonical:
            return canonical
        # Unknown but real publisher — keep the prefix verbatim.
        return prefix

    def _extract_version_from_filename(self, filename: str) -> Optional[str]:
        """Extract a trailing version (vX.Y) from the filename convention."""
        if not filename:
            return None
        stem = _strip_known_extensions(filename)
        matches = _FILENAME_VERSION_PATTERN.findall(stem)
        if matches:
            return matches[-1]
        return None
    
    def _filename_registry(self, publisher: Optional[str], filename: str) -> Optional[str]:
        """
        Registry declared by the filename itself.

        The "Publisher - Title" prefix is the strongest form: when it resolves
        to a known registry that wins, and the rest of the filename is treated
        as topic, not provenance. Without a prefix, a registry name inside the
        filename still counts — naming the file is a user declaration.
        """
        if publisher:
            for pattern in self.patterns:
                if pattern.is_registry and publisher.lower() == pattern.name.lower():
                    return pattern.name
            # A declared non-registry publisher takes precedence over name
            # substrings elsewhere in the filename ("ICVCM - Review of Gold
            # Standard" is an ICVCM document about Gold Standard).
            return None
        filename_text = re.sub(
            r"[^a-z0-9]+", " ", _strip_known_extensions(filename).lower()
        )
        for pattern in self.patterns:
            if not pattern.is_registry:
                continue
            name = pattern.name.lower()
            if re.search(rf"(?<![a-z0-9]){re.escape(name)}(?![a-z0-9])", filename_text):
                return pattern.name
        return None

    def _detect_registry_pattern(self, text: str) -> Optional[Tuple[RegistryPattern, bool]]:
        """
        Detect which registry/category pattern the document's content matches.

        Args:
            text: Text to analyze

        Returns:
            ``(pattern, had_id_match)`` for the best-matching pattern, or None.
            The caller uses the pattern for ``category`` (topic) and only
            promotes it to ``registry`` when ``had_id_match`` or filename
            provenance supports it — content markers alone are topic evidence.
        """
        text_lower = text.lower()

        # Score each pattern based on marker matches and explicit ID matches.
        # Prefer concrete registry ID matches over generic thematic categories.
        scores: Dict[str, Tuple[int, int, int]] = {}
        pattern_by_name: Dict[str, RegistryPattern] = {}
        for pattern in self.patterns:
            score = 0
            for marker in pattern.content_markers:
                if marker in text_lower:
                    score += 1
            if score > 0:
                has_id_match = 0
                for id_pattern in pattern.id_patterns:
                    if re.search(id_pattern, text, re.IGNORECASE):
                        has_id_match = 1
                        break

                # Prefer true registry patterns over generic categories when all else ties.
                registry_priority = 1 if pattern.is_registry else 0
                scores[pattern.name] = (has_id_match, score, registry_priority)
                pattern_by_name[pattern.name] = pattern

        if scores:
            best_name, best = max(scores.items(), key=lambda item: item[1])
            return pattern_by_name[best_name], bool(best[0])

        return None
    
    def _extract_document_id(self, text: str, registry: Optional[str] = None) -> Optional[str]:
        """
        Extract document ID using registry-specific patterns.
        
        Args:
            text: Text to analyze
            registry: Optional registry name to prioritize patterns
            
        Returns:
            Document ID if found, None otherwise
        """
        # If registry is known, try its patterns first
        if registry:
            for pattern in self.patterns:
                if pattern.name == registry:
                    for id_pattern in pattern.id_patterns:
                        match = re.search(id_pattern, text, re.IGNORECASE)
                        if match:
                            return match.group(1).upper()
        
        # Try all patterns
        for pattern in self.patterns:
            for id_pattern in pattern.id_patterns:
                match = re.search(id_pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1).upper()
        
        return None
    
    def _extract_version(self, text: str, registry: Optional[str] = None) -> Optional[str]:
        """
        Extract version number from document.
        
        Args:
            text: Text to analyze
            registry: Optional registry name to prioritize patterns
            
        Returns:
            Version string if found, None otherwise
        """
        # If registry is known, try its patterns first
        if registry:
            for pattern in self.patterns:
                if pattern.name == registry:
                    for ver_pattern in pattern.version_patterns:
                        match = re.search(ver_pattern, text, re.IGNORECASE)
                        if match:
                            return match.group(1)
        
        # Try all patterns
        for pattern in self.patterns:
            for ver_pattern in pattern.version_patterns:
                match = re.search(ver_pattern, text, re.IGNORECASE)
                if match:
                    return match.group(1)
        
        return None
    

# Singleton instance storage
_metadata_extractor_instance: Optional[MetadataExtractor] = None
_metadata_extractor_lock = Lock()


def get_metadata_extractor() -> MetadataExtractor:
    """Get or create the MetadataExtractor singleton (thread-safe)."""
    global _metadata_extractor_instance

    # Fast path: already initialized
    if _metadata_extractor_instance is not None:
        return _metadata_extractor_instance

    # Double-checked locking for thread-safe initialization
    with _metadata_extractor_lock:
        if _metadata_extractor_instance is None:
            _metadata_extractor_instance = MetadataExtractor()

    return _metadata_extractor_instance
