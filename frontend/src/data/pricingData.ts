/**
 * Shared constants for the pricing education page.
 */

export type ForceId = 'type' | 'integrity' | 'claims' | 'compliance' | 'vintage';

/**
 * Semantic role of a price-comparison bar. The chart maps tone to a palette
 * color, so a datum carries meaning and the component owns presentation.
 * `neutral` marks the reference level (older vintage, pre-approval) and
 * `removal-deep` marks the durable end of the removal range (engineered).
 */
export type BarTone = 'reduction' | 'removal' | 'removal-deep' | 'neutral';

/** The two factors that render a milestone timeline. */
export type TimelineForceId = 'claims' | 'compliance';

export const FORCE_ORDER: ForceId[] = ['type', 'integrity', 'claims', 'compliance', 'vintage'];

/**
 * Visual treatment of a phase bar on the timeline. The component maps the
 * role to a background, so a bar cannot render without its treatment.
 */
export type TimelineBarTone = 'muted' | 'base' | 'green' | 'hatch';

export interface TimelineBar {
  /** Fractional year the bar starts at - 2027 covers all of 2027. */
  from: number;
  /** Fractional year the bar ends at (exclusive). */
  to: number;
  tone: TimelineBarTone;
  /** Bars that run past the last labelled year fade at the right edge. */
  open?: boolean;
  text?: string;
}

export interface TimelineRow {
  name: string;
  sub: string;
  bars: TimelineBar[];
  /** Milestone ids drawn as diamonds on this row. */
  milestones?: number[];
  tag?: { at: number; text: string; soft?: boolean };
}

export interface TimelineMilestone {
  id: number;
  /** Fractional year the milestone sits at. */
  at: number;
  /** Display date, e.g. `Jan 2027`. */
  date: string;
  /** Era / version shown next to the date, e.g. `V2.0`. */
  era: string;
  label: string;
}

export interface ForceTimeline {
  from: number;
  to: number;
  rows: TimelineRow[];
  milestones: TimelineMilestone[];
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
      from: 2024,
      to: 2036,
      rows: [
        {
          name: 'V1.3.1',
          sub: 'Current standard',
          bars: [{ from: 2024, to: 2027, tone: 'muted', text: 'Neutralize residual emissions' }],
          milestones: [0],
          tag: { at: 2027, text: 'Replaced by V2.0', soft: true },
        },
        {
          name: 'V2.0',
          sub: 'New standard',
          bars: [{ from: 2027, to: 2036, tone: 'green', open: true, text: 'Removals required for net-zero' }],
          milestones: [1, 2],
        },
      ],
      milestones: [
        { id: 0, at: 2024, date: '2024', era: 'V1.3.1', label: 'Neutralize residual emissions' },
        { id: 1, at: 2027, date: 'Jan 2027', era: 'V2.0', label: 'Removals required for net-zero' },
        { id: 2, at: 2035, date: '2035', era: 'V2.0', label: '1% removal mandate begins' },
      ],
    } satisfies ForceTimeline,
  },
  compliance: {
    label: 'Article 6 authorization',
    subtitle: 'Compliance buyers',
    timeline: {
      from: 2024,
      to: 2036,
      rows: [
        {
          name: 'First phase',
          sub: '2024-2026 emissions',
          bars: [
            { from: 2024, to: 2027, tone: 'green', text: 'Offsetting period' },
            { from: 2027, to: 2028, tone: 'hatch' },
          ],
          milestones: [0, 1],
          tag: { at: 2028, text: 'Cancellation deadline' },
        },
        {
          name: 'Second phase',
          sub: '2027-2035 emissions',
          bars: [{ from: 2027, to: 2036, tone: 'muted', text: 'Second phase' }],
          milestones: [2],
        },
      ],
      milestones: [
        { id: 0, at: 2024, date: '2024', era: 'Phase 1', label: 'First phase begins' },
        { id: 1, at: 2028, date: 'Jan 2028', era: 'Phase 1', label: 'First-phase units must be cancelled' },
        { id: 2, at: 2036, date: '2035', era: 'Phase 2', label: 'Second phase ends' },
      ],
    } satisfies ForceTimeline,
  },
  vintage: {
    label: 'Vintage',
    subtitle: 'Price gap by credit age',
  },
} satisfies Record<ForceId, ForceEntry>;
