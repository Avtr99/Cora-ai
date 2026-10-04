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
  /** Year-on-year change in percent, rendered as a chip next to the price. */
  change?: number;
  /** Open-ended value: the ratio caption is a floor and carries a `+`. */
  open?: boolean;
}

/**
 * One column of a vertical bar chart: a relative value the chart scales to the
 * tallest column, plus the label above the bar. A divider column marks a
 * labelled event between two bars instead of a value.
 */
export type VerticalBarStep =
  | {
      kind: 'bar';
      label: string;
      value: number;
      tone: BarTone;
      /** Text shown above the bar (a value or `Baseline`). */
      top?: string;
      /** Small colored suffix after `top`, e.g. `+149%`. */
      delta?: string;
      /** Muted styling for the reference column. */
      mutedTop?: boolean;
    }
  | { kind: 'divider'; text: string };

/**
 * One row of a mini horizontal bar chart: label, optional sub-label and tag,
 * a relative value and the number printed at the end of the track.
 */
export interface MiniBarRow {
  key: string;
  sub?: string;
  tag?: string;
  value: number;
  display: string;
  tone: BarTone;
}

/** A 100-cell waffle: `on` cells are colored, the rest are the hairline tint. */
export interface WaffleVis {
  on: number;
  total: number;
  caption: Caption;
}

/** Bolded lead-in for a visual caption: `lead` + `strong` + `tail`. */
export interface Caption {
  lead?: string;
  strong?: string;
  tail?: string;
}

/**
 * A methodology reference: registry code + display name. The single shape used
 * anywhere a methodology is listed, so renderers never re-parse display strings.
 */
export interface MethodologyRef {
  code: string;
  name: string;
}

/** Removal or reduction family, used for the dot that labels each method. */
export type MethodologyKind = 'removal' | 'reduction';

/**
 * CCP assessment outcome for a methodology version. Drives the status grouping
 * on the Integrity tab - the label and tone are derived from this, never stored
 * as display strings, so a status can never render without its group.
 */
export type MethodologyStatus = 'approved' | 'conditional';

export interface MethodologyDecision extends MethodologyRef {
  kind: MethodologyKind;
  status: MethodologyStatus;
  note?: string;
}

/**
 * Semantic status for a claim flow sink. Components map it to the semantic
 * success/warning palette, so a status can never render without its color.
 */
export type StatusTone = 'success' | 'warning';

/** Where a credit can be used at net-zero: neutralize, or contribute only. */
export type FlowSinkId = 'neutral' | 'oer';

/** Icon id for a flow source card; the component maps it to a lucide icon. */
export type FlowIconId = 'flame' | 'sprout' | 'trees' | 'zap';

export interface FlowSource {
  code: string;
  type: string;
  icon: FlowIconId;
  to: FlowSinkId;
  /** Trace text shown when the source is hovered or selected. */
  message: { lead: string; body: string };
}

export interface FlowSink {
  id: FlowSinkId;
  tone: StatusTone;
  status: string;
  title: string;
  body: string;
}

export interface ClaimFlow {
  intro: string;
  sources: FlowSource[];
  sinks: FlowSink[];
  /** Copy shown before any source is traced. */
  resting: string;
}

/** Icon id for a buyer pool row; the component maps it to a lucide icon. */
export type StairIconId = 'plane' | 'landmark' | 'building';

export interface StairPool {
  icon: StairIconId;
  name: string;
  sub: string;
  /** Requirement indices this pool needs before it can bid. */
  needs: number[];
}

export interface StairLevel {
  name: string;
  /** Requirement chip shown above the level name. */
  gate: string;
  /** Set when the gate starts with a `+` glyph. */
  gateIcon?: boolean;
  /** Rule read out when the column is selected. */
  sub: string;
  /** Requirement indices met at this level. */
  met: number[];
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

/** Caveat shown in every factor panel footer, next to the source links. */
export const PRICE_YEAR_NOTE = 'Prices shown are 2024 transaction averages.';

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
 * Screen-reader text for the milestone timelines, and the footnote shown under
 * the SBTi rollout timeline. Keyed by the same TimelineForceId union the
 * component accepts, so copy and data stay attached to the factor they
 * describe.
 */
export interface TimelineCopy {
  ariaLabel: string;
}

export const TIMELINE_COPY: Record<TimelineForceId, TimelineCopy> = {
  claims: {
    ariaLabel:
      'SBTi V2.0 timeline: V1.3.1 in 2024, removals required for net-zero from January 2027, and the 1 percent removal mandate beginning in 2035',
  },
  compliance: {
    ariaLabel:
      'CORSIA timeline: first phase begins in 2024, first-phase units must be cancelled by January 2028, and the second phase ends in 2035',
  },
};

export const CLAIMS_TIMELINE_NOTE =
  'Removal demand applies at each company\u2019s net-zero year - not automatically in 2027.';

/**
 * Insight-card copy for the evidence rows. `id` keys the icon/visual map in
 * the panel component, so a missing entry is a compile error, not a blank spot.
 */
export interface FactorInsight<Id extends string> {
  id: Id;
  title: string;
  body: string;
}

export type TypeInsightId = 'supply' | 'demand' | 'durability';
export type VintageInsightId = 'reporting' | 'methodology' | 'quality';

/* -------------------------------------------------------------------------- */
/* Removal vs avoidance                                                        */
/* -------------------------------------------------------------------------- */

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
    tone: 'removal-deep',
    description: 'Durable storage at small scale.',
    examples: 'Biochar',
    open: true,
  },
];

export const TYPE_PRICE_HINT =
  'Bars are drawn to scale. A biochar tonne costs about 40 reduction tonnes.';

export const TYPE_PRICE_AXIS = [0, 40, 80, 120, 160];

export const TYPE_PRICE_ARIA_LABEL =
  '2024 average price per tonne: reduction or avoidance $4.05, all removals $19.50, 4.8 times more, engineered removals $160 or more.';

export const TYPE_INSIGHTS: FactorInsight<TypeInsightId>[] = [
  {
    id: 'supply',
    title: 'Scarce supply',
    body: 'Removals were only 5% of traded volume in 2024.',
  },
  {
    id: 'demand',
    title: 'Focused buyer demand',
    body: 'Average removal prices rose 13% as supply lagged demand in 2024.',
  },
  {
    id: 'durability',
    title: 'Durability premium',
    body: 'Nature-based removals are the largest removal category. Engineered removals such as biochar trade in small volumes at $160+ per tonne, 8.2x the removal average.',
  },
];

export const TYPE_SUPPLY_WAFFLE: WaffleVis = {
  on: 5,
  total: 100,
  caption: { strong: '5 of every 100', tail: ' credits traded were removals.' },
};

export const TYPE_DEMAND_VIS: VerticalBarStep[] = [
  { kind: 'bar', label: '2023', value: 100, tone: 'neutral', mutedTop: true },
  { kind: 'bar', label: '2024', value: 113, tone: 'removal', top: '+13%' },
];

export const TYPE_DEMAND_CAPTION: Caption = {
  lead: 'Average removal price, ',
  strong: '$19.50',
  tail: ' in 2024.',
};

export const TYPE_DURABILITY_VIS: MiniBarRow[] = [
  {
    key: 'Nature-based',
    sub: 'ARR and others',
    tag: 'Largest supply',
    value: 19.5,
    display: '$19.50',
    tone: 'removal',
  },
  {
    key: 'Engineered',
    sub: 'Biochar',
    tag: 'Small volume',
    value: 160,
    display: '$160+',
    tone: 'removal-deep',
  },
];

export const TYPE_DURABILITY_CAPTION = 'ARR: afforestation, reforestation and revegetation.';

/* -------------------------------------------------------------------------- */
/* Integrity                                                                  */
/* -------------------------------------------------------------------------- */

export const INTEGRITY_BAND_SUB =
  'ICVCM approved landfill gas methodologies for the CCP label in July 2024. Price and traded volume both rose.';

export const INTEGRITY_PRICE_VIS: VerticalBarStep[] = [
  { kind: 'bar', label: 'Before', value: 100, tone: 'neutral', top: 'Baseline', mutedTop: true },
  { kind: 'divider', text: 'July 2024 \u00b7 CCP' },
  { kind: 'bar', label: 'After', value: 135, tone: 'removal', top: '+35%' },
];

export const INTEGRITY_CHART_ARIA_LABEL =
  'Landfill gas average price increased 35 percent after CCP approval in July 2024';

export const INTEGRITY_VOLUME_VIS: VerticalBarStep[] = [
  { kind: 'bar', label: '2023', value: 1, tone: 'neutral', mutedTop: true },
  { kind: 'bar', label: '2024', value: 2.49, tone: 'removal', top: '3.1M', delta: '+149%' },
];

export const INTEGRITY_VOLUME_ARIA_LABEL =
  'Landfill gas traded volume reached 3.1 million credits in 2024, up 149 percent from 2023';

export const INTEGRITY_VERSION_NOTE =
  'Approval is version-specific. A methodology decision does not automatically label every credit.';

export const INTEGRITY_METHODS: MethodologyDecision[] = [
  { code: 'VM0044 v1.2', name: 'Biochar', kind: 'removal', status: 'approved' },
  { code: 'VM0047 v1.1', name: 'ARR', kind: 'removal', status: 'approved' },
  {
    code: 'VM0048 v1.0',
    name: 'REDD+',
    kind: 'reduction',
    status: 'conditional',
    note: 'Only qualifying activities using VMD0055 v1.1.',
  },
  {
    code: 'VMR0017 v1.0',
    name: 'Renewable energy',
    kind: 'reduction',
    status: 'conditional',
    note: 'Requires the specified financial additionality test.',
  },
];

/**
 * EM SOVCM 2025: "the premium for credits with at least one SDG certification
 * grew to 71 percent, compared to 29 percent the year before."
 */
export const INTEGRITY_SDG = {
  headline: '71% premium',
  body: 'Credits with at least one certified SDG fetched 71% more on average than credits without, in 2024.',
  ariaLabel: 'SDG co-benefit premium: 29 percent in 2023, 71 percent in 2024',
  bars: [
    { key: '2023', value: 29, display: '29%', tone: 'neutral' as BarTone },
    { key: '2024', value: 71, display: '71%', tone: 'removal' as BarTone },
  ],
};

/* -------------------------------------------------------------------------- */
/* Claim eligibility (SBTi)                                                    */
/* -------------------------------------------------------------------------- */

export const NET_ZERO_CHART_LABEL =
  "Company emissions fall from the base year to a small residual at the company's net-zero year. Avoidance credits can support contribution claims along the way. From the net-zero year, removals plotted below zero cancel the residual emissions so the net is zero.";

export const NET_ZERO_BAND_SUB =
  'Company emissions fall from the base year to a small residual at your net-zero year. Hover or click a step below to highlight it on the chart.';

export const NET_ZERO_KEYS: Record<
  '1' | '2' | '3',
  { title: string; body: string; status?: { tone: StatusTone; label: string } }
> = {
  '1': {
    title: 'Abatement',
    body: 'Cut in your own value chain first. Credits do not replace this.',
  },
  '2': {
    title: 'Ongoing emissions',
    body: 'Avoidance credits address ongoing emissions as a voluntary contribution under OER.',
    status: { tone: 'warning', label: 'Not for net-zero' },
  },
  '3': {
    title: 'Residual emissions',
    body: 'Eligible removals must cover 100% of residual emissions from the net-zero year on.',
    status: { tone: 'success', label: 'Required for net-zero' },
  },
};

export const CLAIMS_FLOW_INTRO =
  'Only eligible removals neutralize residual emissions. Avoidance credits remain a voluntary contribution.';

export const CLAIMS_FLOW: ClaimFlow = {
  intro: CLAIMS_FLOW_INTRO,
  resting: 'Hover or select a credit to trace its claim.',
  sources: [
    {
      code: 'VM0044',
      type: 'Biochar',
      icon: 'flame',
      to: 'neutral',
      message: {
        lead: 'VM0044 Biochar',
        body: ' stores carbon removed from the atmosphere. Eligible removals like this can neutralize residual emissions at the net-zero year.',
      },
    },
    {
      code: 'VM0047',
      type: 'ARR',
      icon: 'sprout',
      to: 'neutral',
      message: {
        lead: 'VM0047 ARR',
        body: ' grows new forest that removes carbon. Eligible removals like this can neutralize residual emissions at the net-zero year.',
      },
    },
    {
      code: 'VM0048',
      type: 'REDD+',
      icon: 'trees',
      to: 'oer',
      message: {
        lead: 'VM0048 REDD+',
        body: ' avoids emissions from deforestation. It does not neutralize residual emissions. It counts as a voluntary contribution under OER.',
      },
    },
    {
      code: 'VMR0017',
      type: 'Renewable energy',
      icon: 'zap',
      to: 'oer',
      message: {
        lead: 'VMR0017 Renewable energy',
        body: ' displaces fossil generation. It does not neutralize residual emissions. It counts as a voluntary contribution under OER.',
      },
    },
  ],
  sinks: [
    {
      id: 'neutral',
      tone: 'success',
      status: 'Required for net-zero',
      title: 'Neutralize residual emissions',
      body: 'Residual emissions \u2192 eligible removals. Required for 100% of residual emissions at the net-zero year.',
    },
    {
      id: 'oer',
      tone: 'warning',
      status: 'Not for net-zero',
      title: 'OER contribution',
      body: 'Ongoing emissions \u2192 voluntary contribution. Not eligible for net-zero neutralization.',
    },
  ],
};

/* -------------------------------------------------------------------------- */
/* Article 6 authorization                                                     */
/* -------------------------------------------------------------------------- */

export const COMPLIANCE_STAIR_SUB =
  'Each step adds a requirement and a buyer pool. Select a column to read the rule.';

export const COMPLIANCE_STAIRCASE: { pools: StairPool[]; levels: StairLevel[] } = {
  pools: [
    {
      icon: 'plane',
      name: 'Airlines under CORSIA',
      sub: 'Compliance demand',
      needs: [0, 1, 2],
    },
    { icon: 'landmark', name: 'Governments', sub: 'Buying toward their targets', needs: [0] },
    { icon: 'building', name: 'Voluntary buyers', sub: 'Corporate climate claims', needs: [] },
  ],
  levels: [
    {
      name: 'Not authorized',
      gate: 'Starting point',
      sub: 'The same tonne from the same project, without the compliance bid.',
      met: [],
    },
    {
      name: 'Article 6-authorized',
      gate: 'Host-country authorization',
      gateIcon: true,
      sub: 'The host country authorizes the credit. Governments can now count it toward their targets.',
      met: [0],
    },
    {
      name: 'CORSIA-eligible',
      gate: 'ICAO programme, 2016+ start',
      gateIcon: true,
      sub: 'Authorized, issued under an ICAO-approved programme, from an activity that started in 2016 or later.',
      met: [0, 1, 2],
    },
  ],
};

/** Copy for the cancellation deadline note under the CORSIA timeline. */
export const CORSIA_DEADLINE_PHRASES = {
  remaining: (months: number) =>
    `Airlines must cancel eligible units for the 2024\u20132026 phase by January 2028, ${months} months from now. Supply of authorized units is the bottleneck.`,
  passed:
    'The first-phase cancellation deadline (January 2028) has passed. Second-phase demand now drives authorized supply.',
};

/* -------------------------------------------------------------------------- */
/* Vintage                                                                    */
/* -------------------------------------------------------------------------- */

export const VINTAGE_PRICE_COMPARISON: PriceComparisonDatum[] = [
  {
    label: 'Within five years',
    value: 9.31,
    displayValue: '$9.31',
    tone: 'removal',
    description: 'Average price rose 17% in 2024.',
    examples: 'Closer reporting-year match',
    change: 17,
  },
  {
    label: 'Older than five years',
    value: 2.94,
    displayValue: '$2.94',
    tone: 'neutral',
    description: 'Average price fell 43% in 2024.',
    examples: 'More exposure to legacy supply',
    change: -43,
  },
];

export const VINTAGE_PRICE_ARIA_LABEL =
  '2024 average transaction prices: credits within five years averaged $9.31, up 17 percent. Credits older than five years averaged $2.94, down 43 percent.';

export const VINTAGE_PRICE_LEGEND = {
  value: '217%',
  text: 'premium for credits from the previous five years.',
};

/**
 * Vintage year strip: years grouped at the five-year cutoff, each group
 * carrying its 2024 average price. Groups take the bar colors of the price
 * comparison above, so the strip reads as the same data in another form.
 */
export const VINTAGE_STRIP = {
  years: [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024],
  cutoff: 2020,
  older: { label: 'Older than five years', display: '$2.94' },
  recent: { label: 'Within five years', display: '$9.31' },
  bought: '\u2191 Bought in 2024',
  ariaLabel:
    'For 2024 transactions, vintages 2020 to 2024 count as within five years and averaged $9.31. Vintages 2019 and older averaged $2.94.',
};

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

/* -------------------------------------------------------------------------- */
/* Shared tails: price outlook                                                */
/* -------------------------------------------------------------------------- */

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
    body: 'Airlines must cancel eligible units for the 2024\u20132026 CORSIA phase, while Article 6 authorization is optional for host countries and granted project by project.',
  },
  {
    trend: 'declining',
    badge: 'Not authorized',
    title: 'No compliance bid',
    body: 'Without authorization a credit competes only for voluntary demand, so compliance scarcity does not lift its price.',
  },
];
