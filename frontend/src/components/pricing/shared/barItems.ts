import { KPI, NEUTRAL } from '@/lib/colors';
import type { BarTone } from '@/data/pricingData';
import type { PriceBarDatum } from '@/data/pricingFactorContent';

export interface BarDatum {
  label: string;
  value: string;
  widthPct: number;
  tone: BarTone;
}

/** Tone → palette. Adding a BarTone without a color is a compile error. */
export const TONE_COLORS: Record<BarTone, string> = {
  reduction: KPI.reduction,
  removal: KPI.removal,
  neutral: NEUTRAL[300],
};

/** Normalize price data into proportional bar widths (max = 100%). */
export const toBarItems = (data: PriceBarDatum[]): BarDatum[] => {
  const maximum = Math.max(...data.map((datum) => datum.value));
  return data.map((datum) => ({
    label: datum.label,
    value: datum.displayValue,
    widthPct: (datum.value / maximum) * 100,
    tone: datum.tone,
  }));
};
