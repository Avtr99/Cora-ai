import React, { Suspense, lazy, useState, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Minimize2, Search, X } from 'lucide-react';
import { useDebounce } from '@/hooks/useDebounce';
import { IconWrapper } from '@/components/icons/IconWrapper';
import XIcon from '@/assets/icons/x.svg?react';
import { BRAND } from '@/lib/colors';
import MapIcon from '@/assets/icons/map.svg?react';
import FileIcon from '@/assets/icons/file.svg?react';
import { ProjectListItem } from '@/components/projects/ProjectListItem';
import { ProjectDetailPanel } from '@/components/projects/ProjectDetailPanel';
import TabButton from '@/components/projects/TabButton';
import MapFallback from '@/components/projects/MapFallback';
import type { VCMProject, ProjectFilterKey } from '@/types/project';
import type { RightPanel } from '@/hooks/useProjectsPageState';

const ProjectMap = lazy(() =>
  import('@/components/projects/ProjectMap').then((m) => ({ default: m.ProjectMap })),
);

/** Reusable detail panel content with empty state fallback */
const DetailPanelContent: React.FC<{ activeProject: VCMProject | null }> = ({ activeProject }) =>
  activeProject ? (
    <ProjectDetailPanel project={activeProject} />
  ) : (
    <div className="w-full h-full flex items-center justify-center p-8">
      <p className="font-inter text-sm text-text-muted">
        Select a project to view details
      </p>
    </div>
  );

interface FullscreenOverlayProps {
  isMapFullscreen: boolean;
  paginated: VCMProject[];
  filtered: VCMProject[];
  activeProject: VCMProject | null;
  compareIds: string[];
  hoveredCountry: string | null;
  rightPanel: RightPanel;
  filters: Partial<Record<ProjectFilterKey, string>>;
  filteredCount: number;
  hasMore: boolean;
  fullscreenDialogRef: React.RefObject<HTMLDivElement | null>;
  fullscreenExitBtnRef: React.RefObject<HTMLButtonElement | null>;
  fullscreenListRef: React.RefObject<HTMLDivElement | null>;
  onSelectProjectInFullscreen: (p: VCMProject) => void;
  onToggleCompare: (id: string) => void;
  onHoverCountry: (c: string | null) => void;
  onSetRightPanel: (panel: RightPanel) => void;
  onSetFilter: (key: string, value: string | null) => void;
  onFullscreenListScroll: () => void;
  onExitFullscreen: () => void;
  searchValue: string;
  onSearchChange: (value: string) => void;
}

const FullscreenOverlay: React.FC<FullscreenOverlayProps> = ({
  isMapFullscreen,
  paginated,
  filtered,
  activeProject,
  compareIds,
  hoveredCountry,
  rightPanel,
  filters,
  filteredCount,
  hasMore,
  fullscreenDialogRef,
  fullscreenExitBtnRef,
  fullscreenListRef,
  onSelectProjectInFullscreen,
  onToggleCompare,
  onHoverCountry,
  onSetRightPanel,
  onSetFilter,
  onFullscreenListScroll,
  onExitFullscreen,
  searchValue,
  onSearchChange,
}) => {
  const [localSearch, setLocalSearch] = useState(searchValue);
  const debouncedSearch = useDebounce(onSearchChange, 250);

  useEffect(() => {
    setLocalSearch(searchValue);
  }, [searchValue]);

  const handleSearchInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value;
    setLocalSearch(v);
    debouncedSearch(v);
  };

  const handleClearSearch = () => {
    debouncedSearch.cancel();
    setLocalSearch('');
    onSearchChange('');
  };

  return (
  <AnimatePresence>
    {isMapFullscreen && (
      <motion.div
        key="fullscreen-explore"
        ref={fullscreenDialogRef}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.15, ease: 'easeOut' }}
        className="fixed inset-0 z-[55] bg-surface-card flex flex-col"
        role="dialog"
        aria-modal="true"
        aria-label="Fullscreen project explorer"
      >
        {/* ── Top bar ──────────────────────────────────────────── */}
        <div className="flex items-center justify-between gap-2 md:gap-3 px-3 md:px-4 h-12 border-b border-border-ui bg-surface-base flex-shrink-0">
          <div className="flex items-center gap-2 md:gap-3 min-w-0">
            <div
              className="inline-flex items-center bg-surface-card border border-border-ui rounded-full p-0.5 overflow-hidden"
              role="tablist"
              aria-label="Fullscreen explorer panes"
            >
              {/* Desktop tabs */}
              <div className="hidden lg:flex">
                <TabButton
                  id="fs-tab-map-desktop"
                  ariaControls="fs-panel-map"
                  layoutId="fs-pane-pill-desktop"
                  active={rightPanel === 'map'}
                  onClick={() => onSetRightPanel('map')}
                  Icon={MapIcon}
                  label="Map"
                />
                <TabButton
                  id="fs-tab-detail-desktop"
                  ariaControls="fs-panel-detail-desktop"
                  layoutId="fs-pane-pill-desktop"
                  active={rightPanel === 'detail'}
                  onClick={() => onSetRightPanel('detail')}
                  Icon={FileIcon}
                  label="Details"
                  disabled={!activeProject}
                />
              </div>
              {/* Mobile tabs */}
              <div className="lg:hidden flex">
                <TabButton
                  id="fs-tab-map-mobile"
                  ariaControls="fs-panel-map"
                  layoutId="fs-pane-pill-mobile"
                  active={rightPanel === 'map'}
                  onClick={() => onSetRightPanel('map')}
                  Icon={MapIcon}
                  label="Map"
                />
                <TabButton
                  id="fs-tab-detail-mobile"
                  ariaControls="fs-panel-detail-mobile"
                  layoutId="fs-pane-pill-mobile"
                  active={rightPanel === 'detail'}
                  onClick={() => onSetRightPanel('detail')}
                  Icon={FileIcon}
                  label="Details"
                  disabled={!activeProject}
                />
              </div>
            </div>
          </div>

          {/* Center: Search */}
          <div className="hidden md:flex flex-1 px-4 min-w-0">
            <div className="relative w-full max-w-[520px]">
              <Search
                className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-text-muted pointer-events-none"
                aria-hidden="true"
              />
              <input
                type="text"
                value={localSearch}
                onChange={handleSearchInput}
                placeholder="Search projects..."
                className="w-full h-7 pl-7 pr-7 font-inter text-[11.5px] text-text-primary placeholder:text-text-muted bg-surface-card border border-border-ui rounded-lg focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 transition-shadow"
                aria-label="Search projects"
              />
              {localSearch && (
                <button
                  type="button"
                  onClick={handleClearSearch}
                  className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-text-muted hover:text-text-primary transition-colors"
                  aria-label="Clear search"
                >
                  <X className="h-3 w-3" />
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2 flex-shrink-0">
            {filters.country && (
              <button
                type="button"
                onClick={() => onSetFilter('country', null)}
                className="hidden sm:inline-flex items-center gap-1.5 h-6 px-2 rounded-full bg-brand-100/70 text-brand-700 font-inter text-[10.5px] font-medium hover:bg-brand-100 transition-colors"
                aria-label={`Clear ${filters.country} filter`}
              >
                <span className="w-1 h-1 rounded-full bg-brand-500" />
                {filters.country}
                <IconWrapper Icon={XIcon} size={9} color={BRAND.primary700} aria-hidden={true} />
              </button>
            )}
            <span className="font-inter text-[10.5px] md:text-[11.5px] text-text-muted tabular-nums">
              {filteredCount.toLocaleString()} projects
            </span>

            {/* Exit */}
            <button
              type="button"
              ref={fullscreenExitBtnRef}
              onClick={onExitFullscreen}
              className="inline-flex items-center gap-1.5 h-8 px-2.5 md:px-3 rounded-full border border-border-ui bg-surface-card text-text-secondary font-inter text-[11.5px] md:text-xs font-medium hover:border-brand-500 hover:text-brand-700 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 flex-shrink-0"
              aria-label="Exit fullscreen explorer"
            >
              <Minimize2 className="w-3.5 h-3.5" aria-hidden="true" />
              <span className="hidden sm:inline">Exit fullscreen</span>
              <span className="sm:hidden">Exit</span>
            </button>
          </div>
        </div>

        {/* ── Body: list + right panel ────────────────────────── */}
        <div className="flex-1 min-h-0 flex">
          {/* List — visible on md+ alongside the right panel */}
          <div
            id="fs-panel-list"
            ref={fullscreenListRef}
            onScroll={onFullscreenListScroll}
            className="hidden md:flex md:w-[280px] lg:w-[340px] md:flex-shrink-0 w-full flex-col overflow-y-auto divide-y divide-surface-subtle md:border-r border-border-ui"
            role="list"
            aria-label="Project list"
          >
            {paginated.map((project) => (
              <ProjectListItem
                key={project.id}
                project={project}
                isActive={activeProject?.id === project.id}
                isSelected={compareIds.includes(project.id)}
                onSelect={onSelectProjectInFullscreen}
                onToggleCompare={onToggleCompare}
                compareDisabled={compareIds.length >= 2}
                isCountryHighlighted={hoveredCountry === project.country}
                onMouseEnterRow={(p) => onHoverCountry(p.country || null)}
                onMouseLeaveRow={() => onHoverCountry(null)}
                hideCompare={true}
              />
            ))}
            {hasMore && (
              <div className="px-4 py-3 text-center">
                <span className="font-inter text-xs text-text-muted">
                  Scroll for more…
                </span>
              </div>
            )}
          </div>

          {/* Right area: Details (lg+) + Map — left-to-right reading flow */}
          <div className="flex flex-1 min-w-0 min-h-0 bg-surface-card relative overflow-hidden">
            {/* Desktop lg+: Details panel between list and map */}
            <AnimatePresence>
              {rightPanel === 'detail' && (
                <motion.div
                  key="fs-detail-panel-desktop"
                  role="tabpanel"
                  id="fs-panel-detail-desktop"
                  aria-labelledby="fs-tab-detail-desktop"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  className="hidden lg:flex w-[360px] xl:w-[420px] flex-shrink-0 border-r border-border-ui bg-surface-card overflow-hidden z-10 flex-col"
                >
                  <DetailPanelContent activeProject={activeProject} />
                </motion.div>
              )}
            </AnimatePresence>

            {/* Map — fills remaining space */}
            <div
              id="fs-panel-map"
              role="tabpanel"
              aria-label="Map view"
              className="flex-1 min-w-0 relative overflow-hidden"
            >
              {/* Single shared ProjectMap instance */}
              <div className="absolute inset-0">
                <Suspense fallback={<MapFallback />}>
                  <ProjectMap
                    projects={filtered}
                    selectedCountry={filters.country ?? null}
                    hoveredCountry={hoveredCountry}
                    onSelectCountry={(c) => onSetFilter('country', c)}
                    onHoverCountry={onHoverCountry}
                    onSelectProject={onSelectProjectInFullscreen}
                  />
                </Suspense>
              </div>

              {/* Mobile / Tablet (< lg): detail panel overlays map */}
              <div
                role="tabpanel"
                id="fs-panel-detail-mobile"
                aria-labelledby="fs-tab-detail-mobile"
                aria-hidden={rightPanel !== 'detail'}
                className={`lg:hidden absolute inset-0 overflow-hidden bg-surface-card transition-opacity duration-150 ease-out ${
                  rightPanel === 'detail' ? 'opacity-100 z-10' : 'opacity-0 pointer-events-none'
                }`}
              >
                <DetailPanelContent activeProject={activeProject} />
              </div>
            </div>
          </div>
        </div>
      </motion.div>
    )}
  </AnimatePresence>
);
};

export default FullscreenOverlay;
