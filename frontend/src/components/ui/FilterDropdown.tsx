import React, { useState, useEffect, useId, useMemo, useRef, useLayoutEffect } from 'react';
import { ChevronDown, X } from 'lucide-react';

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
}

export interface FilterDropdownProps {
  label: string;
  value: string | null;
  options: FilterOption[];
  onChange: (value: string | null) => void;
  width?: string;
  /** Horizontal alignment of the dropdown relative to the trigger */
  align?: 'left' | 'right';
  /** Start the dropdown in an open state (useful for Storybook / visual regression) */
  initialOpen?: boolean;
}

interface MenuPosition {
  top: number;
  left?: number;
  right?: number;
}

/**
 * Reusable filter dropdown component matching ProjectFiltersV2 styling
 * Use this for consistent filter dropdowns across the application
 */
export const FilterDropdown: React.FC<FilterDropdownProps> = ({
  label,
  value,
  options,
  onChange,
  width = 'auto',
  align = 'left',
  initialOpen = false,
}) => {
  const [open, setOpen] = useState(initialOpen);
  const [focusedIndex, setFocusedIndex] = useState<number>(-1);
  const [menuPos, setMenuPos] = useState<MenuPosition | null>(null);
  const listId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const displayLabel = useMemo(() => {
    if (!value) return label;
    const selectedOption = options.find(opt => opt.value === value);
    return selectedOption?.label || value;
  }, [value, label, options]);

  const menuStyle = useMemo<React.CSSProperties | undefined>(() => {
    if (!menuPos) return undefined;
    const style: React.CSSProperties = { '--menu-top': `${menuPos.top}px` } as React.CSSProperties;
    if (menuPos.left !== undefined) style['--menu-left'] = `${menuPos.left}px`;
    if (menuPos.right !== undefined) style['--menu-right'] = `${menuPos.right}px`;
    return style;
  }, [menuPos]);

  const optionCount = value ? options.length + 1 : options.length;

  // Compute fixed dropdown position relative to the trigger so it escapes
  // any parent overflow:hidden / rounded clipping (e.g. cards on the document store).
  const updateMenuPosition = useMemo(() => () => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    const margin = 4;
    setMenuPos(
      align === 'right'
        ? { top: rect.bottom + margin, right: window.innerWidth - rect.right }
        : { top: rect.bottom + margin, left: rect.left }
    );
  }, [align]);

  useLayoutEffect(() => {
    if (!open) {
      setMenuPos(null);
      return;
    }
    updateMenuPosition();
  }, [open, updateMenuPosition]);

  useEffect(() => {
    if (!open) return;
    const handle = () => updateMenuPosition();
    window.addEventListener('resize', handle);
    window.addEventListener('scroll', handle, true);
    return () => {
      window.removeEventListener('resize', handle);
      window.removeEventListener('scroll', handle, true);
    };
  }, [open, updateMenuPosition]);

  // Initialize focused index when opening
  useEffect(() => {
    if (open) {
      // If there's a value, focus the first option (Clear button at index 0)
      // Otherwise focus index 0 (first actual option)
      setFocusedIndex(0);
    } else {
      setFocusedIndex(-1);
    }
  }, [open]);

  // Scroll focused option into view
  useEffect(() => {
    if (focusedIndex >= 0 && open) {
      const optionEl = document.getElementById(`${listId}-option-${focusedIndex}`);
      if (optionEl) {
        optionEl.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [focusedIndex, listId, open]);

  // Lock body scroll on mobile when dropdown is open
  useEffect(() => {
    if (!open) return;

    const isMobile = window.matchMedia('(max-width: 640px)').matches;
    if (!isMobile) return;

    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  // Keyboard navigation
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'Escape':
          e.preventDefault();
          setOpen(false);
          break;
        case 'ArrowDown':
          e.preventDefault();
          setFocusedIndex((prev) => {
            const next = prev + 1;
            return next >= optionCount ? 0 : next;
          });
          break;
        case 'ArrowUp':
          e.preventDefault();
          setFocusedIndex((prev) => {
            const next = prev - 1;
            return next < 0 ? optionCount - 1 : next;
          });
          break;
        case 'Enter':
          e.preventDefault();
          if (focusedIndex >= 0 && focusedIndex < optionCount) {
            if (value && focusedIndex === 0) {
              // Clear button
              onChange(null);
            } else {
              const optionIndex = value ? focusedIndex - 1 : focusedIndex;
              if (optionIndex >= 0 && optionIndex < options.length) {
                onChange(options[optionIndex].value);
              }
            }
            setOpen(false);
          }
          break;
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, optionCount, focusedIndex, value, options, onChange]);

  return (
    <div className="relative" style={{ width }}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(!open)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? `${listId}-list` : undefined}
        className={`inline-flex items-center justify-between w-full h-8 px-3 rounded-lg font-inter text-xs font-medium transition-all
          border focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
          ${value
            ? 'bg-brand-900 text-white border-brand-900'
            : 'bg-surface-card text-text-secondary border-border-ui hover:border-border-ui'
          }`}
      >
        <span className="truncate">{displayLabel}</span>
        <ChevronDown aria-hidden="true" className={`w-3 h-3 transition-transform duration-200 ${open ? 'rotate-180' : ''} ${value ? 'text-white/70' : 'text-text-muted'}`} />
      </button>

      {open && menuPos && (
        <>
          <div
            className="fixed inset-0 z-30 sm:bg-transparent bg-black/20"
            onClick={() => setOpen(false)}
            aria-hidden="true"
          />
          <div
            id={`${listId}-list`}
            role="listbox"
            aria-label={label}
            aria-activedescendant={focusedIndex >= 0 ? `${listId}-option-${focusedIndex}` : undefined}
            tabIndex={-1}
            style={menuStyle}
            className="fixed inset-x-0 bottom-0 sm:inset-x-auto sm:top-[var(--menu-top)] sm:left-[var(--menu-left)] sm:right-[var(--menu-right)] sm:bottom-auto z-40 bg-surface-card border-t sm:border border-border-ui rounded-t-2xl sm:rounded-xl shadow-2xl sm:shadow-lg max-h-[70vh] sm:max-h-[280px] overflow-hidden sm:min-w-[200px] sm:max-w-[320px] flex flex-col"
          >
            {/* Mobile header — makes the bottom sheet look like a modal,
                mirroring the Filters popup for UX consistency. */}
            <div className="sm:hidden flex items-center justify-between border-b border-surface-subtle px-4 py-3">
              <span className="font-poppins text-sm font-semibold text-text-primary">
                {label}
              </span>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label={`Close ${label} filter`}
                className="p-1.5 -m-1.5 rounded-lg text-text-muted hover:bg-surface-subtle transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto py-1">
              {value && (
                <button
                  id={`${listId}-option-0`}
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => { onChange(null); setOpen(false); }}
                  onMouseEnter={() => setFocusedIndex(0)}
                  className={`w-full text-left px-4 sm:px-3 py-3 sm:py-2 font-inter text-sm sm:text-xs transition-colors
                    ${focusedIndex === 0 ? 'bg-surface-subtle' : 'hover:bg-surface-base'}
                    text-text-muted hover:text-text-primary
                  `}
                >
                  Clear {label.toLowerCase()}
                </button>
              )}
              {options.length === 0 ? (
                <div className="px-4 sm:px-3 py-3 sm:py-2 font-inter text-sm sm:text-xs text-text-muted italic">
                  No options available
                </div>
              ) : (
                options.map((opt, idx) => {
                  const optionIndex = value ? idx + 1 : idx;
                  return (
                    <button
                      id={`${listId}-option-${optionIndex}`}
                      key={opt.value}
                      type="button"
                      role="option"
                      aria-selected={value === opt.value}
                      onClick={() => { onChange(opt.value); setOpen(false); }}
                      onMouseEnter={() => setFocusedIndex(optionIndex)}
                      className={`w-full text-left px-4 sm:px-3 py-3 sm:py-2 font-inter text-sm sm:text-xs transition-colors flex items-center justify-between gap-3
                      ${value === opt.value
                        ? 'bg-surface-subtle text-text-primary font-medium'
                        : focusedIndex === optionIndex
                          ? 'bg-surface-subtle'
                          : 'text-text-secondary hover:bg-surface-base'
                      }`}
                    >
                      <span className="break-words max-w-[260px] overflow-hidden">{opt.label}</span>
                      {opt.count !== undefined && (
                        <span className="text-text-muted text-xs sm:text-2xs flex-shrink-0">{opt.count.toLocaleString()}</span>
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default FilterDropdown;
