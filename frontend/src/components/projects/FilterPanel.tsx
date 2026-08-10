import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import type { ProjectFilterKey } from '@/types/project';
import type { FilterOption, FilterDef } from './filterTypes';
import { FilterSearchInput } from './FilterSearchInput';
import { FilterPillList } from './FilterPillList';

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
}) => {
  const [activeTab, setActiveTab] = useState<ProjectFilterKey | undefined>(
    filterDefs[0]?.key
  );
  const [tabSearch, setTabSearch] = useState('');

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

  const handleTabChange = (key: ProjectFilterKey) => {
    setActiveTab(key);
    setTabSearch('');
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

  const activeTabOptions = activeTab ? filterOptions[activeTab] || [] : [];
  const activeTabValue = activeTab ? filters[activeTab] : undefined;
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

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-30"
        role="presentation"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed inset-x-0 bottom-0 z-40 bg-surface-card border-t border-border-ui shadow-2xl overflow-hidden rounded-t-2xl max-h-[80vh]">
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
          <div className="mb-3">
            <FilterSearchInput
              value={tabSearch}
              onChange={setTabSearch}
              placeholder={`Search ${activeTabLabel.toLowerCase()}...`}
              ariaLabel={`Search ${activeTabLabel}`}
            />
          </div>
          <FilterPillList
            options={filteredOptions}
            selected={activeTabValue}
            onToggle={(value, isSelected) =>
              activeTab ? onFilterChange(activeTab, isSelected ? null : value) : undefined
            }
            emptySearchTerm={tabSearch}
          />
        </div>
      </div>
    </>
  );
};
