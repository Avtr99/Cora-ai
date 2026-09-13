import React from 'react';
import { Search, X } from 'lucide-react';
import { FilterDropdown } from '@/components/ui/FilterDropdown';

interface FilterOption {
  value: string;
  label: string;
}

interface DocumentFiltersProps {
  search: string;
  onSearchChange: (value: string) => void;
  statusFilter: string | null;
  onStatusFilterChange: (value: string | null) => void;
  typeFilter: string | null;
  onTypeFilterChange: (value: string | null) => void;
  statusOptions: FilterOption[];
  typeOptions: FilterOption[];
}

export const DocumentFilters: React.FC<DocumentFiltersProps> = ({
  search,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  typeFilter,
  onTypeFilterChange,
  statusOptions,
  typeOptions,
}) => {
  return (
    <div className="mt-3 3xl:mt-4 4xl:mt-5 flex flex-wrap items-center gap-2.5 3xl:gap-3 4xl:gap-4">
      <div className="relative flex-1 min-w-[200px] max-w-md 3xl:max-w-lg 4xl:max-w-xl">
        <Search className="absolute left-3 3xl:left-4 top-1/2 -translate-y-1/2 h-3.5 w-3.5 3xl:h-4 3xl:w-4 4xl:h-5 4xl:w-5 text-text-muted" />
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search documents or tags"
          className="w-full h-8 3xl:h-10 4xl:h-12 pl-9 3xl:pl-11 pr-8 3xl:pr-10 rounded-lg 3xl:rounded-xl border border-border-ui bg-surface-card font-inter text-body-sm 3xl:text-[15px] 4xl:text-base text-text-primary placeholder:text-text-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
        />
        {search && (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute right-2.5 3xl:right-3 top-1/2 -translate-y-1/2 p-0.5 text-text-muted hover:text-text-primary"
          >
            <X className="h-3 w-3 3xl:h-4 3xl:w-4" />
          </button>
        )}
      </div>

      <FilterDropdown
        label="Status"
        value={statusFilter}
        options={statusOptions}
        onChange={onStatusFilterChange}
        width="120px"
      />

      <FilterDropdown
        label="Type"
        value={typeFilter}
        options={typeOptions}
        onChange={onTypeFilterChange}
        width="120px"
      />
    </div>
  );
};
