"""
Registry Patterns Configuration

Defines carbon registry patterns used by:
- Router: to know what's in the knowledge base
- Document loaders: to extract metadata during ingestion

This is configuration data only - no ingestion dependencies.
"""

from dataclasses import dataclass
from typing import List


@dataclass
class RegistryPattern:
    """
    Configuration for a carbon registry's document patterns.

    Attributes:
        name: Registry name (e.g., "Verra", "Gold Standard")
        content_markers: Phrases that identify this registry in content
        id_patterns: Regex patterns to extract document IDs
        version_patterns: Regex patterns to extract version numbers
    """
    name: str
    content_markers: List[str]
    id_patterns: List[str]
    version_patterns: List[str]


# Registry configurations - easily extensible
REGISTRY_PATTERNS: List[RegistryPattern] = [
    RegistryPattern(
        name="Verra",
        # Include VM/VMD/VMR patterns as content markers for registry detection
        content_markers=["verra", "vcs", "verified carbon standard", "vcu", "vm0", "vmd0", "vmr0"],
        id_patterns=[
            r'\b(VM[DR]?\d{4})\b',  # VM0007, VMD0001, VMR0004
            r'\b(VCS[-\s]?\d+)\b',  # VCS-001
            r'\b(VT\d{4})\b',       # VT0001 (tools)
        ],
        version_patterns=[
            r'[Vv]ersion[:\s*]+(\d+\.?\d*)',  # **Version:** 1.8 or Version: 1.8
            r'\bv\.?(\d+\.?\d*)\b',
            r'\bV(\d+\.?\d*)\b',
        ]
    ),
    RegistryPattern(
        name="Gold Standard",
        content_markers=["gold standard", "gs ver", "gold standard foundation", "gs-ver"],
        id_patterns=[
            r'\b(\d{2,3}G)(?:_|\b)',  # 115G, 101G (followed by underscore or word boundary)
            r'\b(GS[-\s]?\d+)\b',     # GS-001
            r'\b(TPDDTEC\d+)\b',      # TPDDTEC methodology codes
        ],
        version_patterns=[
            r'\*?\*?[Vv][Ee][Rr][Ss][Ii][Oo][Nn]\*?\*?[:\s–-]+(\d+\.?\d*)',  # **VERSION** – 1.0
            r'\bv\.?(\d+\.?\d*)\b',
        ]
    ),
    # Note: Article 6.4 is a UNFCCC policy mechanism, not a registry.
    # It is classified under VCM Policy below for correct taxonomy.
    #
    # CDM → PACM transition context:
    #   The CDM is being wound up by end-2026 (COP30, Brazil, Nov 2025).
    #   The Paris Agreement Crediting Mechanism (PACM) under Article 6.4 is the
    #   successor. New CDM methodology/tool requests are now closed. As PACM
    #   methodologies emerge, this pattern will match both legacy CDM and new
    #   PACM artifact IDs.
    RegistryPattern(
        name="CDM",
        content_markers=["clean development mechanism", "cdm", "unfccc cdm"],
        id_patterns=[
            r'\b(ACM\d{4})\b',      # ACM0001
            r'\b(AM\d{4})\b',       # AM0001
            r'\b(AMS[-\s]?[IVX]+\.?[A-Z]?\.?\d*)\b',  # AMS-I.D, AMS-III.D
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
        ]
    ),
    RegistryPattern(
        name="ART",
        # Architecture for REDD+ Transactions — issues TREES credits (a credit registry)
        content_markers=[
            "art trees", "architecture for redd+ transactions",
            "redd+ environmental excellence standard",
            "the redd+ environmental excellence standard",
        ],
        id_patterns=[
            r'\b(TREES[-\s]?[vV]?\d+(?:\.\d+)?)\b',  # TREES 2.0, TREES-2.0, TREES v2.0
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
            r'\bv\.?(\d+\.?\d*)\b',
        ]
    ),
    RegistryPattern(
        name="Global Carbon Council",
        content_markers=["global carbon council", "gcc standard", "gcc programme"],
        id_patterns=[
            r'\b(GCCM\d+)\b',  # Global Carbon Council methodology codes
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
            r'\bv\.?(\d+\.?\d*)\b',
        ]
    ),
    RegistryPattern(
        name="American Carbon Registry",
        content_markers=["american carbon registry", "acr standard", "winrock"],
        id_patterns=[],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
        ]
    ),
    RegistryPattern(
        name="Climate Action Reserve",
        content_markers=["climate action reserve", "reserve offset protocol", "climate reserve tonne"],
        id_patterns=[],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
        ]
    ),
    RegistryPattern(
        name="Plan Vivo",
        content_markers=["plan vivo", "plan vivo standard", "plan vivo certificate"],
        id_patterns=[],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
        ]
    ),
    RegistryPattern(
        name="Social Carbon",
        content_markers=["socialcarbon", "social carbon standard"],
        id_patterns=[],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
        ]
    ),
    # Paris Agreement Crediting Mechanism (PACM) — successor to CDM under
    # Article 6.4. Winding up of CDM means PACM will issue new methodologies.
    RegistryPattern(
        name="PACM",
        content_markers=[
            "paris agreement crediting mechanism", "pacm",
            "article 6.4 mechanism", "a6.4 mechanism",
        ],
        id_patterns=[
            r'\b(PACM[-\s]?[A-Z]+[-\s]?\d+)\b',  # PACM-METH-001 (future)
            r'\b(PACM[-\s]?\d+)\b',
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
            r'\bv\.?(\d+\.?\d*)\b',
        ]
    ),
    RegistryPattern(
        name="Isometric",
        content_markers=[
            "isometric", "isometric carbon", "isometric registry",
            "isometric verified",
        ],
        id_patterns=[
            r'\b(ISO-\d+)\b',  # ISO-001 (anticipated)
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
            r'\bv\.?(\d+\.?\d*)\b',
        ]
    ),
    RegistryPattern(
        name="Puro.earth",
        content_markers=[
            "puro.earth", "puro earth", "puro standard",
            "puro methodology", "carbon removal certificate",
            "puro certified",
        ],
        id_patterns=[
            r'\b(PUR[-\s]?\d+)\b',  # PUR-001
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
            r'\bv\.?(\d+\.?\d*)\b',
        ]
    ),
    RegistryPattern(
        name="Carbon Standards International",
        content_markers=[
            "carbon standards international", "csi standard",
            "csi programme", "csi registry",
        ],
        id_patterns=[
            r'\b(CSI[-\s]?\d+)\b',  # CSI-001
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
            r'\bv\.?(\d+\.?\d*)\b',
        ]
    ),
    RegistryPattern(
        name="ICVCM",
        content_markers=["icvcm", "integrity council", "core carbon principles", "ccp"],
        id_patterns=[
            r'\b(CCP[-\s]?\d+)\b',  # CCP-001
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
        ]
    ),
    RegistryPattern(
        name="SBTi",
        content_markers=["sbti", "science based targets", "science-based targets"],
        id_patterns=[
            r'\b(SBTi[-\s]?\w+)\b',
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
        ]
    ),
    RegistryPattern(
        name="CORSIA",
        content_markers=["corsia", "icao", "carbon offsetting and reduction scheme"],
        id_patterns=[
            r'\b(CORSIA[-\s]?\w+)\b',
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
        ]
    ),
    # --- Non-registry document categories ---
    RegistryPattern(
        name="VCM Policy",
        content_markers=[
            "cop29", "cop30", "cop 29", "cop 30",
            "article 6.2", "article 6", "article 6, paragraph 4",
            "article 6.4", "a6.4",
            "itmo", "ndc",
            "nationally determined contribution",
            "vcmi", "claims code", "benefit sharing",
            "double counting", "corresponding adjustment",
            "unfccc", "paris agreement",
        ],
        id_patterns=[
            r'\b(A6\.4[-\s]?[A-Z]+\d+[-\s]?[A-Z]?\d*)\b',  # A6.4-SBM014-A06
            r'\b(STAN[-\s]?METH[-\s]?\d+)\b',              # STAN-METH-001
        ],
        version_patterns=[
            r'[Vv]ersion[:\s]+(\d+\.?\d*)',
        ],
    ),
    RegistryPattern(
        name="Market Intelligence",
        content_markers=[
            "state of the market", "market report", "carbon pricing",
            "price forecast", "offset demand", "compliance market",
            "voluntary carbon market report", "credit issuance",
            "retirement", "market trends", "carbon market",
            "voluntary carbon market",
        ],
        id_patterns=[],
        version_patterns=[],
    ),
    RegistryPattern(
        name="REDD+ / NBS",
        content_markers=[
            "redd+", "redd", "afolu", "arr", "ifm", "alm",
            "avoided deforestation", "reforestation",
            "afforestation", "land use", "nesting",
            "trees", "jurisdictional", "sbti flag",
            "forest, land and agriculture",
        ],
        id_patterns=[],
        version_patterns=[],
    ),
    RegistryPattern(
        name="Blue Carbon",
        content_markers=[
            "blue carbon", "mangrove", "freshwater wetland",
            "tidal wetland", "seagrass", "macroalgae",
        ],
        id_patterns=[],
        version_patterns=[],
    ),
    RegistryPattern(
        name="Methodology Concepts",
        content_markers=[
            "additionality", "baseline", "permanence", "leakage",
            "monitoring", "verification", "mrv",
            "non-permanence risk", "crediting period",
            "emission reduction", "emission factor",
            "ghg protocol",
            "ozone depleting substances", "ozone-depleting substances",
            "advanced and indirect mitigation",
        ],
        id_patterns=[],
        version_patterns=[],
    ),
    RegistryPattern(
        name="Project Development",
        content_markers=[
            "project design document", "pdd", "validation",
            "registration", "issuance", "ccb standards",
            "project cycle", "fee schedule",
        ],
        id_patterns=[],
        version_patterns=[],
    ),
    RegistryPattern(
        name="SD VISta / SDGs",
        content_markers=[
            "sd vista", "sdg", "sustainable development",
            "co-benefits", "safeguards",
        ],
        id_patterns=[],
        version_patterns=[],
    ),
    RegistryPattern(
        name="CDR / Removals",
        content_markers=[
            "carbon dioxide removal", "cdr", "direct air capture",
            "dac", "biochar", "enhanced weathering",
            "accelerated carbonation", "carbon capture",
            "geologic storage", "bioenergy",
        ],
        id_patterns=[],
        version_patterns=[],
    ),
    RegistryPattern(
        name="Cookstoves / Energy",
        content_markers=[
            "cookstove", "cooking", "improved cookstove",
            "clean cooking", "energy efficiency",
            "metered energy",
        ],
        id_patterns=[],
        version_patterns=[],
    ),
    RegistryPattern(
        name="Quality Assessments",
        content_markers=[
            "ccqi", "calyx global", "carbon credit quality",
            "quality initiative", "rating",
        ],
        id_patterns=[],
        version_patterns=[],
    ),
]
