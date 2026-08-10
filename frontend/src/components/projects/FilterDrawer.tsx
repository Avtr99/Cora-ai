import React, { useState, useEffect } from 'react';
import { X, ChevronRight, ChevronDown } from 'lucide-react';
import type { ProjectFilterKey } from '@/types/project';
import type { FilterOption, FilterDef } from './filterTypes';
import { FilterSearchInput } from './FilterSearchInput';
import { FilterPillList } from './FilterPillList';

interface FilterDrawerProps {
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
}

export const FilterDrawer: React.FC<FilterDrawerProps> = ({
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
}) => {
  const [activeTab, setActiveTab] = useState<ProjectFilterKey | undefined>(
    filterDefs[0]?.key
  );
  const [search, setSearch] = useState('');

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

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (filterDefs.length === 0 || !isOpen) {
    return null;
  }

  const handleSectionToggle = (key: ProjectFilterKey) => {
    setActiveTab(activeTab === key ? undefined : key);
    setSearch('');
  };

  const activeTabOptions = activeTab ? filterOptions[activeTab] || [] : [];
  const activeTabLabel = filterDefs.find((f) => f.key === activeTab)?.label ?? '';

  const filteredActiveOptions = search
    ? activeTabOptions.filter((o) =>
        o.value.toLowerCase().includes(search.toLowerCase())
      )
    : activeTabOptions;

  const activeCount = filterDefs.reduce(
    (acc, f) => acc + (filters[f.key] ? 1 : 0),
    0
  );

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-30"
        role="presentation"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed z-40 flex flex-col bg-surface-card shadow-2xl inset-x-0 bottom-0 rounded-t-2xl max-h-[80vh] lg:fixed lg:inset-y-0 lg:right-0 lg:left-auto lg:top-0 lg:w-[400px] lg:max-h-none lg:rounded-none lg:border-l lg:border-border-ui">
        {/* Drawer header */}
        <div className="flex items-center justify-between p-3 border-b border-surface-subtle flex-shrink-0">
          <span className="font-poppins font-semibold text-sm text-text-primary">
            {ariaLabel}
          </span>
          <div className="flex items-center gap-3">
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

        {/* Global search */}
        <div className="p-3 border-b border-surface-subtle flex-shrink-0">
          <FilterSearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search filters..."
            ariaLabel="Search filters"
          />
        </div>

        {/* Accordion */}
        <div className="flex-1 overflow-y-auto">
          {search.length > 0 ? (
            filterDefs
              .map((def) => ({
                ...def,
                matches: (filterOptions[def.key] || []).filter((o) =>
                  o.value.toLowerCase().includes(search.toLowerCase())
                ),
              }))
              .filter((def) => def.matches.length > 0)
              .map(({ key, label, matches }) => (
                <div
                  key={key}
                  className="border-b border-surface-subtle last:border-0 p-3"
                >
                  <div className="font-inter text-xs font-medium text-text-primary mb-2">
                    {label}
                  </div>
                  <FilterPillList
                    options={matches}
                    selected={filters[key]}
                    onToggle={(value, isSelected) =>
                      onFilterChange(key, isSelected ? null : value)
                    }
                    emptySearchTerm={search}
                  />
                </div>
              ))
          ) : (
            filterDefs.map(({ key, label }) => {
              const isActive = activeTab === key;
              const hasValue = !!filters[key];
              return (
                <div
                  key={key}
                  className="border-b border-surface-subtle last:border-0"
                >
                  <button
                    type="button"
                    onClick={() => handleSectionToggle(key)}
                    aria-expanded={isActive}
                    aria-controls={`${idPrefix}-panel-${key}`}
                    id={`${idPrefix}-tab-${key}`}
                    className="w-full flex items-center justify-between px-3 py-3 text-left transition-colors hover:bg-surface-subtle"
                  >
                    <span className="flex items-center gap-1.5 font-inter text-xs font-medium text-text-primary">
                      {label}
                      {hasValue && (
                        <span className="w-1.5 h-1.5 rounded-full bg-brand-900" />
                      )}
                    </span>
                    {isActive ? (
                      <ChevronDown className="w-3.5 h-3.5 text-text-muted" />
                    ) : (
                      <ChevronRight className="w-3.5 h-3.5 text-text-muted" />
                    )}
                  </button>
                  {isActive && (
                    <div
                      id={`${idPrefix}-panel-${key}`}
                      role="region"
                      aria-labelledby={`${idPrefix}-tab-${key}`}
                      className="px-3 pb-3"
                    >
                      <FilterPillList
                        options={filteredActiveOptions}
                        selected={filters[key]}
                        onToggle={(value, isSelected) =>
                          onFilterChange(key, isSelected ? null : value)
                        }
                        emptySearchTerm={search}
                      />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>
    </>
  );
};
