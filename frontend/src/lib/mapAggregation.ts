/**
 * Aggregates projects by country for the map view.
 * Produces per-country stats + a dominant scope color, so the map
 * can render one bubble per country sized by project count and
 * tinted by the most common project scope.
 */
import type { VCMProject } from '@/types/project';
import { getProjectTypeColor } from '@/lib/colors';
import { isMetaCountry } from '@/lib/countryCoordinates';

export interface CountryScopeBreakdown {
  scope: string;
  count: number;
  color: string;
}

export interface CountryAggregate {
  country: string;
  projects: VCMProject[];
  projectCount: number;
  creditsIssued: number;
  creditsRetired: number;
  dominantScope: string;
  dominantColor: string;
  /** Top scope breakdown (max 4 entries) for tooltip. */
  scopes: CountryScopeBreakdown[];
  /** Up to 3 top projects (by credits issued) for the tooltip. */
  topProjects: VCMProject[];
}

export function aggregateByCountry(projects: VCMProject[]): CountryAggregate[] {
  const byCountry = new Map<string, VCMProject[]>();

  for (const p of projects) {
    if (!p.country || isMetaCountry(p.country)) continue;
    const list = byCountry.get(p.country);
    if (list) list.push(p);
    else byCountry.set(p.country, [p]);
  }

  const result: CountryAggregate[] = [];

  for (const [country, list] of byCountry) {
    const scopeCount = new Map<string, number>();
    let creditsIssued = 0;
    let creditsRetired = 0;

    for (const p of list) {
      const scope = p.scope || 'Other';
      scopeCount.set(scope, (scopeCount.get(scope) || 0) + 1);
      creditsIssued += p.creditsIssued ?? 0;
      creditsRetired += p.creditsRetired ?? 0;
    }

    const scopes = Array.from(scopeCount.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([scope, count]) => ({
        scope,
        count,
        color: getProjectTypeColor(scope).accent,
      }))
      .slice(0, 4);

    const dominantScope = scopes[0]?.scope || 'Other';
    const dominantColor = scopes[0]?.color || getProjectTypeColor(dominantScope).accent;

    const topProjects = [...list]
      .sort((a, b) => (b.creditsIssued ?? 0) - (a.creditsIssued ?? 0))
      .slice(0, 3);

    result.push({
      country,
      projects: list,
      projectCount: list.length,
      creditsIssued,
      creditsRetired,
      dominantScope,
      dominantColor,
      scopes,
      topProjects,
    });
  }

  // Sort so bigger bubbles render UNDER smaller ones (smaller drawn last = on top).
  result.sort((a, b) => b.projectCount - a.projectCount);
  return result;
}

/**
 * Compute a radius for a country bubble from its project count using
 * a square-root scale — area is proportional to projects so visual
 * weight matches the data.
 */
export function bubbleRadius(count: number, opts?: { min?: number; max?: number; divisor?: number }): number {
  const { min = 4, max = 32, divisor = 2.1 } = opts ?? {};
  const r = Math.sqrt(count) * divisor;
  if (r < min) return min;
  if (r > max) return max;
  return r;
}
