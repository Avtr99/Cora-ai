import { KPI, NEUTRAL } from '@/lib/colors';
import type { BarTone } from '@/data/pricingData';
import type { PriceComparisonDatum } from '@/data/pricingFactorContent';

export interface BarDatum {
  label: string;
  value: string;
  widthPct: number;
  tone: BarTone;
  /** Unscaled price, used for ratio captions such as `4.8x reduction`. */
  rawValue: number;
  /** Example sub-label shown under the bar name. */
  examples?: string;
  /** Year-on-year chip shown under the price. */
  chip?: { direction: 'up' | 'down'; text: string };
  /** Open-ended value: the ratio caption is a floor and carries a `+`. */
  open?: boolean;
}

/** Maps a semantic tone to its palette color. Adding a BarTone without a
 *  color here is a compile error. */
export const TONE_COLORS: Record<BarTone, string> = {
  reduction: KPI.reduction,
  removal: KPI.removal,
  'removal-deep': KPI.removalDeep,
  neutral: NEUTRAL[300],
};

/** The same mapping as a Tailwind class, so markup can carry color without
 *  an inline style. */
export const TONE_CLASSES: Record<BarTone, string> = {
  reduction: 'bg-kpi-reduction',
  removal: 'bg-kpi-removal',
  'removal-deep': 'bg-kpi-removal-deep',
  neutral: 'bg-text-disabled',
};

/** Normalize price data into proportional bar widths (max = 100%). */
export const toBarItems = (data: PriceComparisonDatum[]): BarDatum[] => {
  const maximum = Math.max(...data.map((datum) => datum.value));
  return data.map((datum) => ({
    label: datum.label,
    value: datum.displayValue,
    widthPct: (datum.value / maximum) * 100,
    tone: datum.tone,
    rawValue: datum.value,
    examples: datum.examples,
    chip: priceChangeChip(datum),
    open: datum.open,
  }));
};

const priceChangeChip = (datum: PriceComparisonDatum) =>
  datum.change === undefined
    ? undefined
    : {
        direction: datum.change < 0 ? ('down' as const) : ('up' as const),
        text: `${datum.change < 0 ? '\u2212' : '+'}${Math.abs(datum.change)}% in 2024`,
      };
