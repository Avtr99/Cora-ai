/**
 * VCM Domain Glossary
 *
 * Static dictionary of Voluntary Carbon Market terminology used by the
 * GlossaryHydrator to inject contextual hover definitions into AI responses.
 *
 * Matching is case-insensitive and whole-word. Order matters: longer terms
 * are matched first to avoid partial overlaps (e.g. "REDD+" before "REDD").
 *
 * Add new terms here — no other file changes required.
 */

export interface GlossaryEntry {
  /** Canonical display term (used in the HoverCard title). */
  term: string;
  /** One-sentence plain-language definition. */
  definition: string;
  /** Optional category tag shown as a pill above the definition. */
  category?: string;
}

export const VCM_GLOSSARY: GlossaryEntry[] = [
  // ── Standards & Registries ──────────────────────────────────────────
  {
    term: 'CORSIA',
    definition:
      'Carbon Offsetting and Reduction Scheme for International Aviation — an ICAO-mandated program requiring airlines to offset CO₂ emissions from international flights above 2020 baseline levels.',
    category: 'Standard',
  },
  {
    term: 'Verra',
    definition:
      'A global standards body that manages the Verified Carbon Standard (VCS), the world\'s most widely used voluntary GHG program.',
    category: 'Registry',
  },
  {
    term: 'Gold Standard',
    definition:
      'A certification standard for carbon offset projects that requires demonstration of real, measurable climate benefits and contributions to sustainable development goals.',
    category: 'Standard',
  },
  {
    term: 'Verified Carbon Standard|VCS',
    definition:
      'Verified Carbon Standard — Verra\'s flagship program for certifying GHG emission reductions and removals in the voluntary market.',
    category: 'Standard',
  },
  {
    term: 'American Carbon Registry|ACR',
    definition:
      'One of the earliest voluntary GHG registries in the U.S., now a program of Winrock International, issuing Emission Reduction Tonnes (ERTs) across forestry, waste, and energy sectors.',
    category: 'Registry',
  },
  {
    term: 'Climate Action Reserve|CAR',
    definition:
      'A U.S.-focused carbon offset registry that develops standardized protocols and issues Climate Reserve Tonnes (CRTs) for North American project types.',
    category: 'Registry',
  },
  {
    term: 'Plan Vivo',
    definition:
      'A certification framework for community-led, nature-based projects in developing countries, emphasizing smallholder participation and ecosystem services.',
    category: 'Standard',
  },
  {
    term: 'Puro.earth',
    definition:
      'A registry specializing in engineered carbon removal credits (CORCs), covering methods like biochar, enhanced weathering, and direct air capture.',
    category: 'Registry',
  },
  {
    term: 'Architecture for REDD+ Transactions|ART',
    definition:
      'Architecture for REDD+ Transactions — a standard that issues jurisdictional-scale forest carbon credits (TREES credits) to national or subnational governments.',
    category: 'Standard',
  },
  {
    term: 'TREES',
    definition:
      'The REDD+ Environmental Excellence Standard — ART\'s crediting framework for high-integrity, jurisdictional-scale REDD+ programs.',
    category: 'Standard',
  },
  {
    term: 'Clean Development Mechanism|CDM',
    definition:
      'Clean Development Mechanism — a UNFCCC mechanism under the Kyoto Protocol that allows developed countries to earn emission reduction credits by investing in emission reduction projects in developing countries.',
    category: 'Standard',
  },
  {
    term: 'Global Carbon Council',
    definition:
      'A carbon crediting program based in the Gulf region that approves methodologies and issues Approved Carbon Credits (ACCs) for voluntary and CORSIA-eligible projects.',
    category: 'Registry',
  },
  {
    term: 'Social Carbon',
    definition:
      'A standard developed by the Ecológica Institute that evaluates the co-benefits of carbon projects across six sustainability dimensions including biodiversity and community well-being.',
    category: 'Standard',
  },
  {
    term: 'Climate, Community & Biodiversity Standards|CCB Standards',
    definition:
      'Climate, Community & Biodiversity Standards — a Verra-managed add-on certification that evaluates land-based projects for climate, community, and biodiversity co-benefits.',
    category: 'Standard',
  },
  {
    term: 'Sustainable Development Verified Impact Standard|SD VISta',
    definition:
      'Sustainable Development Verified Impact Standard — a Verra program that certifies and quantifies a project\'s contributions to the UN Sustainable Development Goals.',
    category: 'Standard',
  },

  // ── Core Concepts ───────────────────────────────────────────────────
  {
    term: 'Additionality',
    definition:
      'The principle that greenhouse gas reductions would not have occurred without the financial incentive provided by carbon credit revenues.',
    category: 'Core Concept',
  },
  {
    term: 'Permanence',
    definition:
      'The requirement that carbon removals or emission reductions are long-lasting and not reversed, typically guaranteed for a minimum of 100 years.',
    category: 'Core Concept',
  },
  {
    term: 'Leakage',
    definition:
      'An increase in GHG emissions outside a project boundary that occurs as a direct result of the project activity — effectively displacing, rather than reducing, emissions.',
    category: 'Core Concept',
  },
  {
    term: 'Baseline',
    definition:
      'A reference scenario representing the level of emissions that would occur in the absence of the carbon credit project, against which reductions are measured.',
    category: 'Core Concept',
  },
  {
    term: 'MRV',
    definition:
      'Measurement, Reporting, and Verification — the systematic process of quantifying emissions reductions, documenting them, and having them independently audited.',
    category: 'Core Concept',
  },
  {
    term: 'Co-benefits',
    definition:
      'Positive social, economic, or environmental impacts beyond GHG reduction, such as biodiversity conservation, community development, or improved health outcomes.',
    category: 'Core Concept',
  },
  {
    term: 'Double Counting',
    definition:
      'The risk that the same emission reduction or removal is claimed by more than one entity — encompassing double issuance, double use, and double claiming.',
    category: 'Core Concept',
  },
  {
    term: 'Corresponding Adjustment',
    definition:
      'An accounting entry by a host country under Article 6 of the Paris Agreement that adds the transferred emission reductions back to its own inventory, preventing double counting between nations.',
    category: 'Core Concept',
  },
  {
    term: 'Crediting Period',
    definition:
      'The fixed time window during which a carbon project is eligible to generate credits, often 7–10 years and renewable depending on the standard.',
    category: 'Core Concept',
  },
  {
    term: 'Project Boundary',
    definition:
      'The defined geographic area and set of GHG sources, sinks, and reservoirs that are included in a project\'s emission reduction accounting.',
    category: 'Core Concept',
  },
  {
    term: 'Counterfactual',
    definition:
      'The hypothetical scenario describing what would have happened in the absence of the carbon project — the basis for determining baseline emissions and additionality.',
    category: 'Core Concept',
  },
  {
    term: 'Conservativeness',
    definition:
      'A crediting principle that requires assumptions and parameters to err on the side of under-crediting rather than over-crediting emission reductions.',
    category: 'Core Concept',
  },
  {
    term: 'Over-crediting',
    definition:
      'The issuance of more carbon credits than the actual emission reductions achieved, often due to inflated baselines or inaccurate measurement.',
    category: 'Core Concept',
  },
  {
    term: 'Reversal',
    definition:
      'The unintended release of previously sequestered carbon back into the atmosphere, for example through wildfire, disease, or land-use change.',
    category: 'Core Concept',
  },
  {
    term: 'Avoidance Credit',
    definition:
      'A carbon credit generated by preventing emissions that would have otherwise occurred (e.g., protecting a forest from being cleared) as opposed to actively removing CO₂ from the atmosphere.',
    category: 'Core Concept',
  },
  {
    term: 'Removal Credit',
    definition:
      'A carbon credit generated by physically drawing CO₂ out of the atmosphere and storing it durably — examples include afforestation, BECCS, and direct air capture.',
    category: 'Core Concept',
  },
  {
    term: 'Carbon Insetting',
    definition:
      'Investing in emission reduction or removal activities within a company\'s own value chain, rather than purchasing offsets from external third-party projects.',
    category: 'Core Concept',
  },
  {
    term: 'Carbon Offsetting',
    definition:
      'The practice of compensating for an entity\'s own emissions by purchasing carbon credits from external projects that reduce or remove an equivalent amount of CO₂e.',
    category: 'Core Concept',
  },
  {
    term: 'Stacking',
    definition:
      'Generating and selling multiple types of environmental credits (e.g., carbon credits and biodiversity credits) from the same project area, provided there is no double counting of the same benefit.',
    category: 'Core Concept',
  },
  {
    term: 'Bundling',
    definition:
      'Combining different environmental attributes (e.g., carbon reduction + SDG impact) into a single credit product, as opposed to selling them separately.',
    category: 'Core Concept',
  },
  {
    term: 'Like-for-like',
    definition:
      'A compensation principle stating that CO₂ emissions from fossil sources should ideally be offset by credits that represent equivalent long-duration storage, not short-cycle sequestration.',
    category: 'Core Concept',
  },
  {
    term: 'GHG Protocol',
    definition:
      'The most widely used international accounting framework for quantifying and reporting greenhouse gas emissions across Scope 1, 2, and 3 categories.',
    category: 'Core Concept',
  },
  {
    term: 'Scope 1 Emissions',
    definition:
      'Direct GHG emissions from sources owned or controlled by an organization, such as on-site combustion or company vehicles.',
    category: 'Core Concept',
  },
  {
    term: 'Scope 2 Emissions',
    definition:
      'Indirect GHG emissions from the generation of purchased electricity, steam, heating, or cooling consumed by an organization.',
    category: 'Core Concept',
  },
  {
    term: 'Scope 3 Emissions',
    definition:
      'All other indirect GHG emissions in a company\'s value chain — including supply chain, business travel, employee commuting, and end-of-life treatment of products.',
    category: 'Core Concept',
  },
  {
    term: 'Global Warming Potential|GWP',
    definition:
      'Global Warming Potential — a factor that converts the climate impact of a given greenhouse gas into the equivalent amount of CO₂ over a specified time horizon, typically 100 years.',
    category: 'Core Concept',
  },
  {
    term: 'Emissions Factor',
    definition:
      'A coefficient that translates an activity (e.g., burning one litre of diesel) into a quantity of greenhouse gas emissions, expressed in kg or tonnes of CO₂e per unit of activity.',
    category: 'Core Concept',
  },
  {
    term: 'Benefit Sharing',
    definition:
      'The agreed-upon mechanism for distributing carbon credit revenues among project developers, landowners, local communities, and other stakeholders.',
    category: 'Core Concept',
  },
  {
    term: 'Free, Prior, and Informed Consent|FPIC',
    definition:
      'Free, Prior, and Informed Consent — the right of Indigenous peoples and local communities to give or withhold consent for projects that affect their lands, territories, or resources.',
    category: 'Core Concept',
  },
  {
    term: 'Safeguards',
    definition:
      'Policies and procedures that carbon projects must follow to prevent negative social and environmental impacts, including respect for land rights, biodiversity, and community well-being.',
    category: 'Core Concept',
  },

  // ── Project Types ──────────────────────────────
  {
    term: 'REDD+',
    definition:
      'Reducing Emissions from Deforestation and Forest Degradation — a framework that incentivizes developing countries to protect and manage their forests to avoid carbon emissions.',
    category: 'Project Type',
  },
  {
    term: 'Afforestation, Reforestation, and Revegetation|ARR',
    definition:
      'Afforestation, Reforestation, and Revegetation — project activities that increase carbon stocks by establishing or re-establishing forest cover on previously non-forested land.',
    category: 'Project Type',
  },
  {
    term: 'Blue Carbon',
    definition:
      'Carbon captured and stored by coastal and marine ecosystems — primarily mangroves, seagrasses, and salt marshes — which sequester carbon at rates up to 10× faster than terrestrial forests.',
    category: 'Project Type',
  },
  {
    term: 'Improved Forest Management|IFM',
    definition:
      'Improved Forest Management — project activities that increase carbon stocks or reduce emissions on forested lands through practices like extended rotation lengths or reduced-impact logging.',
    category: 'Project Type',
  },
  {
    term: 'Biochar',
    definition:
      'A stable, carbon-rich solid produced by heating biomass in the absence of oxygen (pyrolysis), which locks carbon into a form that resists decomposition for hundreds to thousands of years when applied to soil.',
    category: 'Project Type',
  },
  {
    term: 'Direct Air Capture|DAC',
    definition:
      'A technology that uses chemical processes to capture CO₂ directly from ambient air, which is then permanently stored underground or utilized in durable products.',
    category: 'Project Type',
  },
  {
    term: 'Bioenergy with Carbon Capture and Storage|BECCS',
    definition:
      'Bioenergy with Carbon Capture and Storage — a process that generates energy from biomass while capturing and permanently storing the resulting CO₂ emissions underground.',
    category: 'Project Type',
  },
  {
    term: 'Enhanced Rock Weathering|ERW',
    definition:
      'A carbon removal technique that spreads finely crushed silicate minerals on land (often agricultural soil) to accelerate natural chemical reactions that convert atmospheric CO₂ into stable carbonates.',
    category: 'Project Type',
  },
  {
    term: 'Improved Cookstove|Clean Cookstoves',
    definition:
      'A project type that distributes fuel-efficient or clean-burning stoves to households in developing regions, reducing black carbon, GHG emissions, and indoor air pollution.',
    category: 'Project Type',
  },
  {
    term: 'Methane Avoidance',
    definition:
      'Projects that prevent methane from being released into the atmosphere — commonly from landfills, wastewater, or livestock manure — by capturing or destroying it.',
    category: 'Project Type',
  },
  {
    term: 'Renewable Energy',
    definition:
      'Carbon credit projects that displace fossil-fuel electricity generation by deploying wind, solar, hydro, or biomass energy sources, thereby reducing grid-level emissions.',
    category: 'Project Type',
  },
  {
    term: 'Soil Carbon',
    definition:
      'Projects that increase the amount of organic carbon stored in agricultural or degraded soils through practices like no-till farming, cover cropping, and regenerative grazing.',
    category: 'Project Type',
  },
  {
    term: 'Avoided Conversion',
    definition:
      'Projects that prevent the conversion of high-carbon-stock ecosystems (e.g., grasslands, peatlands, wetlands) into agriculture or other uses, avoiding the release of stored carbon.',
    category: 'Project Type',
  },
  {
    term: 'Landfill Gas Capture',
    definition:
      'Projects that collect and destroy or utilize methane generated by decomposing organic waste in landfills, preventing a potent greenhouse gas from reaching the atmosphere.',
    category: 'Project Type',
  },
  {
    term: 'Fuel Switching',
    definition:
      'Projects that reduce emissions by replacing a high-carbon fuel (e.g., coal) with a lower-carbon alternative (e.g., natural gas or biomass) in industrial or energy applications.',
    category: 'Project Type',
  },
  {
    term: 'Peatland Restoration',
    definition:
      'Projects that re-wet and rehabilitate drained peatlands to halt the oxidation of ancient organic carbon and restore their natural carbon sink function.',
    category: 'Project Type',
  },
  {
    term: 'Tidal Wetland Restoration',
    definition:
      'Projects that restore natural tidal flows to degraded coastal wetlands, re-establishing their capacity to sequester carbon in waterlogged, anaerobic soils.',
    category: 'Project Type',
  },
  {
    term: 'Ocean Alkalinity Enhancement',
    definition:
      'A marine carbon removal approach that adds alkaline substances to seawater to increase its capacity to absorb and permanently store atmospheric CO₂.',
    category: 'Project Type',
  },
  {
    term: 'Industrial Gas Destruction',
    definition:
      'Projects that capture and destroy potent industrial greenhouse gases — such as HFC-23, N₂O, or SF₆ — which have global warming potentials thousands of times greater than CO₂.',
    category: 'Project Type',
  },
  {
    term: 'Nature-based Solutions|NbS',
    definition:
      'Carbon credit projects that harness natural ecosystems — forests, wetlands, soils, oceans — to sequester or avoid releasing CO₂, while delivering biodiversity and livelihood co-benefits.',
    category: 'Project Type',
  },
  {
    term: 'Technology-based Removal',
    definition:
      'Carbon removal approaches that rely on engineered systems rather than natural ecosystems, including DAC, BECCS, biochar, and enhanced rock weathering.',
    category: 'Project Type',
  },
  {
    term: 'Carbon Dioxide Removal|CDR',
    definition:
      'Carbon Dioxide Removal — any human-driven activity that removes CO₂ from the atmosphere and durably stores it in geological, terrestrial, or ocean reservoirs, or in products.',
    category: 'Project Type',
  },
  {
    term: 'Jurisdictional REDD+|J-REDD+',
    definition:
      'A government-led approach to REDD+ that accounts for forest emissions and removals at the national or subnational level, rather than on a project-by-project basis.',
    category: 'Project Type',
  },
  {
    term: 'Agroforestry',
    definition:
      'A land management practice — and carbon project type — that integrates trees into agricultural landscapes, sequestering carbon while enhancing crop yields, biodiversity, and soil health.',
    category: 'Project Type',
  },

  // ── Market Mechanics ────────────────────────────────────────────────
  {
    term: 'Vintage',
    definition:
      'The calendar year in which the emission reduction or removal occurred. Older vintages typically trade at lower prices due to evolving quality standards.',
    category: 'Market',
  },
  {
    term: 'Retirement',
    definition:
      'The permanent cancellation of a carbon credit to claim the associated emission reduction. Once retired, a credit cannot be resold or transferred.',
    category: 'Market',
  },
  {
    term: 'Issuance',
    definition:
      'The creation of carbon credits by a registry after verification that emission reductions have occurred. Each issued credit represents one tonne of CO₂e.',
    category: 'Market',
  },
  {
    term: 'Buffer Pool',
    definition:
      'A reserve of credits set aside by a project to cover potential reversals of carbon sequestration (e.g., from wildfires or disease), ensuring permanence.',
    category: 'Market',
  },
  {
    term: 'OTC',
    definition:
      'Over-the-Counter — bilateral carbon credit transactions negotiated directly between buyer and seller, outside of a formal exchange, allowing bespoke terms on volume, price, and vintage.',
    category: 'Market',
  },
  {
    term: 'Spot Market',
    definition:
      'A marketplace where carbon credits are bought and sold for immediate delivery, with settlement typically occurring within a few business days.',
    category: 'Market',
  },
  {
    term: 'Forward Contract',
    definition:
      'An agreement to buy or sell a specified quantity of carbon credits at a set price on a future date, commonly used to lock in supply from projects still generating credits.',
    category: 'Market',
  },
  {
    term: 'Ex-ante Credit',
    definition:
      'A carbon credit issued before the emission reduction or removal has actually occurred, based on projected future performance — carries higher delivery and quality risk.',
    category: 'Market',
  },
  {
    term: 'Ex-post Credit',
    definition:
      'A carbon credit issued after an emission reduction or removal has been verified to have already occurred, providing greater certainty of environmental integrity.',
    category: 'Market',
  },
  {
    term: 'Price Discovery',
    definition:
      'The process by which the market determines the fair price of a carbon credit through the interaction of supply, demand, quality attributes, and available information.',
    category: 'Market',
  },
  {
    term: 'Tokenization',
    definition:
      'The process of representing a carbon credit as a digital token on a blockchain, aiming to improve transparency, traceability, and fractional ownership in carbon markets.',
    category: 'Market',
  },
  {
    term: 'dMRV',
    definition:
      'Digital Measurement, Reporting, and Verification — the use of remote sensing, IoT devices, and automated data pipelines to monitor and verify emission reductions with reduced human intervention.',
    category: 'Market',
  },
  {
    term: 'Serialization',
    definition:
      'The assignment of a unique serial number to each carbon credit by its registry, enabling tracking from issuance through transfer to final retirement.',
    category: 'Market',
  },
  {
    term: 'Registry Transfer',
    definition:
      'The movement of carbon credits from one account holder to another within a registry system, recording a change of ownership without retirement.',
    category: 'Market',
  },
  {
    term: 'Compliance Market',
    definition:
      'A regulated carbon market created by mandatory government policies (e.g., cap-and-trade systems like the EU ETS) — distinct from the voluntary carbon market.',
    category: 'Market',
  },
  {
    term: 'Carbon Exchange',
    definition:
      'A formal trading platform where standardized carbon credit contracts are listed, matched, and settled — examples include CBL (Xpansiv) and AirCarbon Exchange.',
    category: 'Market',
  },
  {
    term: 'Offtake Agreement',
    definition:
      'A long-term contractual commitment by a buyer to purchase a defined volume of carbon credits from a project over a specified period, providing revenue certainty to the developer.',
    category: 'Market',
  },
  {
    term: 'Bid-Ask Spread',
    definition:
      'The difference between the highest price a buyer is willing to pay and the lowest price a seller is willing to accept for a carbon credit — a measure of market liquidity.',
    category: 'Market',
  },
  {
    term: 'Market Liquidity',
    definition:
      'The ease with which carbon credits can be bought or sold without causing significant price changes — higher liquidity typically means tighter bid-ask spreads and faster transactions.',
    category: 'Market',
  },

  // ── Methodologies ───────────────────────────────────────────────────
  {
    term: 'VM0042',
    definition:
      'A Verra methodology for quantifying GHG emission reductions from improved agricultural land management practices, such as reduced tillage or cover cropping.',
    category: 'Methodology',
  },
  {
    term: 'VM0048',
    definition:
      'A Verra methodology for reducing emissions from deforestation and degradation, covering both planned and unplanned deforestation scenarios.',
    category: 'Methodology',
  },
  {
    term: 'AMS-III.D',
    definition:
      'A small-scale CDM methodology for methane recovery in animal waste management systems, commonly used for biodigester projects.',
    category: 'Methodology',
  },
  {
    term: 'VM0007',
    definition:
      'A Verra REDD+ methodology for quantifying emission reductions from avoided unplanned deforestation, one of the most widely used forestry methodologies in the VCM.',
    category: 'Methodology',
  },
  {
    term: 'VM0009',
    definition:
      'A Verra methodology for avoided ecosystem conversion, applicable to projects that prevent the conversion of non-forest ecosystems such as grasslands and shrublands.',
    category: 'Methodology',
  },
  {
    term: 'VM0015',
    definition:
      'A Verra methodology for avoided unplanned deforestation, previously among the most commonly applied REDD+ methodologies before consolidation into VM0048.',
    category: 'Methodology',
  },
  {
    term: 'ACM0001',
    definition:
      'A CDM consolidated methodology for landfill gas capture and flaring or energy generation projects, widely used in methane avoidance crediting.',
    category: 'Methodology',
  },
  {
    term: 'ACM0002',
    definition:
      'A consolidated methodology for grid-connected electricity generation from renewable sources, widely used for wind, hydro, and solar projects.',
    category: 'Methodology',
  },
  {
    term: 'Methodology',
    definition:
      'A documented set of rules and procedures approved by a carbon standard for quantifying the GHG emission reductions or removals of a specific project type.',
    category: 'Methodology',
  },
  {
    term: 'Dynamic Baseline',
    definition:
      'A baseline that is periodically updated during the crediting period to reflect changing conditions (e.g., deforestation trends, grid emission factors), improving accuracy over a fixed baseline.',
    category: 'Methodology',
  },
  {
    term: 'Performance Benchmark',
    definition:
      'A standardized threshold of GHG intensity (e.g., tCO₂e per MWh) that a project must outperform to demonstrate additionality under certain methodological approaches.',
    category: 'Methodology',
  },

  // ── Crediting & Units ───────────────────────────────────────────────
  {
    term: 'Verified Carbon Unit|VCU',
    definition:
      'Verified Carbon Unit — Verra\'s tradeable credit unit, representing one metric tonne of CO₂ equivalent reduced or removed from the atmosphere.',
    category: 'Credit Type',
  },
  {
    term: 'Certified Emission Reduction|CER',
    definition:
      'Certified Emission Reduction — a credit issued under the Clean Development Mechanism (CDM) of the Kyoto Protocol, representing one tonne of CO₂e.',
    category: 'Credit Type',
  },
  {
    term: 'tCO₂e',
    definition:
      'Tonnes of carbon dioxide equivalent — the standard unit for measuring greenhouse gas emissions, normalised to the global warming potential of CO₂.',
    category: 'Unit',
  },
  {
    term: 'Verified Emission Reduction|VER',
    definition:
      'Verified Emission Reduction — a generic term for a carbon credit issued in the voluntary market representing one tonne of CO₂e reduced or removed.',
    category: 'Credit Type',
  },
  {
    term: 'Gold Standard Verified Emission Reduction|GS VER',
    definition:
      'Gold Standard Verified Emission Reduction — a carbon credit issued under the Gold Standard, representing one tonne of CO₂e with verified sustainable development co-benefits.',
    category: 'Credit Type',
  },
  {
    term: 'Emission Reduction Tonne|ERT',
    definition:
      'Emission Reduction Tonne — the credit unit issued by the American Carbon Registry (ACR), each representing one metric tonne of CO₂e.',
    category: 'Credit Type',
  },
  {
    term: 'Climate Reserve Tonne|CRT',
    definition:
      'Climate Reserve Tonne — the credit unit issued by the Climate Action Reserve, each representing one metric tonne of CO₂e reduced or sequestered.',
    category: 'Credit Type',
  },
  {
    term: 'CO₂ Removal Certificate|CORC',
    definition:
      'CO₂ Removal Certificate — a credit issued by Puro.earth for verified engineered carbon removals, such as biochar or direct air capture with storage.',
    category: 'Credit Type',
  },
  {
    term: 'Internationally Transferred Mitigation Outcome|ITMO',
    definition:
      'Internationally Transferred Mitigation Outcome — a unit under Article 6.2 of the Paris Agreement representing transferred emission reductions between countries, requiring a corresponding adjustment.',
    category: 'Credit Type',
  },
  {
    term: 'Article 6.4 Emission Reduction|A6.4ER',
    definition:
      'Article 6.4 Emission Reduction — a credit issued under the Paris Agreement\'s Article 6.4 supervisory body, intended to succeed the CDM as the UN-backed crediting mechanism.',
    category: 'Credit Type',
  },
  {
    term: 'Emission Reduction Unit|ERU',
    definition:
      'Emission Reduction Unit — a credit issued under the Kyoto Protocol\'s Joint Implementation mechanism, representing one tonne of CO₂e reduced in an industrialized country.',
    category: 'Credit Type',
  },
  {
    term: 'Renewable Energy Certificate|REC',
    definition:
      'Renewable Energy Certificate — a market-based instrument representing the environmental attributes of 1 MWh of renewable electricity; distinct from a carbon credit but sometimes confused with one.',
    category: 'Credit Type',
  },
  {
    term: 'Biodiversity Credit',
    definition:
      'An emerging unit representing a measured, verified improvement in biodiversity — sometimes generated alongside carbon credits but representing a separate environmental outcome.',
    category: 'Credit Type',
  },

  // ── Integrity ───────────────────────────────────────────────────────
  {
    term: 'ICVCM',
    definition:
      'Integrity Council for the Voluntary Carbon Market — an independent governance body that sets and enforces quality benchmarks (Core Carbon Principles) for carbon credits.',
    category: 'Governance',
  },
  {
    term: 'VCMI',
    definition:
      'Voluntary Carbon Markets Integrity Initiative — provides guidance on credible use of carbon credits by companies making climate claims.',
    category: 'Governance',
  },
  {
    term: 'Core Carbon Principles',
    definition:
      'A set of quality criteria established by the ICVCM that define what constitutes a high-integrity carbon credit, including additionality, permanence, and robust MRV.',
    category: 'Governance',
  },
  {
    term: 'Science Based Targets initiative|SBTi',
    definition:
      'Science Based Targets initiative — a partnership that helps companies set GHG reduction targets aligned with the Paris Agreement, and provides guidance on the role of carbon credits beyond the value chain.',
    category: 'Governance',
  },
  {
    term: 'International Carbon Reduction and Offsetting Alliance|ICROA',
    definition:
      'International Carbon Reduction and Offsetting Alliance — an industry body that sets a code of best practice for carbon credit providers and promotes high-quality offsetting.',
    category: 'Governance',
  },
  {
    term: 'Taskforce on Scaling Voluntary Carbon Markets|TSVCM',
    definition:
      'Taskforce on Scaling Voluntary Carbon Markets — a private-sector initiative (now succeeded by the ICVCM) that produced recommendations for building a large-scale, transparent, and high-integrity VCM.',
    category: 'Governance',
  },
  {
    term: 'Validation and Verification Body|VVB',
    definition:
      'Validation and Verification Body — an independent, accredited auditor that assesses whether a carbon project\'s design meets a standard\'s requirements (validation) and confirms claimed emission reductions (verification).',
    category: 'Governance',
  },
  {
    term: 'Validation',
    definition:
      'The independent assessment of a project\'s design and documentation against a carbon standard\'s requirements before credits are issued — confirms the project is eligible and sound.',
    category: 'Governance',
  },
  {
    term: 'Verification',
    definition:
      'The independent, periodic audit of a project\'s monitored data and emission reduction claims by a VVB, required before a registry will issue carbon credits.',
    category: 'Governance',
  },
  {
    term: 'Third-party Audit',
    definition:
      'An independent review conducted by a VVB to assess a project\'s compliance with its methodology, monitoring plan, and the requirements of its certifying standard.',
    category: 'Governance',
  },
  {
    term: 'Accreditation',
    definition:
      'The formal recognition by a carbon standard that a VVB is qualified to perform validation and verification audits for specific project types or sectors.',
    category: 'Governance',
  },
  {
    term: 'Due Diligence',
    definition:
      'The process of investigating and evaluating a carbon credit or project before purchase, covering legal title, methodology, additionality, MRV quality, and reputational risk.',
    category: 'Governance',
  },
  {
    term: 'Greenwashing',
    definition:
      'Misleading claims by a company about its environmental performance or the climate impact of the carbon credits it purchases, eroding market trust and potentially violating regulations.',
    category: 'Governance',
  },

  // ── Policy & Paris Agreement ──────────────────────────────────────────
  {
    term: 'Article 6',
    definition:
      'The section of the Paris Agreement that establishes cooperative mechanisms for international carbon trading, including bilateral transfers (6.2) and a centralized crediting mechanism (6.4).',
    category: 'Policy',
  },
  {
    term: 'NDC',
    definition:
      'Nationally Determined Contribution — a country\'s self-defined climate plan under the Paris Agreement, outlining its emission reduction targets and adaptation strategies.',
    category: 'Policy',
  },
  {
    term: 'Host Country Approval',
    definition:
      'A formal authorization from the country where a carbon project is located, often required under Article 6 for the project to issue internationally transferable credits.',
    category: 'Policy',
  },
  {
    term: 'Letter of Authorization',
    definition:
      'A government-issued document confirming that the host country authorizes a project to generate carbon credits that may be used internationally, and committing to apply corresponding adjustments.',
    category: 'Policy',
  },
  {
    term: 'Paris Agreement',
    definition:
      'The 2015 international climate treaty committing signatory nations to limit global warming to well below 2 °C (ideally 1.5 °C) above pre-industrial levels, with provisions for market-based cooperation under Article 6.',
    category: 'Policy',
  },
  {
    term: 'Nested Approach',
    definition:
      'A framework for integrating project-level REDD+ activities within a broader jurisdictional accounting system, preventing double counting and aligning incentives between local projects and national programs.',
    category: 'Policy',
  },
  {
    term: 'EU ETS',
    definition:
      'European Union Emissions Trading System — the world\'s largest compliance carbon market, operating as a cap-and-trade system across EU member states.',
    category: 'Policy',
  },
  {
    term: 'Cap-and-Trade',
    definition:
      'A regulatory approach that sets a declining ceiling on total emissions and allows companies to buy and sell emission allowances, creating a market-based incentive to reduce GHG output.',
    category: 'Policy',
  },
  {
    term: 'Carbon Tax',
    definition:
      'A government-imposed price per tonne of CO₂e emitted, designed to internalize the social cost of carbon and incentivize emission reductions without creating a tradeable allowance market.',
    category: 'Policy',
  },

  // ── Climate Claims & Corporate Action ─────────────────────────────────
  {
    term: 'Net Zero',
    definition:
      'A state in which an entity\'s residual greenhouse gas emissions are fully balanced by an equivalent quantity of verified carbon removals, achieved after deep decarbonization of direct and value-chain emissions.',
    category: 'Climate Claim',
  },
  {
    term: 'Carbon Neutral',
    definition:
      'A claim that an entity has compensated for all of its measured CO₂ emissions — typically through a combination of reductions and offsets — resulting in no net addition of CO₂ to the atmosphere.',
    category: 'Climate Claim',
  },
  {
    term: 'Climate Positive',
    definition:
      'A claim that an entity removes more CO₂ from the atmosphere than it emits across its entire value chain, going beyond net zero.',
    category: 'Climate Claim',
  },
  {
    term: 'Beyond Value Chain Mitigation|BVCM',
    definition:
      'Investments in emission reductions or removals outside a company\'s own Scope 1, 2, and 3 footprint — the SBTi\'s recommended framing for corporate use of carbon credits.',
    category: 'Climate Claim',
  },
  {
    term: 'Contribution Claim',
    definition:
      'A corporate claim that a company is financially contributing to climate action through carbon credit purchases, without asserting that its own emissions have been fully "offset."',
    category: 'Climate Claim',
  },
  {
    term: 'Mitigation Hierarchy',
    definition:
      'The principle that companies should first avoid, then reduce their own emissions before compensating for any residual emissions through carbon credits.',
    category: 'Climate Claim',
  },
  {
    term: 'Residual Emissions',
    definition:
      'The GHG emissions that remain after a company has implemented all technically and economically feasible reduction measures — these are the emissions typically addressed with carbon removal credits in a net-zero strategy.',
    category: 'Climate Claim',
  },

  // ── Ratings & Quality ─────────────────────────────────────────────────
  {
    term: 'Carbon Credit Rating',
    definition:
      'An independent assessment of a carbon credit\'s quality and risk, provided by agencies such as BeZero Carbon, Calyx Global, or Sylvera, typically expressed as a letter grade.',
    category: 'Quality',
  },
  {
    term: 'BeZero Carbon',
    definition:
      'A carbon credit rating agency that evaluates the likelihood that a credit represents one tonne of real, additional, and permanent CO₂ avoidance or removal.',
    category: 'Quality',
  },
  {
    term: 'Sylvera',
    definition:
      'A carbon intelligence firm that uses satellite data and machine learning to rate the quality of carbon credits and provide risk assessments for buyers.',
    category: 'Quality',
  },
  {
    term: 'Calyx Global',
    definition:
      'A carbon credit rating agency that provides independent quality assessments across additionality, over-crediting risk, and permanence dimensions.',
    category: 'Quality',
  },

  // ── Remote Sensing & Technology ───────────────────────────────────────
  {
    term: 'Remote Sensing',
    definition:
      'The use of satellite or aerial imagery to monitor land-use change, forest cover, and carbon stocks for MRV purposes in nature-based carbon projects.',
    category: 'Technology',
  },
  {
    term: 'Light Detection and Ranging|LiDAR',
    definition:
      'Light Detection and Ranging — an airborne or satellite-based technology that uses laser pulses to create 3-D maps of forest canopy structure, enabling accurate estimation of above-ground biomass and carbon stocks.',
    category: 'Technology',
  },
  {
    term: 'Allometric Equation',
    definition:
      'A mathematical relationship used to estimate tree biomass and carbon content from easily measured variables like diameter at breast height (DBH) and tree height.',
    category: 'Technology',
  },
  {
    term: 'Internet of Things Sensor|IoT Sensor',
    definition:
      'An Internet of Things device deployed in carbon projects (e.g., soil moisture probes, methane detectors) to collect real-time environmental data for digital MRV.',
    category: 'Technology',
  },
  {
    term: 'Carbon Flux',
    definition:
      'The rate of exchange of CO₂ between the atmosphere and an ecosystem, measured to determine whether a project area is a net carbon source or sink.',
    category: 'Technology',
  },
  {
    term: 'Eddy Covariance',
    definition:
      'A micrometeorological technique that measures the exchange of CO₂, water vapor, and energy between an ecosystem and the atmosphere by sampling turbulent air flow at high frequency.',
    category: 'Technology',
  },

  // ── SDGs & Sustainability ─────────────────────────────────────────────
  {
    term: 'Sustainable Development Goals|SDGs',
    definition:
      'Sustainable Development Goals — the 17 global goals adopted by the United Nations in 2015, often used to classify and market the co-benefits of carbon projects.',
    category: 'Sustainability',
  },
  {
    term: 'SDG Alignment',
    definition:
      'The mapping of a carbon project\'s co-benefits to specific UN Sustainable Development Goals, increasingly required by buyers seeking demonstrable social and environmental impact.',
    category: 'Sustainability',
  },
];

/**
 * Build a pre-sorted array for matching (longest term first) and
 * a case-insensitive lookup map. Computed once at module load.
 *
 * Terms with `|` separator (e.g., "Direct Air Capture|DAC") are split
 * into multiple entries so both forms can be matched independently.
 */
const _expanded: { term: string; entry: GlossaryEntry }[] = [];
VCM_GLOSSARY.forEach((entry) => {
  const variants = entry.term.split('|');
  variants.forEach((variant) => {
    const trimmed = variant.trim();
    if (trimmed.length > 0) {
      _expanded.push({ term: trimmed, entry });
    }
  });
});

const _sorted = _expanded.sort((a, b) => b.term.length - a.term.length);

/** Map from lower-cased term → GlossaryEntry for O(1) lookup. */
export const GLOSSARY_MAP = new Map<string, GlossaryEntry>(
  _sorted.map((item) => [item.term.toLowerCase(), item.entry]),
);

/**
 * Pre-compiled regex that matches any glossary term (longest-first,
 * case-insensitive, whole-word). The `u` flag ensures Unicode safety.
 */
export const GLOSSARY_REGEX = new RegExp(
  `(?<![\\p{L}\\p{N}_])(${_sorted.map((e) => e.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})(?![\\p{L}\\p{N}_])`,
  'giu',
);
