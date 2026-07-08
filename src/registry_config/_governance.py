"""
Governance / standard body patterns (``is_registry=False``).

These are organisations that set standards, accredit programs, or define
frameworks — but do **not** issue carbon credits themselves.  The
metadata extractor stores the pattern name under the ``category`` field
(not ``registry``) to keep the ``registry`` field clean.

Included:
  ICVCM  — Integrity Council for the Voluntary Carbon Market (CCP framework)
  SBTi   — Science Based Targets initiative
  CORSIA — ICAO Carbon Offsetting and Reduction Scheme
  VCMI   — Voluntary Carbon Markets Integrity Initiative (Claims Code)
  GHG Protocol — Greenhouse Gas accounting standard (Scope 1/2/3)
  CDP    — Carbon Disclosure Project
  ICROA  — International Carbon Reduction and Offset Alliance
"""

from typing import List

from ._common import RegistryPattern, VERSION_STANDARD

GOVERNANCE_PATTERNS: List[RegistryPattern] = [
    RegistryPattern(
        name="ICVCM",
        content_markers=["icvcm", "integrity council", "core carbon principles", "ccp"],
        id_patterns=[
            r'\b(CCP[-\s]?\d+)\b',  # CCP-001
        ],
        version_patterns=VERSION_STANDARD,
        is_registry=False,
    ),
    RegistryPattern(
        name="SBTi",
        content_markers=["sbti", "science based targets", "science-based targets"],
        id_patterns=[
            r'\b(SBTi[-\s]?\w+)\b',
        ],
        version_patterns=VERSION_STANDARD,
        is_registry=False,
    ),
    RegistryPattern(
        name="CORSIA",
        content_markers=[
            "corsia", "icao", "carbon offsetting and reduction scheme",
            "corsia phase 2", "corsia second phase", "2027-2029",
            "corsia eligible emissions units",
        ],
        id_patterns=[
            r'\b(CORSIA[-\s]?\w+)\b',
        ],
        version_patterns=VERSION_STANDARD,
        is_registry=False,
    ),
    # VCMI — Voluntary Carbon Markets Integrity Initiative. Issues the Claims
    # Code of Practice for corporate use of carbon credits. Complements ICVCM
    # (supply-side integrity) with demand-side integrity guidance.
    RegistryPattern(
        name="VCMI",
        content_markers=[
            "vcmi", "voluntary carbon markets integrity initiative",
            "vcmi claims code", "claims code of practice",
            "vcmi claim",
        ],
        id_patterns=[],
        version_patterns=VERSION_STANDARD,
        is_registry=False,
    ),
    # GHG Protocol — Greenhouse Gas Protocol. Accounting standard for
    # measuring and reporting emissions (Scope 1, 2, 3). Developed by
    # WRI and WBCSD. Underpins SBTi, CDP, VCMI, and CSRD.
    RegistryPattern(
        name="GHG Protocol",
        content_markers=[
            "ghg protocol", "greenhouse gas protocol",
            "corporate accounting and reporting standard",
            "value chain accounting", "land sector and removals",
        ],
        id_patterns=[],
        version_patterns=VERSION_STANDARD,
        is_registry=False,
    ),
    # CDP — Carbon Disclosure Project. Global environmental disclosure
    # platform. 25,000+ entities report via CDP in 2025.
    RegistryPattern(
        name="CDP",
        content_markers=[
            "cdp", "carbon disclosure project",
            "cdp climate disclosure", "cdp questionnaire",
        ],
        id_patterns=[],
        version_patterns=VERSION_STANDARD,
        is_registry=False,
    ),
    # ICROA — International Carbon Reduction and Offset Alliance.
    # Accredits carbon offset service providers and endorses crediting
    # programs against its Code of Best Practice.
    RegistryPattern(
        name="ICROA",
        content_markers=[
            "icroa", "international carbon reduction and offset alliance",
            "icroa code of best practice", "icroa endorsed",
            "icroa accredited",
        ],
        id_patterns=[],
        version_patterns=VERSION_STANDARD,
        is_registry=False,
    ),
]
