import React, { useState, useCallback, useRef, useEffect } from 'react';
import type { VCMProject } from '@/types/project';
import { getProjectTypeColor, getStatusStyle, TEXT } from '@/lib/colors';
import { useLongPress } from '@/hooks/useLongPress';
import { formatCredits } from '@/lib/formatCredits';

interface ProjectListItemProps {
  project: VCMProject;
  isActive: boolean;
  isSelected: boolean;
  onSelect: (project: VCMProject) => void;
  onToggleCompare: (id: string) => void;
  compareDisabled: boolean;
  /** Soft-highlight when the project's country is hovered on the map. */
  isCountryHighlighted?: boolean;
  /** Fires when the row is hovered — used to sync map-side highlight. */
  onMouseEnterRow?: (project: VCMProject) => void;
  /** Fires when the pointer leaves the row. */
  onMouseLeaveRow?: () => void;
  /** Disables/hides the compare checkbox entirely. */
  hideCompare?: boolean;
}

/** Selects the background class for a project list item row. */
function getItemBgClass({
  longPressFlash,
  isActive,
  isCountryHighlighted,
}: {
  longPressFlash: boolean;
  isActive: boolean;
  isCountryHighlighted: boolean;
}): string {
  if (longPressFlash) return 'bg-brand-100/40';
  if (isActive) return 'bg-brand-100/30';
  if (isCountryHighlighted) return 'bg-brand-100/20';
  return 'bg-surface-card hover:bg-surface-base';
}

export const ProjectListItem: React.FC<ProjectListItemProps> = ({
  project,
  isActive,
  isSelected,
  onSelect,
  onToggleCompare,
  compareDisabled,
  isCountryHighlighted = false,
  onMouseEnterRow,
  onMouseLeaveRow,
  hideCompare = false,
}) => {
  const typeColor = getProjectTypeColor(project.type);
  const statusStyle = getStatusStyle(project.status);

  // Handle creditsIssued === 0 edge case explicitly
  const retiredPct: number | null = (() => {
    if (project.creditsIssued === 0) {
      // No credits issued - can't compute meaningful percentage
      return null;
    }
    const rawRetiredPct = (project.creditsRetired / project.creditsIssued) * 100;
    if (project.creditsRetired > 0) {
      return Math.max(1, Math.min(100, Math.round(rawRetiredPct)));
    }
    return 0;
  })();

  const retiredLabel = (() => {
    if (retiredPct === null) return 'N/A';
    if (project.creditsIssued > 0 && project.creditsRetired > 0) {
      const rawRetiredPct = (project.creditsRetired / project.creditsIssued) * 100;
      if (rawRetiredPct > 0 && rawRetiredPct < 0.5) return '<1%';
    }
    return retiredPct === null ? 'N/A' : `${retiredPct}%`;
  })();

  // Long-press to toggle compare selection (mobile UX)
  const [longPressFlash, setLongPressFlash] = useState(false);
  const flashTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Cleanup flash timeout on unmount
  useEffect(() => {
    return () => {
      if (flashTimeoutRef.current) {
        clearTimeout(flashTimeoutRef.current);
      }
    };
  }, []);

  const handleLongPress = useCallback(() => {
    if (!hideCompare && (!compareDisabled || isSelected)) {
      onToggleCompare(project.id);
      // Brief visual flash to confirm selection
      setLongPressFlash(true);
      // Clear any existing timeout before setting new one
      if (flashTimeoutRef.current) {
        clearTimeout(flashTimeoutRef.current);
      }
      flashTimeoutRef.current = setTimeout(() => {
        setLongPressFlash(false);
        flashTimeoutRef.current = null;
      }, 400);
    }
  }, [hideCompare, compareDisabled, isSelected, onToggleCompare, project.id]);

  const longPressHandlers = useLongPress({ onLongPress: handleLongPress, threshold: 500 });

  const memoOnMouseEnter = useCallback(
    () => onMouseEnterRow?.(project),
    [onMouseEnterRow, project],
  );

  return (
    <div
      role="listitem"
      className={`relative group transition-colors duration-150 cursor-pointer ${getItemBgClass({ longPressFlash, isActive, isCountryHighlighted })}`}
      onMouseEnter={onMouseEnterRow ? memoOnMouseEnter : undefined}
      onMouseLeave={onMouseLeaveRow}
      {...(!hideCompare ? longPressHandlers : {})}
    >
      {/* Compare checkbox — appears on hover or when selected */}
      {!hideCompare && (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          if (!compareDisabled || isSelected) onToggleCompare(project.id);
        }}
        aria-pressed={isSelected}
        aria-label={isSelected ? `Remove ${project.name} from comparison` : `Add ${project.name} to comparison`}
        disabled={compareDisabled && !isSelected}
        className={`absolute top-3 right-3 z-10 w-6 h-6 rounded flex items-center justify-center
          border transition-all flex-shrink-0
          focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
          ${isSelected
            ? 'border-brand-500 bg-brand-500 opacity-100'
            : compareDisabled
              ? 'border-border-ui bg-surface-subtle cursor-not-allowed opacity-0'
              : 'border-border-ui bg-surface-card hover:border-brand-500 opacity-0 group-hover:opacity-100'
          }`}
      >
        {isSelected && (
          <svg width="8" height="6" viewBox="0 0 10 8" fill="none">
            <path d="M1 4L3.5 6.5L9 1" stroke={TEXT.inverse} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>
      )}

      {/* Main clickable area */}
      <button
        type="button"
        className="w-full text-left px-4 py-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500"
        onClick={() => onSelect(project)}
        aria-label={`View details for ${project.name}`}
      >
        {/* Row 1: Status badge + ID + Registry */}
        <div className="flex items-center gap-1.5 mb-1">
          <span
            className="inline-flex items-center gap-1 px-1 py-0.5 rounded text-2xs font-semibold font-inter uppercase tracking-wide flex-shrink-0"
            style={{ backgroundColor: statusStyle.bg, color: statusStyle.text }}
          >
            <span className="w-1 h-1 rounded-full" style={{ backgroundColor: statusStyle.dot }} />
            {project.status.length > 12 ? project.status.slice(0, 10) + '…' : project.status}
          </span>
          <span className="font-inter text-2xs text-text-muted font-medium truncate">{project.id}</span>
          <span className="font-inter text-2xs text-text-muted">·</span>
          <span className="font-inter text-2xs text-text-muted truncate">{project.registry}</span>
        </div>

        {/* Row 2: Project name */}
        <h3 className="font-poppins font-semibold text-sm text-text-primary leading-[1.35] line-clamp-2 pr-8 mb-1.5">
          {project.name}
        </h3>

        {/* Row 3: Type badge + Country */}
        <div className="flex items-center gap-1.5 mb-2">
          <span
            className="inline-block px-1.5 py-0.5 rounded text-2xs font-medium font-inter truncate max-w-[140px]"
            style={{ backgroundColor: typeColor.bg, color: typeColor.text }}
          >
            {project.type}
          </span>
          {project.country && (
            <span className="font-inter text-2xs text-text-muted truncate">{project.country}</span>
          )}
        </div>

        {/* Row 4: Credits with micro progress bar */}
        <div className="flex items-center gap-2">
          <span className="font-poppins font-semibold text-xs text-text-primary tabular-nums flex-shrink-0">
            {formatCredits(project.creditsIssued)}
          </span>
          <div className="flex-1 rounded-full bg-surface-subtle overflow-hidden" style={{ height: '4px' }}>
            <div
              className={`rounded-full transition-all duration-200 ${
                retiredPct === null ? 'bg-text-muted' : retiredPct >= 100 ? 'bg-semantic-success-icon' : 'bg-text-muted'
              }`}
              style={{
                height: '4px',
                width: retiredPct === null ? '0%' : `${retiredPct}%`,
              }}
            />
          </div>
          <span className="font-inter text-xs text-text-muted flex-shrink-0 tabular-nums">
            {retiredLabel} retired
          </span>
        </div>
      </button>
    </div>
  );
};
