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
    <div className="mt-3 flex flex-wrap items-center gap-2.5">
      <div className="relative flex-1 min-w-[200px] max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-muted" />
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search documents or tags"
          className="w-full h-8 pl-9 pr-8 rounded-lg border border-border-ui bg-surface-card font-inter text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
        />
        {search && (
          <button
            type="button"
            onClick={() => onSearchChange('')}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 text-text-muted hover:text-text-primary"
          >
            <X className="h-3 w-3" />
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
