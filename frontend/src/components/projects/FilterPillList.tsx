import React from 'react';
import type { FilterOption } from './filterTypes';

interface FilterPillListProps {
  options: FilterOption[];
  selected?: string | null;
  onToggle: (value: string, isSelected: boolean) => void;
  emptySearchTerm?: string;
}

export const FilterPillList: React.FC<FilterPillListProps> = ({
  options,
  selected,
  onToggle,
  emptySearchTerm,
}) => (
  <div className="flex flex-wrap gap-1.5">
    {options.length === 0 ? (
      <span className="font-inter text-xs text-text-muted py-2">
        {emptySearchTerm && emptySearchTerm.length > 0
          ? `No results for "${emptySearchTerm}"`
          : 'No options available'}
      </span>
    ) : (
      options.map((opt) => {
        const isSelected = selected === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onToggle(opt.value, isSelected)}
            aria-pressed={isSelected}
            className={`px-2.5 py-1 rounded-md font-inter text-xs font-medium transition-colors
              focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
              ${isSelected
                ? 'bg-brand-900 text-white'
                : 'bg-surface-subtle text-text-secondary hover:bg-border-ui'
              }`}
          >
            {opt.value}{' '}
            <span
              className={
                isSelected ? 'text-white/60' : 'text-text-muted'
              }
            >
              ({opt.count})
            </span>
          </button>
        );
      })
    )}
  </div>
);
