import React, { useState, useEffect } from 'react';
import { X, SlidersHorizontal, Search } from 'lucide-react';
import { FilterDropdown } from '@/components/ui/FilterDropdown';
import { FilterPanel } from '@/components/projects/FilterPanel';
import { useDebounce } from '@/hooks/useDebounce';
import type { ProjectFilterKey } from '@/types/project';

interface FilterOption {
  value: string;
  count: number;
}

interface ProjectFiltersV2Props {
  filters: Partial<Record<ProjectFilterKey, string>>;
  filterOptions: Record<string, FilterOption[]>;
  onFilterChange: (key: ProjectFilterKey, value: string | null) => void;
  onClearAll: () => void;
  activeFilterCount: number;
  filteredCount: number;
  totalCount: number;
  searchValue: string;
  onSearchChange: (value: string) => void;
}

const PRIMARY_FILTERS: { key: ProjectFilterKey; label: string }[] = [
  { key: 'registry', label: 'Registry' },
  { key: 'status', label: 'Status' },
  { key: 'reductionRemoval', label: 'Type' },
];

const SECONDARY_FILTERS: { key: ProjectFilterKey; label: string }[] = [
  { key: 'scope', label: 'Scope' },
  { key: 'type', label: 'Project Type' },
  { key: 'region', label: 'Region' },
  { key: 'country', label: 'Country' },
];

export const ProjectFiltersV2: React.FC<ProjectFiltersV2Props> = ({
  filters,
  filterOptions,
  onFilterChange,
  onClearAll,
  activeFilterCount,
  filteredCount,
  totalCount,
  searchValue,
  onSearchChange,
}) => {
  const [showMore, setShowMore] = useState(false);
  const [showPrimaryMobile, setShowPrimaryMobile] = useState(false);
  const [localSearch, setLocalSearch] = useState(searchValue);

  const debouncedSearch = useDebounce(onSearchChange, 250);

  useEffect(() => {
    setLocalSearch(searchValue);
  }, [searchValue]);

  const handleSearchInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setLocalSearch(v);
    debouncedSearch(v);
  };

  const handleClearSearch = () => {
    setLocalSearch('');
    onSearchChange('');
  };

  const primaryActiveCount = PRIMARY_FILTERS.reduce(
    (acc, f) => acc + (filters[f.key] ? 1 : 0),
    0
  );

  const secondaryActiveCount = SECONDARY_FILTERS.reduce(
    (acc, f) => acc + (filters[f.key] ? 1 : 0),
    0
  );

  return (
    <div className="mb-3">
      {/* Unified toolbar: search + filters + count */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Inline search */}
        <div className="relative flex-shrink-0 w-full sm:w-[300px] md:w-[280px] lg:w-[380px]">
          <Search
            className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-muted pointer-events-none"
            aria-hidden="true"
          />
          <input
            type="text"
            value={localSearch}
            onChange={handleSearchInput}
            placeholder="Search projects..."
            className="w-full h-8 pl-8 pr-8 font-inter text-xs text-text-primary placeholder:text-text-muted
              bg-surface-card border border-border-ui rounded-lg
              focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2
              transition-shadow"
            aria-label="Search projects"
          />
          {localSearch && (
            <button
              type="button"
              onClick={handleClearSearch}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-text-muted hover:text-text-primary transition-colors"
              aria-label="Clear search"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </div>

        {/* Divider */}
        <div className="hidden sm:block w-px h-5 bg-border-ui" />

        {/* Primary filters container — desktop shows 3 dropdowns, mobile shows unified button */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Desktop: individual dropdowns */}
          <div className="hidden md:flex items-center gap-2">
            {PRIMARY_FILTERS.map(({ key, label }) => (
              <FilterDropdown
                key={key}
                label={label}
                value={filters[key] || null}
                options={(filterOptions[key] || []).map((opt) => ({
                  value: opt.value,
                  label: opt.value,
                  count: opt.count,
                }))}
                onChange={(value) => onFilterChange(key, value)}
              />
            ))}
          </div>

          {/* Mobile: unified button with tabbed panel */}
          <div className="md:hidden relative">
            <button
              type="button"
              onClick={() => setShowPrimaryMobile(!showPrimaryMobile)}
              className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-lg font-inter text-xs font-medium transition-all
                border focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
                ${showPrimaryMobile || primaryActiveCount > 0
                  ? 'bg-brand-900 text-white border-brand-900'
                  : 'bg-surface-card text-text-secondary border-border-ui hover:border-border-ui'
                }`}
            >
              <SlidersHorizontal className="w-3 h-3" />
              <span>Registry & Type</span>
              {primaryActiveCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-white/25 text-white text-xs font-bold flex items-center justify-center">
                  {primaryActiveCount}
                </span>
              )}
            </button>

            {showPrimaryMobile && (
              <FilterPanel
                isOpen={showPrimaryMobile}
                onClose={() => setShowPrimaryMobile(false)}
                filterDefs={PRIMARY_FILTERS}
                filters={filters}
                filterOptions={filterOptions}
                onFilterChange={onFilterChange}
                onClearAll={() =>
                  PRIMARY_FILTERS.forEach((f) => onFilterChange(f.key, null))
                }
                clearLabel="Clear"
                ariaLabel="Primary filter categories"
                idPrefix="primary"
                mode="drawer"
              />
            )}
          </div>

          {/* More filters — floating popover, never displaces layout */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowMore(!showMore)}
              className={`inline-flex items-center gap-1.5 h-8 px-3 rounded-lg font-inter text-xs font-medium transition-all
                border focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
                ${showMore || secondaryActiveCount > 0
                  ? 'bg-brand-900 text-white border-brand-900'
                  : 'bg-surface-card text-text-secondary border-border-ui hover:border-border-ui'
                }`}
            >
              <SlidersHorizontal className="w-3 h-3" />
              <span>Filters</span>
              {secondaryActiveCount > 0 && (
                <span className="w-4 h-4 rounded-full bg-white/25 text-white text-xs font-bold flex items-center justify-center">
                  {secondaryActiveCount}
                </span>
              )}
            </button>

            {showMore && (
              <FilterPanel
                isOpen={showMore}
                onClose={() => setShowMore(false)}
                filterDefs={SECONDARY_FILTERS}
                filters={filters}
                filterOptions={filterOptions}
                onFilterChange={onFilterChange}
                onClearAll={() =>
                  SECONDARY_FILTERS.forEach((f) => onFilterChange(f.key, null))
                }
                clearLabel="Clear filters"
                ariaLabel="Filter categories"
                idPrefix="secondary"
                mode="popover"
              />
            )}
          </div>

          {activeFilterCount > 0 && (
            <button
              type="button"
              onClick={onClearAll}
              className="inline-flex items-center gap-1 font-inter text-xs text-text-muted hover:text-text-primary transition-colors ml-1"
            >
              <X className="h-3 w-3" />
              Clear all
            </button>
          )}
        </div>

        {(activeFilterCount > 0 || searchValue) && (
          <div aria-live="polite" className="font-inter text-xs text-text-muted flex-shrink-0">
            <span className="font-semibold text-text-primary">{filteredCount.toLocaleString()}</span>
            {' '}of {totalCount.toLocaleString()} projects
          </div>
        )}
      </div>
    </div>
  );
};
