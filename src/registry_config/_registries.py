"""
Credit-issuing registry patterns (``is_registry=True``).

Each ``RegistryPattern`` in this module represents a real carbon credit
registry — an organisation that issues, tracks, and retires serialized
carbon credits.  The metadata extractor stores the pattern name under
the ``registry`` metadata field.

Ordered by market significance.  Order matters for scoring tie-breaks
in ``MetadataExtractor._detect_registry_pattern`` — when two patterns
have equal scores, the first one encountered wins.
"""

from typing import List

from ._common import RegistryPattern, VERSION_EXTENDED, VERSION_STANDARD

REGISTRY_PATTERNS: List[RegistryPattern] = [
    # ── Major voluntary carbon registries ──────────────────────────
    RegistryPattern(
        name="Verra",
        # Include VM/VMD/VMR patterns as content markers for registry detection
        content_markers=[
            "verra", "vcs", "verified carbon standard", "vcu",
            "vm0", "vmd0", "vmr0",
            "s&p global energy",  # Verra registry migrated to S&P Global (July 2026)
        ],
        id_patterns=[
            r'\b(VM[DR]?\d{4})\b',  # VM0007, VMD0001, VMR0004
            r'\b(VCS[-\s]?\d+)\b',  # VCS-001
            r'\b(VT\d{4})\b',       # VT0001 (tools)
        ],
        version_patterns=[
            r'[Vv]ersion[:\s*]+(\d+\.?\d*)',  # **Version:** 1.8 or Version: 1.8
            r'\bv\.?(\d+\.?\d*)\b',
            r'\bV(\d+\.?\d*)\b',
        ],
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
        ],
    ),
    # Note: Article 6.4 is a UNFCCC policy mechanism, not a registry.
    # It is classified under VCM Policy in _categories.py for correct taxonomy.
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
        version_patterns=VERSION_STANDARD,
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
        version_patterns=VERSION_EXTENDED,
    ),
    RegistryPattern(
        name="Global Carbon Council",
        content_markers=["global carbon council", "gcc standard", "gcc programme"],
        id_patterns=[
            r'\b(GCCM\d+)\b',  # Global Carbon Council methodology codes
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    RegistryPattern(
        name="American Carbon Registry",
        content_markers=[
            "american carbon registry", "acr standard", "winrock",
            "ice greentrace",  # ACR migrated to ICE GreenTrace (2026)
            "environmental resources trust",  # ACR's parent org (ERT)
        ],
        id_patterns=[],
        version_patterns=VERSION_STANDARD,
    ),
    RegistryPattern(
        name="Climate Action Reserve",
        content_markers=["climate action reserve", "reserve offset protocol", "climate reserve tonne"],
        id_patterns=[],
        version_patterns=VERSION_STANDARD,
    ),
    RegistryPattern(
        name="Plan Vivo",
        content_markers=["plan vivo", "plan vivo standard", "plan vivo certificate"],
        id_patterns=[],
        version_patterns=VERSION_STANDARD,
    ),
    RegistryPattern(
        name="Social Carbon",
        content_markers=["socialcarbon", "social carbon standard"],
        id_patterns=[],
        version_patterns=VERSION_STANDARD,
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
        version_patterns=VERSION_EXTENDED,
    ),

    # ── CDR-focused registries ─────────────────────────────────────
    RegistryPattern(
        name="Isometric",
        content_markers=[
            "isometric", "isometric carbon", "isometric registry",
            "isometric verified",
        ],
        id_patterns=[
            r'\b(ISO-\d+)\b',  # ISO-001 (anticipated)
        ],
        version_patterns=VERSION_EXTENDED,
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
        version_patterns=VERSION_EXTENDED,
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
        version_patterns=VERSION_EXTENDED,
    ),

    # ── Regional / national registries (global coverage) ───────────
    # Cercarbono — Colombian voluntary standard, ICROA-endorsed, CORSIA-eligible.
    # Uses EcoRegistry as its registry platform. 190+ projects across Latin
    # America, Turkey, and Southeast Asia.
    RegistryPattern(
        name="Cercarbono",
        content_markers=[
            "cercarbono", "certified carbon standard", "ecoregistry",
            "cercarbono standard", "cercarbono protocol",
        ],
        id_patterns=[
            r'\b(CER[-\s]?\d+)\b',  # CER-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # BioCarbon Registry — BioCarbon's GHG Crediting Program. Issues BCR credits.
    # Growing registry for nature-based and removal projects.
    RegistryPattern(
        name="BioCarbon Registry",
        content_markers=[
            "biocarbon registry", "biocarbon standard", "biocarbon",
            "bcr standard", "bcr carbon standard",
        ],
        id_patterns=[
            r'\b(BCR[-\s]?\d+)\b',  # BCR-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # International Carbon Registry (ICR) — ICROA-endorsed, ISO 14064-2 based.
    # Follows Paris Agreement Article 6 principles.
    RegistryPattern(
        name="International Carbon Registry",
        content_markers=[
            "international carbon registry", "icr standard",
            "icr programme", "carbonregistry.com",
        ],
        id_patterns=[
            r'\b(ICR[-\s]?\d+)\b',  # ICR-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # Climate Forward — CAR's forward-looking crediting program. Issues
    # Forecasted Mitigation Units (FMUs) for ex ante crediting.
    RegistryPattern(
        name="Climate Forward",
        content_markers=[
            "climate forward", "forecast mitigation unit", "fmu",
            "climate forward registry", "forward crediting",
        ],
        id_patterns=[
            r'\b(FMU[-\s]?\d+)\b',  # FMU-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # J-Credit Scheme — Japanese government-backed domestic credit scheme.
    # Certifies GHG reductions and removals within Japan. CORSIA-eligible.
    RegistryPattern(
        name="J-Credit Scheme",
        content_markers=[
            "j-credit", "jcredit", "j-credit scheme",
            "japan credit scheme", "j-ver",
        ],
        id_patterns=[
            r'\b(JC[-\s]?\d+)\b',  # JC-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # CCER — China Certified Emission Reduction. National voluntary offset
    # mechanism, relaunched January 2024 after 2017 suspension.
    # Registry operated by NCSC; trading on Beijing Green Exchange.
    RegistryPattern(
        name="CCER",
        content_markers=[
            "ccer", "chinese certified emission reduction",
            "china certified emission reduction",
            "beijing green exchange", "national voluntary emission reduction",
        ],
        id_patterns=[
            r'\b(CCER[-\s]?\d+)\b',  # CCER-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # OxCarbon — Issues OxCs on S&P Global Environmental Registry.
    # ICROA-endorsed. Principles-based standard.
    RegistryPattern(
        name="OxCarbon",
        content_markers=[
            "oxcarbon", "oxc", "oxcarbon principles",
            "s&p global environmental registry",
            "oxcarbon certificates",
        ],
        id_patterns=[
            r'\b(OxC[-\s]?\d+)\b',  # OxC-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # Equitable Earth — Ecosystem restoration registry, APX-hosted.
    # ICROA conditionally endorsed. CCP-Eligible. Issues Equitable Carbon
    # Units (ECUs). Focus on IPs and LCs, biodiversity, and livelihoods.
    # Formerly Ecosystem Restoration Standard (ERS) — rebranded July 2025
    # after ERS acquired the Equitable Earth brand. Legacy documents may
    # still reference "ERS" or "Ecosystem Restoration Standard".
    RegistryPattern(
        name="Equitable Earth",
        content_markers=[
            "equitable earth", "equitable carbon unit",
            "eq-earth", "ecu standard",
            "ers standard", "ecosystem restoration standard",  # former name
        ],
        id_patterns=[
            r'\b(ECU[-\s]?\d+)\b',  # ECU-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # Proba — Supply chain inset/offset standard. ICROA conditionally endorsed.
    # Issues Proba Inset Units (PIUs) for scope 3 value chain decarbonization.
    # NOTE: bare "proba" removed — it matches "probable", "probably" in
    # common English text via substring matching.
    RegistryPattern(
        name="Proba",
        content_markers=[
            "proba standard", "proba registry",
            "proba inset", "inset unit",
        ],
        id_patterns=[
            r'\b(PIU[-\s]?\d+)\b',  # PIU-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # Rainbow (formerly Riverse) — French CDR registry. ICROA-endorsed.
    # Rebranded from Riverse to Rainbow in 2026. CCP-Eligible (Rainbow
    # Standard Rules v7+). Focus on durable carbon removal projects.
    # NOTE: bare "rainbow" removed — it matches common English "rainbow"
    # via substring matching. "riverse" kept for legacy document detection.
    RegistryPattern(
        name="Rainbow",
        content_markers=[
            "rainbow standard", "rainbow registry",
            "rainbow carbon", "riverse",  # former name — legacy documents
        ],
        id_patterns=[
            r'\b(RAIN[-\s]?\d+)\b',  # RAIN-001 (Rainbow)
            r'\b(RIV[-\s]?\d+)\b',   # RIV-001 (legacy Riverse)
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # Premium T-VER — Thailand Voluntary Emission Reduction Program.
    # CORSIA-eligible for 2024-2026 compliance period. Operated by TGO
    # (Thailand Greenhouse Gas Management Organization). Issues Carbon
    # Credits from projects situated in Thailand.
    RegistryPattern(
        name="Premium T-VER",
        content_markers=[
            "premium t-ver", "t-ver", "tver",
            "thailand voluntary emission reduction",
            "thailand greenhouse gas", "tgo carbon",
        ],
        id_patterns=[
            r'\b(T-VER[-\s]?P?[-\s]?\d+[-\s]?\d+)\b',  # T-VER-P-METH-13-04
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # Indonesia SRUK — National Carbon Unit Registry System (Sistem
    # Registrasi Unit Karbon). Launched July 9, 2026. Connected to
    # IDXCarbon exchange. Covers forestry, energy, industry, agriculture,
    # marine, and environment sectors. Issues SPE (Sertifikat Pengurangan
    # Emisi Gas) credits. Article 6 aligned.
    RegistryPattern(
        name="Indonesia SRUK",
        content_markers=[
            "sruk", "sistem registrasi unit karbon",
            "national carbon unit registry", "indonesia carbon registry",
            "idxcarbon", "nilai ekonomi karbon",
            "sertifikat pengurangan emisi", "spe credit",
        ],
        id_patterns=[
            r'\b(SPE[-\s]?\d+)\b',  # SPE-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # India CCTS — Carbon Credit Trading Scheme. Notified by Ministry of
    # Power 2023; CERC trading rules notified Feb 27, 2026. Registry
    # operated by GRID-INDIA. Issues Carbon Credit Certificates (CCCs).
    # Covers steel, cement, aluminium, fertilisers. CBAM-driven.
    RegistryPattern(
        name="India CCTS",
        content_markers=[
            "carbon credit trading scheme", "ccts",
            "carbon credit certificate", "ccc trading",
            "bureau of energy efficiency", "bee",
            "grid-india", "grid india",
            "cerc carbon market", "india carbon market",
        ],
        id_patterns=[
            r'\b(CCC[-\s]?\d+)\b',  # CCC-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
    # DRC Lumiere — Democratic Republic of Congo national carbon registry.
    # Full launch expected 2026. Article 6 and CORSIA aligned. Developed
    # by DRC Ministry of Environment with M&M Greentech and TRST01.
    RegistryPattern(
        name="DRC Lumiere",
        content_markers=[
            "lumiere", "lumiere credit carbon",
            "drc carbon registry", "congo carbon registry",
            "m&m greentech", "trst01",
        ],
        id_patterns=[
            r'\b(LUM[-\s]?\d+)\b',  # LUM-001
        ],
        version_patterns=VERSION_EXTENDED,
    ),
]
