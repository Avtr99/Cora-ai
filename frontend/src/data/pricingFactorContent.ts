import type { BarTone, ForceId, TimelineForceId } from './pricingData';

export interface PricingSource {
  label: string;
  href: string;
}

/**
 * One bar in a price comparison. `tone` is the bar's semantic role - the chart
 * maps it to a palette color, so data carries meaning and color stays in the
 * component. A datum without a tone cannot be constructed.
 */
export interface PriceBarDatum {
  label: string;
  value: number;
  displayValue: string;
  tone: BarTone;
}

export interface PriceComparisonDatum extends PriceBarDatum {
  description: string;
  examples: string;
}

/**
 * A methodology reference: registry code + display name. The single shape used
 * anywhere a methodology is listed, so renderers never re-parse display strings.
 */
export interface MethodologyRef {
  code: string;
  name: string;
}

/**
 * CCP assessment outcome for a methodology version. Drives the status grouping
 * on the Integrity tab - the label and tone are derived from this, never stored
 * as display strings, so a status can never render without its group.
 */
export type MethodologyStatus = 'approved' | 'conditional';

export interface MethodologyDecision extends MethodologyRef {
  status: MethodologyStatus;
  note?: string;
}

/**
 * A headline figure with a delta, rendered as a tinted companion panel under a
 * chart (traded volume on Integrity, SDG premium on Vintage).
 */
export interface DeltaStat {
  label: string;
  value: string;
  unit: string;
  delta: string;
  deltaLabel: string;
}

/**
 * Semantic status for a lane or status line. Components map it to the semantic
 * success/warning palette, so a status can never render without its color.
 */
export type StatusTone = 'success' | 'warning';

export interface ClaimsLane {
  title: string;
  status: string;
  tone: StatusTone;
  flow: { from: string; to: string };
  demand: string;
  methodologies: MethodologyRef[];
}

export const MARKET_SOURCES: PricingSource[] = [
  {
    label: 'Ecosystem Marketplace, State of the VCM 2025',
    href: 'https://www.ecosystemmarketplace.com/publications/2025-state-of-the-voluntary-carbon-market-sovcm/',
  },
];

export const INTEGRITY_SOURCES: PricingSource[] = [
  ...MARKET_SOURCES,
  {
    label: 'ICVCM methodology assessment status',
    href: 'https://icvcm.org/assessment-status/',
  },
];

export const CLAIMS_SOURCES: PricingSource[] = [
  {
    label: 'SBTi Corporate Net-Zero Standard V2.0, Chapter 6',
    href: 'https://standards.sciencebasedtargets.org/chapter/6-ongoing-emissions-responsibility',
  },
  {
    label: 'ICVCM methodology assessment status',
    href: 'https://icvcm.org/assessment-status/',
  },
];

export const COMPLIANCE_SOURCES: PricingSource[] = [
  {
    label: 'ICAO, CORSIA Eligible Emissions Units',
    href: 'https://www.icao.int/CORSIA/corsia-eligible-emissions-units',
  },
  ...MARKET_SOURCES,
];

export const FACTOR_INTRO: Record<ForceId, string> = {
  type: 'Removal credits averaged $19.50 versus $4.05 for reduction credits in 2024.',
  integrity: 'Methodology approval can change buyer confidence and market access.',
  claims: 'SBTi gives removals and avoidance credits different roles in corporate climate action.',
  compliance: 'Article 6 authorization opens a credit to compliance buyers like CORSIA airlines. Without it, the credit competes for voluntary demand only.',
  vintage: 'Recent vintages averaged $9.31 versus $2.94 for older credits in 2024.',
};

/**
 * Headline takeaway per factor, shown in the page hero next to the title.
 * All values render at the same compact size (section-heading scale) so the
 * hero hierarchy stays consistent across tabs - including date values like
 * Jan 2028, where display size would read as a calendar label.
 */
export const FORCE_HEADLINE_STAT: Record<ForceId, { value: string; caption: string }> = {
  type: { value: '381%', caption: 'premium for removals over reductions' },
  integrity: { value: '+35%', caption: 'landfill-gas price lift after CCP approval' },
  claims: { value: '100%', caption: 'of residual emissions must use removals at net-zero' },
  compliance: { value: 'Jan 2028', caption: 'first-phase CORSIA units must be cancelled by this date' },
  vintage: { value: '217%', caption: 'premium for credits from the previous five years' },
};

export const RELATED_FACTORS: Record<ForceId, { id: ForceId; text: string; label: string }> = {
  type: {
    id: 'claims',
    text: 'Claim rules create required demand for eligible removals.',
    label: 'See claim eligibility',
  },
  integrity: {
    id: 'vintage',
    text: 'New methodology versions often create a cutoff between older and newer supply.',
    label: 'See vintage',
  },
  claims: {
    id: 'type',
    text: 'Required removal demand helps explain the removal premium.',
    label: 'See removal vs avoidance',
  },
  compliance: {
    id: 'integrity',
    text: 'Article 6 authorization and the CCP label are separate screens. A credit can hold one without the other.',
    label: 'See integrity',
  },
  vintage: {
    id: 'integrity',
    text: 'Recent vintages often use newer methodology versions.',
    label: 'See integrity',
  },
};

/**
 * Screen-reader text and footnote for the milestone timelines. Keyed by the
 * same TimelineForceId union the component accepts, so copy and data stay
 * attached to the factor they describe.
 */
export interface TimelineCopy {
  ariaLabel: string;
  note: string;
}

export const TIMELINE_COPY: Record<TimelineForceId, TimelineCopy> = {
  claims: {
    ariaLabel:
      'SBTi V2.0 timeline: V1.3.1 in 2024, removals required for net-zero from January 2027, and the 1 percent removal mandate beginning in 2035',
    note: 'Removal demand applies at each company’s net-zero year - not automatically in 2027.',
  },
  compliance: {
    ariaLabel:
      'CORSIA timeline: first phase begins in 2024, first-phase units must be cancelled by January 2028, and the second phase ends in 2035',
    note: 'Not every Article 6-authorized credit qualifies: CORSIA also requires an ICAO-approved programme and an activity start of 2016 or later.',
  },
};

/**
 * Insight-card copy for the chart-plus-card factors. `id` keys the icon map in
 * the panel component, so a missing icon is a compile error, not a blank spot.
 */
export interface FactorInsight<Id extends string> {
  id: Id;
  title: string;
  body: string;
}

export type TypeInsightId = 'supply' | 'demand' | 'durability';
export type VintageInsightId = 'reporting' | 'methodology' | 'quality';

export const TYPE_PRICE_COMPARISON: PriceComparisonDatum[] = [
  {
    label: 'Reduction / avoidance',
    value: 4.05,
    displayValue: '$4.05',
    tone: 'reduction',
    description: 'Prevents or reduces emissions against a baseline.',
    examples: 'REDD+, renewable energy',
  },
  {
    label: 'Removal (all)',
    value: 19.5,
    displayValue: '$19.50',
    tone: 'removal',
    description: 'Removes carbon from the atmosphere and stores it.',
    examples: 'ARR, mangrove restoration, agroforestry',
  },
  {
    label: 'Engineered removal',
    value: 160,
    displayValue: '$160+',
    tone: 'removal',
    description: 'Durable storage at small scale.',
    examples: 'Biochar',
  },
];

export const TYPE_INSIGHTS: FactorInsight<TypeInsightId>[] = [
  { id: 'supply', title: 'Scarce supply', body: 'Removals were only 5% of traded volume in 2024.' },
  { id: 'demand', title: 'Focused buyer demand', body: 'Average removal prices rose 13% as supply lagged demand in 2024.' },
  {
    id: 'durability',
    title: 'Durability premium',
    body: 'ARR supplied 99% of traded removals. Engineered removals with long-term storage cost about ten times more.',
  },
];

export const VINTAGE_PRICE_COMPARISON: PriceComparisonDatum[] = [
  {
    label: 'Older than five years',
    value: 2.94,
    displayValue: '$2.94',
    tone: 'neutral',
    description: 'Average price fell 43% in 2024.',
    examples: 'More exposure to legacy supply',
  },
  {
    label: 'Within five years',
    value: 9.31,
    displayValue: '$9.31',
    tone: 'removal',
    description: 'Average price rose 17% in 2024.',
    examples: 'Closer reporting-year match',
  },
];

export const VINTAGE_INSIGHTS: FactorInsight<VintageInsightId>[] = [
  {
    id: 'reporting',
    title: 'Reporting-year match',
    body: 'Buyers often align vintage with the emissions year they are addressing.',
  },
  {
    id: 'methodology',
    title: 'Newer methodology versions',
    body: 'Recent credits are less likely to rely on methods that have since been replaced.',
  },
  {
    id: 'quality',
    title: 'Not a quality grade',
    body: 'Vintage alone does not establish integrity. Project quality still matters.',
  },
];

/**
 * Landfill-gas price level before/after CCP approval (July 2024). `value` is a
 * relative level where 100 = baseline, so bar widths are derived by the chart,
 * not stored as presentation data.
 */
export const INTEGRITY_PRICE_BARS: PriceBarDatum[] = [
  { label: 'Before CCP', value: 100, displayValue: 'Baseline', tone: 'neutral' },
  { label: 'After CCP', value: 135, displayValue: '+35%', tone: 'removal' },
];

export const INTEGRITY_CHART_ARIA_LABEL =
  'Landfill gas average price increased 35 percent after CCP approval in July 2024';

export const INTEGRITY_VERSION_NOTE =
  'Approval is version-specific. A methodology decision does not automatically label every credit.';

export const INTEGRITY_METHODS: MethodologyDecision[] = [
  { code: 'VM0044 v1.2', name: 'Biochar', status: 'approved' },
  { code: 'VM0047 v1.1', name: 'ARR', status: 'approved' },
  {
    code: 'VM0048 v1.0',
    name: 'REDD+',
    status: 'conditional',
    note: 'Only qualifying activities using VMD0055 v1.1.',
  },
  {
    code: 'VMR0017 v1.0',
    name: 'Renewable energy',
    status: 'conditional',
    note: 'Requires the specified financial additionality test.',
  },
];

/**
 * Landfill Gas only - the source reports 3.1M tons traded for that project
 * type, not the market total.
 */
export const INTEGRITY_VOLUME: DeltaStat = {
  label: 'Traded volume',
  value: '3.1M',
  unit: 'credits in 2024',
  delta: '+149%',
  deltaLabel: 'vs 2023',
};

/**
 * EM SOVCM 2025: "the premium for credits with at least one SDG certification
 * grew to 71 percent, compared to 29 percent the year before."
 */
export const VINTAGE_SDG_PREMIUM: DeltaStat = {
  label: 'SDG co-benefit premium',
  value: '71%',
  unit: 'average premium fetched by credits with a certified SDG vs those without, 2024',
  delta: 'up from 29%',
  deltaLabel: 'in 2023',
};

export const CLAIMS_LANES_INTRO =
  'Only eligible removals neutralize residual emissions. Avoidance credits remain a voluntary contribution.';

export const CLAIMS_LANES: ClaimsLane[] = [
  {
    title: 'Removal credits',
    status: 'Required for net-zero',
    tone: 'success',
    flow: { from: 'Residual emissions', to: 'Eligible removals' },
    demand: 'Required for 100% of residual emissions at the company’s net-zero year.',
    methodologies: [
      { code: 'VM0044', name: 'Biochar' },
      { code: 'VM0047', name: 'ARR' },
    ],
  },
  {
    title: 'Avoidance / reduction credits',
    status: 'Not for net-zero',
    tone: 'warning',
    flow: { from: 'Ongoing emissions', to: 'OER contribution' },
    demand: 'Not eligible for net-zero neutralization - counts as a voluntary contribution under the OER program.',
    methodologies: [
      { code: 'VM0048', name: 'REDD+' },
      { code: 'VMR0017', name: 'Renewable energy' },
    ],
  },
];

export interface BuyerPool {
  title: string;
  status: string;
  tone: StatusTone;
  buyers: string[];
  body: string;
}

export const COMPLIANCE_BUYER_POOLS: BuyerPool[] = [
  {
    title: 'Article 6-authorized',
    status: 'Compliance and voluntary demand',
    tone: 'success',
    buyers: ['Airlines under CORSIA', 'Governments buying toward their targets', 'Voluntary buyers'],
    body: 'Host-country authorization under Article 6 adds a buyer pool the voluntary market does not have.',
  },
  {
    title: 'Not authorized',
    status: 'Voluntary demand only',
    tone: 'warning',
    buyers: ['Voluntary buyers'],
    body: 'The same tonne from the same project, without the compliance bid.',
  },
];

export interface PriceOutlook {
  trend: 'rising' | 'declining';
  badge: string;
  title: string;
  body: string;
}

export const CLAIMS_PRICE_OUTLOOK: PriceOutlook[] = [
  {
    trend: 'rising',
    badge: 'Removal credits',
    title: 'Required demand supports prices',
    body: 'Net-zero rules require removal credits, which gives eligible removals a steady demand floor.',
  },
  {
    trend: 'declining',
    badge: 'Avoidance credits',
    title: 'Voluntary demand limits price support',
    body: 'Avoidance credits do not count toward net-zero claims, so they have less price support.',
  },
];

export const COMPLIANCE_PRICE_OUTLOOK: PriceOutlook[] = [
  {
    trend: 'rising',
    badge: 'Article 6-authorized',
    title: 'Scarce supply meets a hard deadline',
    body: 'Airlines must cancel eligible units for the 2024–2026 CORSIA phase, while Article 6 authorization is optional for host countries and granted project by project.',
  },
  {
    trend: 'declining',
    badge: 'Not authorized',
    title: 'No compliance bid',
    body: 'Without authorization a credit competes only for voluntary demand, so compliance scarcity does not lift its price.',
  },
];
