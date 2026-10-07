"""Topic category patterns (``is_registry=False``).

Thematic classifiers — what a document is *about* (REDD+, blue carbon,
CDR), not who issued it. The metadata extractor stores the match under
``category``.

Markers match by case-insensitive substring and also seed the router's KB
keyword set — keep broad domain terms out. Short acronyms embedded in
common words were removed as false-positive risks (``arr``, ``alm``,
``ods``, ``saf``, ``rating``, ``retirement``), as were terms owned by more
specific patterns (``ghg protocol``, ``vcmi``, ``compliance market``) or
too generic to classify (``monitoring``, ``verification``,
``transportation``).
"""

from typing import List

from ._common import RegistryPattern

CATEGORY_PATTERNS: List[RegistryPattern] = [
    # ── Policy & market topics ─────────────────────────────────────
    RegistryPattern(
        name="VCM Policy",
        content_markers=[
            "cop29", "cop30", "cop 29", "cop 30",
            "article 6.2", "article 6", "article 6, paragraph 4",
            "article 6.4", "a6.4",
            "itmo", "ndc",
            "nationally determined contribution",
            "benefit sharing",
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
        is_registry=False,
        doc_type="policy",
    ),
    RegistryPattern(
        name="Market Intelligence",
        content_markers=[
            "state of the market", "market report", "carbon pricing",
            "price forecast", "offset demand",
            "voluntary carbon market report", "credit issuance",
            "credit retirement", "unit retirement",
            "market trends",
            # NOTE: "carbon market" and "voluntary carbon market" removed —
            # they are domain-level terms that match nearly every VCM document,
            # causing widespread misclassification as "Market Intelligence".
            # A document needs specific market-report markers to qualify.
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
    ),

    # ── Nature-based solutions ─────────────────────────────────────
    RegistryPattern(
        name="REDD+ / NBS",
        content_markers=[
            "redd+", "redd", "afolu",
            "avoided deforestation", "reforestation",
            "afforestation", "land use", "nesting",
            "jurisdictional", "sbti flag",
            "forest, land and agriculture",
            "agroforestry", "silvopasture",
            "forest carbon", "forest management",
            "deforestation", "degradation",
            "protected area", "conservation concession",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
    ),
    RegistryPattern(
        name="Blue Carbon",
        content_markers=[
            "blue carbon", "mangrove", "freshwater wetland",
            "tidal wetland", "seagrass", "macroalgae",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
    ),

    # ── Methodology & project cycle ────────────────────────────────
    RegistryPattern(
        name="Methodology Concepts",
        content_markers=[
            "additionality", "baseline", "permanence", "leakage",
            "mrv", "monitoring plan", "verification report",
            "non-permanence risk", "crediting period",
            "emission reduction", "emission factor",
            "ozone depleting substances", "ozone-depleting substances",
            "advanced and indirect mitigation",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
        doc_type="methodology",
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
        is_registry=False,
        doc_type="project",
    ),
    RegistryPattern(
        name="SD VISta / SDGs",
        content_markers=[
            "sd vista", "sdg", "sustainable development",
            "co-benefits", "safeguards",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
        doc_type="standard",
    ),

    # ── Carbon removal pathways ────────────────────────────────────
    RegistryPattern(
        name="CDR / Removals",
        content_markers=[
            "carbon dioxide removal", "cdr", "direct air capture",
            "dac", "daccs", "biochar", "enhanced weathering",
            "accelerated carbonation", "carbon capture",
            "geologic storage", "bioenergy",
            "beccs", "biomass burial", "bicrs",
            "mcdr", "marine carbon dioxide removal",
            "ocean alkalinity enhancement",
            "mineralization", "carbon mineralization",
            "biomass carbon removal and storage",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
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
        is_registry=False,
    ),

    # ── Quality & ratings ──────────────────────────────────────────
    RegistryPattern(
        name="Quality Assessments",
        content_markers=[
            "ccqi", "calyx global", "carbon credit quality",
            "quality initiative",
            "sylvera", "bezero", "renoster",
            "carbon ratings agency", "carbon rating",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
    ),

    # ── Compliance markets & sectoral categories ───────────────────
    # Compliance Markets — Cap-and-trade systems, border adjustments, and
    # government-mandated carbon pricing mechanisms. Distinct from the VCM
    # but increasingly interconnected (e.g., CORSIA, CBAM, Article 6).
    RegistryPattern(
        name="Compliance Markets",
        content_markers=[
            "eu ets", "european union emissions trading system",
            "eu emissions trading", "eutl", "union registry",
            "cbam", "carbon border adjustment mechanism",
            "uk ets", "uk emissions trading",
            "china ets", "china national ets", "cea allowance",
            "k-ets", "korea ets", "korean emissions trading",
            "california cap-and-trade", "california cap and trade",
            "cap and trade", "cap-and-trade",
            "allowances", "allowance allocation",
            "jcm", "joint crediting mechanism",
            "new zealand ets", "nz ets",
            "swiss ets",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
        doc_type="policy",
    ),
    # Agriculture / Soil Carbon — Regenerative agriculture, soil organic
    # carbon, enteric fermentation, agroforestry, and livestock management.
    RegistryPattern(
        name="Agriculture / Soil Carbon",
        content_markers=[
            "regenerative agriculture", "soil carbon", "soil organic carbon",
            "enteric fermentation", "agroforestry", "silvopasture",
            "cover crop", "grazing management", "rice cultivation",
            "manure management", "nitrous oxide", "n2o",
            "fertilizer management", "conservation tillage",
            "cropland", "grassland", "rangeland",
            "soil carbon quantification", "carbon farming",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
    ),
    # Industrial / Waste — Industrial gases, landfill, wastewater, anaerobic
    # digestion, and energy-intensive sector decarbonization.
    RegistryPattern(
        name="Industrial / Waste",
        content_markers=[
            "industrial gas", "hfc", "pfc", "sf6", "nf3",
            "ozone depleting substances", "ozone-depleting substances",
            "landfill", "landfill methane", "wastewater",
            "waste management", "anaerobic digestion",
            "biogas", "biomethane",
            "cement", "steel", "chemical industry",
            "industrial decarbonization", "process emissions",
            "blast furnace", "clinker",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
    ),
    # Transportation / Fuels — EV, biofuels, sustainable aviation fuel,
    # low-carbon fuel standards, and maritime/shipping decarbonization.
    RegistryPattern(
        name="Transportation / Fuels",
        content_markers=[
            "electric vehicle", "ev fleet", "vehicle electrification",
            "biofuel", "biodiesel", "bioethanol",
            "sustainable aviation fuel",
            "lcfs", "low carbon fuel standard",
            "fuel switching", "fuel efficiency",
            "marine fuel", "shipping decarbonization",
            "imo 2020", "imo strategy",
            "transportation sector", "fleet decarbonization",
        ],
        id_patterns=[],
        version_patterns=[],
        is_registry=False,
    ),
]
