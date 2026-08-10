/**
 * Format large credit numbers into compact human-readable strings.
 *
 * - 1,500,000,000 → "1.5B"
 * - 1,500,000     → "1.5M"
 * - 1,500         → "2K"   (rounded, no decimal)
 * - 500           → "500"  (locale-aware)
 * - -151,516      → "-152K"
 *
 * Negative values are real: Berkeley reports a handful of projects where
 * retirements exceed issuances, giving a negative "credits remaining".
 * Scale by magnitude so those stay consistent with the compact style.
 */
export function formatCredits(n: number): string {
  const sign = n < 0 ? '-' : '';
  const abs = Math.abs(n);
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}
