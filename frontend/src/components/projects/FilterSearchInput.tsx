import React from 'react';
import { Search, X } from 'lucide-react';

interface FilterSearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  ariaLabel: string;
}

export const FilterSearchInput: React.FC<FilterSearchInputProps> = ({
  value,
  onChange,
  placeholder,
  ariaLabel,
}) => (
  <div className="relative">
    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" />
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      aria-label={ariaLabel}
      className="w-full h-8 pl-8 pr-8 font-inter text-xs text-text-primary placeholder:text-text-muted
        bg-surface-base border border-border-ui rounded-lg
        focus:outline-none focus:bg-surface-card focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
    />
    {value && (
      <button
        type="button"
        onClick={() => onChange('')}
        className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
        aria-label="Clear search"
      >
        <X className="w-3 h-3" />
      </button>
    )}
  </div>
);
