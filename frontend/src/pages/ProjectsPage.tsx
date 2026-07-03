import React, { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { IconWrapper } from '@/components/icons/IconWrapper';
import ChevronLeftIcon from '@/assets/icons/chevron-left.svg?react';
import { ScrollToTop } from '@/components/ui/ScrollToTop';
import { ProjectFiltersV2 } from '@/components/projects/ProjectFiltersV2';
import { ProjectKPIs } from '@/components/projects/ProjectKPIs';
import { KPISkeleton, SplitViewSkeleton } from '@/components/projects/ProjectSkeletons';
import { NoResults, FetchError } from '@/components/projects/ProjectEmptyState';
import { ProjectAttribution } from '@/components/projects/ProjectAttribution';
import { CompareBar } from '@/components/projects/CompareBar';
import { ComparePanel } from '@/components/projects/ComparePanel';
import { MobileProjectDetail } from '@/components/projects/MobileProjectDetail';
import InlineSplitView from '@/components/projects/InlineSplitView';
import FullscreenOverlay from '@/components/projects/FullscreenOverlay';
import { useProjectsPageState } from '@/hooks/useProjectsPageState';
import type { VCMProject } from '@/types/project';

/**
 * Prefetch large data files needed by this page only.
 * Moved from index.html to avoid competing for bandwidth on other pages.
 */
if (typeof document !== 'undefined') {
  const prefetch = (href: string) => {
    if (document.querySelector(`link[rel="prefetch"][href="${href}"]`)) return;
    const link = document.createElement('link');
    link.rel = 'prefetch';
    link.href = href;
    link.as = 'fetch';
    document.head.appendChild(link);
  };
  prefetch('/data/projects-summary.json');
}

const ProjectsPage: React.FC = () => {
  const state = useProjectsPageState();
  const { setActiveProject, setRightPanel, setMobileDetailOpen, setShowCompare, setIsMapFullscreen } = state;

  // Handler for selecting a project in the inline split view
  const handleSelectProjectInline = useCallback(
    (p: VCMProject) => {
      setActiveProject(p);
      setRightPanel('detail');
      setMobileDetailOpen(true);
    },
    [setActiveProject, setRightPanel, setMobileDetailOpen],
  );

  return (
    <main className="bg-surface-page min-h-screen relative">
      <h1 className="sr-only">Explore VCM Projects — Voluntary Carbon Market Project Database</h1>

      <div className="container mx-auto px-4 md:px-12 lg:px-24 pt-16 pb-8 max-w-7xl">
        {/* Back link */}
        <nav aria-label="Breadcrumb navigation: Back to home" className="mb-4 md:mb-8">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base font-semibold"
          >
            <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5" />
            <span>Explore projects</span>
          </Link>
        </nav>

        {/* Comparison Panel - replaces KPIs and search when active */}
        {state.showCompare && state.selectedProjects.length === 2 ? (
          <ComparePanel
            projects={state.selectedProjects as [VCMProject, VCMProject]}
            onClose={() => setShowCompare(false)}
          />
        ) : (
          <>
            {/* KPI Bar */}
            {state.isLoading && <KPISkeleton />}
            {!state.isLoading && !state.isError && state.projects.length > 0 && (
              <ProjectKPIs projects={state.projects} filteredCount={state.filteredCount} />
            )}

            {/* Unified toolbar: search + filters */}
            {!state.isLoading && !state.isError && (
              <ProjectFiltersV2
                filters={state.filters}
                filterOptions={state.filterOptions}
                onFilterChange={state.setFilter}
                onClearAll={state.clearAllFilters}
                activeFilterCount={state.activeFilterCount}
                filteredCount={state.filteredCount}
                totalCount={state.totalCount}
                searchValue={state.query}
                onSearchChange={state.setQuery}
              />
            )}
          </>
        )}

        {/* Loading state */}
        {state.isLoading && <SplitViewSkeleton />}

        {/* Error state */}
        {state.isError && <FetchError onRetry={() => state.refetch()} />}

        {/* Empty state */}
        {!state.isLoading && !state.isError && state.filteredCount === 0 && (
          <NoResults onClearFilters={state.clearAllFilters} />
        )}

        {/* Split view: List + (Map | Detail) */}
        {!state.isLoading && !state.isError && state.filteredCount > 0 && (
          <InlineSplitView
            paginated={state.paginated}
            filtered={state.filtered}
            activeProject={state.activeProject}
            compareIds={state.compareIds}
            hoveredCountry={state.hoveredCountry}
            rightPanel={state.rightPanel}
            filters={state.filters}
            filteredCount={state.filteredCount}
            hasMore={state.hasMore}
            listRef={state.listRef}
            expandTriggerRef={state.expandTriggerRef}
            onSelectProject={handleSelectProjectInline}
            onToggleCompare={state.handleToggleCompare}
            onHoverCountry={state.setHoveredCountry}
            onSetRightPanel={state.setRightPanel}
            onSetFilter={state.setFilter}
            onListScroll={state.handleListScroll}
            onSetMapFullscreen={state.setIsMapFullscreen}
          />
        )}

        {/* Mobile detail — sheet-style overlay for smaller screens */}
        {state.activeProject && state.mobileDetailOpen && (
          <MobileProjectDetail
            project={state.activeProject}
            onClose={() => setMobileDetailOpen(false)}
          />
        )}

        {/* Attribution */}
        {state.dataVersion && state.dataLastUpdated && (
          <ProjectAttribution
            version={state.dataVersion}
            lastUpdated={state.dataLastUpdated}
          />
        )}
      </div>

      {/* Compare Bar */}
      <CompareBar
        selected={state.selectedProjects}
        onRemove={state.handleRemoveFromCompare}
        onCompare={state.handleCompare}
        onClear={state.handleClearCompare}
      />

      {/* Bottom padding for compare bar */}
      {state.compareIds.length > 0 && <div className="h-16" />}

      <ScrollToTop
        scrollContainerSelector="[data-project-list]"
        hasCompareBar={state.compareIds.length > 0}
      />

      {/* Fullscreen "Explore" overlay */}
      <FullscreenOverlay
        isMapFullscreen={state.isMapFullscreen}
        paginated={state.paginated}
        filtered={state.filtered}
        activeProject={state.activeProject}
        compareIds={state.compareIds}
        hoveredCountry={state.hoveredCountry}
        rightPanel={state.rightPanel}
        filters={state.filters}
        filteredCount={state.filteredCount}
        hasMore={state.hasMore}
        fullscreenDialogRef={state.fullscreenDialogRef}
        fullscreenExitBtnRef={state.fullscreenExitBtnRef}
        fullscreenListRef={state.fullscreenListRef}
        onSelectProjectInFullscreen={state.handleSelectProjectInFullscreen}
        onToggleCompare={state.handleToggleCompare}
        onHoverCountry={state.setHoveredCountry}
        onSetRightPanel={state.setRightPanel}
        onSetFilter={state.setFilter}
        onFullscreenListScroll={state.handleFullscreenListScroll}
        onExitFullscreen={() => setIsMapFullscreen(false)}
        searchValue={state.query}
        onSearchChange={state.setQuery}
      />
    </main>
  );
};

export default ProjectsPage;
