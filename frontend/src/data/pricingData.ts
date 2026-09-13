/**
 * Shared constants for the pricing education page.
 */

export type ForceId = 'type' | 'integrity' | 'claims' | 'compliance' | 'vintage';

/**
 * Semantic role of a price-comparison bar. The chart maps tone to a palette
 * color, so a datum carries meaning and the component owns presentation.
 * `neutral` marks the reference level (older vintage, pre-approval).
 */
export type BarTone = 'reduction' | 'removal' | 'neutral';

/** The two factors that render a milestone timeline. */
export type TimelineForceId = 'claims' | 'compliance';

export const FORCE_ORDER: ForceId[] = ['type', 'integrity', 'claims', 'compliance', 'vintage'];

export interface ForceTimeline {
  start: string;
  middle: string;
  end: string;
  startLabel: string;
  middleLabel: string;
  endLabel: string;
}

interface ForceEntry {
  label: string;
  /** Short descriptor shown under the tab label. */
  subtitle: string;
  timeline?: ForceTimeline;
}

/**
 * Factor metadata keyed by id - lookup is total, so no find()/non-null
 * assertions. Timeline-bearing factors (claims, compliance) literally have a
 * `timeline` property, so `FORCES.claims.timeline` is non-optional while
 * `FORCES.type.timeline` is a compile error.
 */
export const FORCES = {
  type: {
    label: 'Removal vs avoidance',
    subtitle: 'Removal vs reduction prices',
  },
  integrity: {
    label: 'Integrity (CCP label)',
    subtitle: 'Methodology approval',
  },
  claims: {
    label: 'Claim eligibility (SBTi)',
    subtitle: 'Eligible climate claims',
    timeline: {
      start: '2024',
      middle: 'Jan 2027',
      end: '2035',
      startLabel: 'V1.3.1\nneutralise residual emissions',
      middleLabel: 'Removals required\nfor net-zero',
      endLabel: '1% removal\nmandate begins',
    },
  },
  compliance: {
    label: 'Article 6 authorization',
    subtitle: 'Compliance buyers',
    timeline: {
      start: '2024',
      middle: 'Jan 2028',
      end: '2035',
      startLabel: 'First phase\nbegins',
      middleLabel: 'First-phase units\nmust be cancelled',
      endLabel: 'Second phase\nends',
    },
  },
  vintage: {
    label: 'Vintage',
    subtitle: 'Price gap by credit age',
  },
} satisfies Record<ForceId, ForceEntry>;
