/**
 * Fractional year for a date - 2026.76 for early October 2026. Timelines and
 * deadlines position "now" on a continuous year axis, so month and day
 * fractions matter.
 */
export const fractionalYear = (date: Date): number =>
  date.getFullYear() + date.getMonth() / 12 + (date.getDate() - 1) / 365;

/** Whole months from today until a fractional year - 0 once it has passed. */
export const monthsUntil = (at: number): number =>
  Math.max(0, Math.round((at - fractionalYear(new Date())) * 12));
