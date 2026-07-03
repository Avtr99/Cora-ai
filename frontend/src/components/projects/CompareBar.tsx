import React from 'react';
import { X, ArrowLeftRight } from 'lucide-react';
import type { VCMProject } from '@/types/project';

interface CompareBarProps {
  selected: VCMProject[];
  onRemove: (id: string) => void;
  onCompare: () => void;
  onClear: () => void;
}

export const CompareBar: React.FC<CompareBarProps> = ({
  selected,
  onRemove,
  onCompare,
  onClear,
}) => {
  if (selected.length === 0) return null;

  const canCompare = selected.length === 2;

  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 bg-surface-card/95 backdrop-blur-sm border-t border-border-ui shadow-bottom-bar">
      <div className="container mx-auto max-w-7xl px-4 md:px-10 py-3 flex items-center gap-3">
        {/* Icon */}
        <ArrowLeftRight className="w-4 h-4 text-text-muted flex-shrink-0 hidden sm:block" />

        {/* Selected project chips */}
        <div className="flex items-center gap-2 flex-1 min-w-0 overflow-x-auto">
          {selected.map((p) => (
            <div
              key={p.id}
              className="flex items-center gap-1.5 pl-3 pr-1.5 py-1.5 bg-surface-subtle border border-border-ui rounded-full flex-shrink-0 max-w-[200px]"
            >
              <span className="font-inter text-xs font-medium text-text-primary truncate">
                {p.name}
              </span>
              <button
                type="button"
                onClick={() => onRemove(p.id)}
                className="flex-shrink-0 p-0.5 hover:bg-surface-subtle rounded-full transition-colors"
                aria-label={`Remove ${p.name} from comparison`}
              >
                <X className="w-3 h-3 text-text-muted" />
              </button>
            </div>
          ))}

          {selected.length === 1 && (
            <span className="font-inter text-xs text-text-muted">
              + select one more
            </span>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            type="button"
            onClick={onClear}
            className="font-inter text-xs text-text-muted hover:text-text-primary transition-colors px-2 py-1.5"
          >
            Clear
          </button>
          <button
            type="button"
            onClick={onCompare}
            disabled={!canCompare}
            className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full font-inter text-sm font-medium transition-all
              focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
              ${canCompare
                ? 'bg-brand-900 text-white hover:bg-brand-500 shadow-sm'
                : 'bg-surface-subtle text-text-disabled cursor-not-allowed'
              }`}
          >
            Compare
          </button>
        </div>
      </div>
    </div>
  );
};
