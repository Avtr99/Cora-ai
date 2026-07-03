import React, { useState, useEffect } from 'react';
import { X, Search } from 'lucide-react';
import type { ProjectFilterKey } from '@/types/project';

interface FilterOption {
  value: string;
  count: number;
}

interface FilterDef {
  key: ProjectFilterKey;
  label: string;
}

interface FilterPanelProps {
  isOpen: boolean;
  onClose: () => void;
  filterDefs: FilterDef[];
  filters: Partial<Record<ProjectFilterKey, string>>;
  filterOptions: Record<string, FilterOption[]>;
  onFilterChange: (key: ProjectFilterKey, value: string | null) => void;
  onClearAll: () => void;
  clearLabel: string;
  ariaLabel: string;
  idPrefix: string;
  mode: 'drawer' | 'popover';
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
  isOpen,
  onClose,
  filterDefs,
  filters,
  filterOptions,
  onFilterChange,
  onClearAll,
  clearLabel,
  ariaLabel,
  idPrefix,
  mode,
}) => {
  const [activeTab, setActiveTab] = useState<ProjectFilterKey | undefined>(
    filterDefs[0]?.key
  );
  const [tabSearch, setTabSearch] = useState('');

  // Sync activeTab when filterDefs changes
  useEffect(() => {
    if (filterDefs.length === 0) {
      setActiveTab(undefined);
      return;
    }
    const keys = filterDefs.map((f) => f.key);
    if (!activeTab || !keys.includes(activeTab)) {
      setActiveTab(keys[0]);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterDefs]);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Guard against empty filterDefs or closed panel
  if (filterDefs.length === 0 || !isOpen) {
    return null;
  }

  const handleTabChange = (key: ProjectFilterKey) => {
    setActiveTab(key);
    setTabSearch('');
    // Focus the newly selected tab
    requestAnimationFrame(() => {
      const tabEl = document.getElementById(`${idPrefix}-tab-${key}`);
      tabEl?.focus();
    });
  };

  const handleTabKeyDown = (e: React.KeyboardEvent, currentIndex: number) => {
    const tabs = filterDefs.map(f => f.key);
    let newIndex = currentIndex;

    switch (e.key) {
      case 'ArrowLeft':
        e.preventDefault();
        newIndex = currentIndex > 0 ? currentIndex - 1 : tabs.length - 1;
        break;
      case 'ArrowRight':
        e.preventDefault();
        newIndex = currentIndex < tabs.length - 1 ? currentIndex + 1 : 0;
        break;
      case 'Home':
        e.preventDefault();
        newIndex = 0;
        break;
      case 'End':
        e.preventDefault();
        newIndex = tabs.length - 1;
        break;
      default:
        return;
    }

    handleTabChange(tabs[newIndex]);
  };

  const activeTabOptions = filterOptions[activeTab] || [];
  const activeTabValue = filters[activeTab];
  const activeTabLabel = filterDefs.find((f) => f.key === activeTab)?.label ?? '';

  const filteredOptions = tabSearch
    ? activeTabOptions.filter((o) =>
        o.value.toLowerCase().includes(tabSearch.toLowerCase())
      )
    : activeTabOptions;

  const activeCount = filterDefs.reduce(
    (acc, f) => acc + (filters[f.key] ? 1 : 0),
    0
  );

  const containerClasses =
    mode === 'popover'
      ? 'fixed lg:absolute inset-x-0 bottom-0 lg:inset-auto lg:top-full lg:left-0 lg:mt-2 z-40 bg-surface-card lg:rounded-xl lg:border lg:border-border-ui shadow-2xl lg:shadow-xl overflow-hidden rounded-t-2xl lg:rounded-t-xl max-h-[80vh] lg:max-h-none lg:w-[680px]'
      : 'fixed inset-x-0 bottom-0 z-40 bg-surface-card border-t border-border-ui shadow-2xl overflow-hidden rounded-t-2xl max-h-[80vh]';

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-30"
        role="presentation"
        onClick={onClose}
      />

      {/* Panel */}
      <div className={containerClasses}>
        {/* Tab nav + actions */}
        <div
          className="flex items-center border-b border-surface-subtle px-3 pt-1 overflow-x-auto scrollbar-hide"
          role="tablist"
          aria-label={ariaLabel}
        >
          {filterDefs.map(({ key, label }, index) => {
            const isActive = activeTab === key;
            const hasValue = !!filters[key];
            return (
              <button
                key={key}
                type="button"
                onClick={() => handleTabChange(key)}
                onKeyDown={(e) => handleTabKeyDown(e, index)}
                role="tab"
                id={`${idPrefix}-tab-${key}`}
                aria-selected={isActive}
                aria-controls={`${idPrefix}-panel-${key}`}
                tabIndex={isActive ? 0 : -1}
                className={`px-3 py-2.5 font-inter text-xs font-medium transition-colors relative flex-shrink-0
                  ${isActive ? 'text-text-primary' : 'text-text-muted hover:text-text-muted'}`}
              >
                <span className="flex items-center gap-1.5">
                  {label}
                  {hasValue && (
                    <span className="w-1.5 h-1.5 rounded-full bg-brand-900" />
                  )}
                </span>
                {isActive && (
                  <span className="absolute bottom-0 left-3 right-3 h-[2px] bg-brand-900 rounded-t" />
                )}
              </button>
            );
          })}
          <div className="flex items-center gap-3 ml-auto pr-1">
            {activeCount > 0 && (
              <button
                type="button"
                onClick={onClearAll}
                className="font-inter text-xs text-destructive hover:text-destructive/80 transition-colors"
              >
                {clearLabel}
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 hover:bg-surface-subtle rounded-lg transition-colors"
              aria-label="Close panel"
            >
              <X className="w-3.5 h-3.5 text-text-muted" />
            </button>
          </div>
        </div>

        {/* Search + pills */}
        <div
          className="p-4"
          role="tabpanel"
          id={`${idPrefix}-panel-${activeTab}`}
          aria-labelledby={`${idPrefix}-tab-${activeTab}`}
        >
          <div className="relative mb-3">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted pointer-events-none" />
            <input
              type="text"
              value={tabSearch}
              onChange={(e) => setTabSearch(e.target.value)}
              placeholder={`Search ${activeTabLabel.toLowerCase()}...`}
              aria-label={`Search ${activeTabLabel}`}
              className="w-full h-8 pl-8 pr-8 font-inter text-xs text-text-primary placeholder:text-text-muted
                bg-surface-base border border-border-ui rounded-lg
                focus:outline-none focus:bg-surface-card focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
            />
            {tabSearch && (
              <button
                type="button"
                onClick={() => setTabSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-text-muted hover:text-text-primary transition-colors"
                aria-label="Clear search"
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>

          <div className="flex flex-wrap gap-1.5 max-h-[200px] overflow-y-auto">
            {activeTabOptions.length === 0 && !tabSearch ? (
              <span className="font-inter text-xs text-text-muted py-2">
                No options available
              </span>
            ) : filteredOptions.length === 0 && tabSearch ? (
              <span className="font-inter text-xs text-text-muted py-2">
                No results for &ldquo;{tabSearch}&rdquo;
              </span>
            ) : (
              filteredOptions.map((opt) => {
                const isSelected = activeTabValue === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() =>
                      onFilterChange(activeTab, isSelected ? null : opt.value)
                    }
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
        </div>
      </div>
    </>
  );
};
