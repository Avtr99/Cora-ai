import React, { Suspense, lazy, useCallback } from 'react';
import { Maximize2 } from 'lucide-react';
import { IconWrapper } from '@/components/icons/IconWrapper';
import XIcon from '@/assets/icons/x.svg?react';
import { BRAND } from '@/lib/colors';
import MapIcon from '@/assets/icons/map.svg?react';
import FileIcon from '@/assets/icons/file.svg?react';
import { ProjectListItem } from '@/components/projects/ProjectListItem';
import { ProjectDetailPanel } from '@/components/projects/ProjectDetailPanel';
import TabButton from '@/components/projects/TabButton';
import MapFallback from '@/components/projects/MapFallback';
import ErrorBoundary from '@/components/ErrorBoundary';
import type { VCMProject, ProjectFilterKey } from '@/types/project';
import type { RightPanel } from '@/hooks/useProjectsPageState';

const ProjectMap = lazy(() =>
  import('@/components/projects/ProjectMap').then((m) => ({ default: m.ProjectMap })),
);

interface InlineSplitViewProps {
  paginated: VCMProject[];
  filtered: VCMProject[];
  activeProject: VCMProject | null;
  compareIds: string[];
  hoveredCountry: string | null;
  rightPanel: RightPanel;
  filters: Partial<Record<ProjectFilterKey, string>>;
  filteredCount: number;
  hasMore: boolean;
  listRef: React.RefObject<HTMLDivElement | null>;
  expandTriggerRef: React.RefObject<HTMLButtonElement | null>;
  onSelectProject: (p: VCMProject) => void;
  onToggleCompare: (id: string) => void;
  onHoverCountry: (c: string | null) => void;
  onSetRightPanel: (panel: RightPanel) => void;
  onSetFilter: (key: string, value: string | null) => void;
  onListScroll: () => void;
  onSetMapFullscreen: (fs: boolean) => void;
}

const InlineSplitView: React.FC<InlineSplitViewProps> = ({
  paginated,
  filtered,
  activeProject,
  compareIds,
  hoveredCountry,
  rightPanel,
  filters,
  filteredCount,
  hasMore,
  listRef,
  expandTriggerRef,
  onSelectProject,
  onToggleCompare,
  onHoverCountry,
  onSetRightPanel,
  onSetFilter,
  onListScroll,
  onSetMapFullscreen,
}) => {
  // Stable handlers to preserve memoization of ProjectListItem
  const handleMouseEnterRow = useCallback(
    (project: VCMProject) => onHoverCountry(project.country || null),
    [onHoverCountry],
  );
  const handleMouseLeaveRow = useCallback(() => onHoverCountry(null), [onHoverCountry]);

  return (
  <div
    className="flex border border-border-ui rounded-2xl overflow-hidden bg-surface-card shadow-card-sm"
    style={{ height: 'calc(100vh - 180px)', minHeight: '560px' }}
  >
    {/* Left: Scrollable project list */}
    <div
      ref={listRef}
      onScroll={onListScroll}
      className="w-full lg:w-[380px] lg:flex-shrink-0 border-r border-border-ui overflow-y-auto divide-y divide-surface-subtle"
      data-project-list
      role="list"
      aria-label="Project list"
    >
      {paginated.map((project) => (
        <ProjectListItem
          key={project.id}
          project={project}
          isActive={activeProject?.id === project.id}
          isSelected={compareIds.includes(project.id)}
          onSelect={onSelectProject}
          onToggleCompare={onToggleCompare}
          compareDisabled={compareIds.length >= 2}
          isCountryHighlighted={hoveredCountry === project.country}
          onMouseEnterRow={handleMouseEnterRow}
          onMouseLeaveRow={handleMouseLeaveRow}
        />
      ))}

      {hasMore && (
        <div className="px-4 py-3 text-center">
          <span className="font-inter text-xs text-text-muted">
            Scroll for more...
          </span>
        </div>
      )}
    </div>

    {/* Right: Map ↔ Detail tabbed panel */}
    <div className="hidden lg:flex flex-1 min-w-0 flex-col bg-surface-card">
      {/* Tab header */}
      <div className="flex items-center justify-between px-4 h-11 border-b border-border-ui bg-surface-base flex-shrink-0">
        <div
          className="inline-flex items-center bg-surface-card border border-border-ui rounded-full p-0.5"
          role="tablist"
          aria-label="Right panel view"
        >
          <TabButton
            id="projects-tab-map"
            ariaControls="projects-panel-map"
            active={rightPanel === 'map'}
            onClick={() => onSetRightPanel('map')}
            Icon={MapIcon}
            label="Map"
          />
          <TabButton
            id="projects-tab-detail"
            ariaControls="projects-panel-detail"
            active={rightPanel === 'detail'}
            onClick={() => onSetRightPanel('detail')}
            Icon={FileIcon}
            label="Details"
            disabled={!activeProject}
          />
        </div>

        <div className="flex items-center gap-2">
          {filters.country && (
            <button
              type="button"
              onClick={() => onSetFilter('country', null)}
              className="inline-flex items-center gap-1.5 h-6 px-2 rounded-full bg-brand-100/70 text-brand-700 font-inter text-[10.5px] font-medium hover:bg-brand-100 transition-colors"
            >
              <span className="w-1 h-1 rounded-full bg-brand-500" />
              {filters.country}
              <IconWrapper Icon={XIcon} size={9} color={BRAND.primary700} aria-hidden={true} />
            </button>
          )}
          <span className="font-inter text-[10.5px] text-text-muted tabular-nums">
            {filteredCount.toLocaleString()} projects
          </span>
          {rightPanel === 'map' && (
            <button
              type="button"
              ref={expandTriggerRef}
              onClick={() => onSetMapFullscreen(true)}
              className="inline-flex items-center gap-1.5 h-6 px-2 rounded-full border border-border-ui bg-surface-card text-text-secondary font-inter text-[10.5px] font-medium hover:border-brand-500 hover:text-brand-700 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
              aria-label="Expand map to fullscreen"
            >
              <Maximize2 className="w-3 h-3" aria-hidden="true" />
              <span>Expand</span>
            </button>
          )}
        </div>
      </div>

      {/* Panel body — both panels stay mounted and switch via opacity */}
      <div className="flex-1 min-h-0 relative overflow-hidden">
        <div
          role="tabpanel"
          id="projects-panel-map"
          aria-labelledby="projects-tab-map"
          aria-hidden={rightPanel !== 'map'}
          {...(rightPanel !== 'map' && { inert: 'true' })}
          className={`absolute inset-0 transition-opacity duration-150 ease-out ${
            rightPanel === 'map' ? 'opacity-100' : 'opacity-0 pointer-events-none'
          }`}
        >
          <ErrorBoundary fallback={<MapFallback errorMessage="Failed to load the map. Please try again." />}>
            <Suspense fallback={<MapFallback />}>
              <ProjectMap
                projects={filtered}
                selectedCountry={filters.country ?? null}
                hoveredCountry={hoveredCountry}
                onSelectCountry={(c) => onSetFilter('country', c)}
                onHoverCountry={onHoverCountry}
                onSelectProject={(p) => {
                  onSelectProject(p);
                  onSetRightPanel('detail');
                }}
              />
            </Suspense>
          </ErrorBoundary>
        </div>
        <div
          role="tabpanel"
          id="projects-panel-detail"
          aria-labelledby="projects-tab-detail"
          aria-hidden={rightPanel !== 'detail'}
          {...(rightPanel !== 'detail' && { inert: 'true' })}
          className={`absolute inset-0 overflow-hidden transition-opacity duration-150 ease-out ${
            rightPanel === 'detail' ? 'opacity-100' : 'opacity-0 pointer-events-none'
          }`}
        >
          {activeProject ? (
            <ProjectDetailPanel project={activeProject} />
          ) : (
            <div className="w-full h-full flex items-center justify-center p-8">
              <p className="font-inter text-sm text-text-muted">
                Select a project to view details
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
    </div>
  );
};

export default InlineSplitView;
