import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import type { ProjectFilterKey, ProjectFilters, VCMProject } from '@/types/project';
import { SEARCH_FIELDS } from '@/types/project';

const FILTER_KEYS: ProjectFilterKey[] = [
  'scope',
  'type',
  'region',
  'country',
  'registry',
  'status',
  'reductionRemoval',
];

const ITEMS_PER_PAGE = 30;

/**
 * Hook that syncs project filters, search query, and pagination
 * to URL search params via React Router's useSearchParams.
 */
export function useProjectFilters(projects: VCMProject[]) {
  const [searchParams, setSearchParams] = useSearchParams();

  // Read state from URL
  const query = searchParams.get('q') || '';
  const parsedPage = parseInt(searchParams.get('page') || '1', 10);
  const page = Number.isNaN(parsedPage) ? 1 : Math.max(1, parsedPage);

  const filters: ProjectFilters = useMemo(() => {
    const f: ProjectFilters = {};
    for (const key of FILTER_KEYS) {
      const val = searchParams.get(key);
      if (val) f[key] = val;
    }
    return f;
  }, [searchParams]);

  const activeFilterCount = Object.keys(filters).length + (query ? 1 : 0);

  // Setters that update URL
  const setQuery = useCallback(
    (q: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (q) {
          next.set('q', q);
        } else {
          next.delete('q');
        }
        next.delete('page'); // reset to page 1
        return next;
      }, { replace: true });
    },
    [setSearchParams],
  );

  const setFilter = useCallback(
    (key: ProjectFilterKey, value: string | null) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (value) {
          next.set(key, value);
        } else {
          next.delete(key);
        }
        next.delete('page');
        return next;
      }, { replace: true });
    },
    [setSearchParams],
  );

  const clearAllFilters = useCallback(() => {
    setSearchParams({}, { replace: true });
  }, [setSearchParams]);

  const setPage = useCallback(
    (p: number) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (p > 1) {
          next.set('page', String(p));
        } else {
          next.delete('page');
        }
        return next;
      }, { replace: true });
    },
    [setSearchParams],
  );

  // Filter + search logic
  const filtered = useMemo(() => {
    const lowerQuery = query.toLowerCase().trim();

    return projects.filter((p) => {
      // Apply filters
      for (const key of FILTER_KEYS) {
        const filterVal = filters[key];
        if (filterVal && p[key]?.toLowerCase() !== filterVal.toLowerCase()) {
          return false;
        }
      }

      // Apply search
      if (lowerQuery) {
        const topMatch = SEARCH_FIELDS.some((f) => {
          const val = p[f];
          return typeof val === 'string' && val.toLowerCase().includes(lowerQuery);
        });
        return topMatch;
      }

      return true;
    });
  }, [projects, filters, query]);

  // Pagination
  const totalPages = Math.max(1, Math.ceil(filtered.length / ITEMS_PER_PAGE));
  const safePage = Math.min(page, totalPages);
  const paginated = filtered.slice(0, safePage * ITEMS_PER_PAGE);
  const hasMore = safePage < totalPages;

  // Compute unique values for filter dropdowns
  const filterOptions = useMemo(() => {
    const opts: Record<ProjectFilterKey, Map<string, number>> = {
      scope: new Map(),
      type: new Map(),
      region: new Map(),
      country: new Map(),
      registry: new Map(),
      status: new Map(),
      reductionRemoval: new Map(),
    };

    for (const p of projects) {
      for (const key of FILTER_KEYS) {
        const val = p[key];
        if (val) {
          opts[key].set(val, (opts[key].get(val) || 0) + 1);
        }
      }
    }

    // Sort each map by count descending
    const sorted: Record<ProjectFilterKey, { value: string; count: number }[]> = {} as Record<ProjectFilterKey, { value: string; count: number }[]>;
    for (const key of FILTER_KEYS) {
      sorted[key] = Array.from(opts[key].entries())
        .map(([value, count]) => ({ value, count }))
        .sort((a, b) => b.count - a.count);
    }
    return sorted;
  }, [projects]);

  return {
    query,
    setQuery,
    filters,
    setFilter,
    clearAllFilters,
    activeFilterCount,
    filtered,
    paginated,
    page: safePage,
    setPage,
    totalPages,
    hasMore,
    totalCount: projects.length,
    filteredCount: filtered.length,
    filterOptions,
  };
}
