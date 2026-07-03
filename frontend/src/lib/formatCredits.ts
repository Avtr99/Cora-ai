/**
 * Format large credit numbers into compact human-readable strings.
 *
 * - 1,500,000,000 → "1.5B"
 * - 1,500,000     → "1.5M"
 * - 1,500         → "2K"   (rounded, no decimal)
 * - 500           → "500"  (locale-aware)
 */
export function formatCredits(n: number): string {
  if (n >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}
