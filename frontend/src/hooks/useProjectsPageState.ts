import { useState, useCallback, useRef, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useFocusTrap } from '@/hooks/useFocusTrap';
import type { ProjectsData, VCMProject } from '@/types/project';
import { useProjectFilters } from '@/hooks/useProjectFilters';
import { PROJECT_DATA_VERSION } from '@/generated/projectVersion';

export type RightPanel = 'map' | 'detail';

async function fetchProjects(): Promise<ProjectsData> {
  const res = await fetch('/data/projects-summary.json');
  if (!res.ok) throw new Error(`Failed to fetch projects: ${res.status}`);
  return res.json();
}

export interface ProjectsPageState {
  // Data
  projects: VCMProject[];
  isLoading: boolean;
  isError: boolean;
  refetch: () => void;

  // Filters
  query: string;
  setQuery: (q: string) => void;
  filters: ReturnType<typeof useProjectFilters>['filters'];
  setFilter: ReturnType<typeof useProjectFilters>['setFilter'];
  clearAllFilters: () => void;
  activeFilterCount: number;
  filtered: VCMProject[];
  paginated: VCMProject[];
  page: number;
  setPage: (p: number | ((prev: number) => number)) => void;
  hasMore: boolean;
  totalCount: number;
  filteredCount: number;
  filterOptions: ReturnType<typeof useProjectFilters>['filterOptions'];

  // Right panel
  rightPanel: RightPanel;
  setRightPanel: (panel: RightPanel) => void;

  // Compare
  compareIds: string[];
  selectedProjects: VCMProject[];
  showCompare: boolean;
  handleToggleCompare: (id: string) => void;
  handleCompare: () => void;
  handleClearCompare: () => void;
  handleRemoveFromCompare: (id: string) => void;
  setShowCompare: (show: boolean) => void;

  // Detail
  activeProject: VCMProject | null;
  setActiveProject: (p: VCMProject | null) => void;
  mobileDetailOpen: boolean;
  setMobileDetailOpen: (open: boolean) => void;

  // Hover highlight
  hoveredCountry: string | null;
  setHoveredCountry: (c: string | null) => void;

  // Fullscreen
  isMapFullscreen: boolean;
  setIsMapFullscreen: (fs: boolean) => void;
  fullscreenDialogRef: React.RefObject<HTMLDivElement | null>;
  fullscreenExitBtnRef: React.RefObject<HTMLButtonElement | null>;
  expandTriggerRef: React.RefObject<HTMLButtonElement | null>;

  // Scroll refs
  listRef: React.RefObject<HTMLDivElement | null>;
  fullscreenListRef: React.RefObject<HTMLDivElement | null>;

  // Handlers
  handleListScroll: () => void;
  handleFullscreenListScroll: () => void;
  handleSelectProjectInFullscreen: (p: VCMProject) => void;

  // Data version info
  dataVersion: string | undefined;
  dataLastUpdated: string | undefined;
}

export function useProjectsPageState(): ProjectsPageState {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['vcm-projects', PROJECT_DATA_VERSION],
    queryFn: fetchProjects,
    staleTime: Infinity,
  });

  const projects = data?.projects ?? [];

  const {
    query,
    setQuery,
    filters,
    setFilter,
    clearAllFilters,
    activeFilterCount,
    filtered,
    paginated,
    page,
    setPage,
    hasMore,
    totalCount,
    filteredCount,
    filterOptions,
  } = useProjectFilters(projects);

  // Right-panel view (Map is the default — exploration first, detail on click)
  const [searchParams, setSearchParams] = useSearchParams();
  const panelParam = searchParams.get('panel');
  const rightPanel: RightPanel = panelParam === 'detail' ? 'detail' : 'map';
  const setRightPanel = useCallback((panel: RightPanel) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      if (panel === 'map') next.delete('panel');
      else next.set('panel', panel);
      return next;
    }, { replace: true });
  }, [setSearchParams]);

  // Compare state
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [showCompare, setShowCompare] = useState(false);

  // Detail panel state
  const [activeProject, setActiveProject] = useState<VCMProject | null>(null);
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);

  // Map ↔ list two-way hover highlight
  const [hoveredCountry, setHoveredCountry] = useState<string | null>(null);

  // Fullscreen "Explore" mode
  const [isMapFullscreen, setIsMapFullscreen] = useState(false);

  // Refs for focus management in fullscreen dialog
  const fullscreenDialogRef = useRef<HTMLDivElement>(null);
  const fullscreenExitBtnRef = useRef<HTMLButtonElement>(null);
  const expandTriggerRef = useRef<HTMLButtonElement>(null);

  // Focus trap for fullscreen dialog
  useFocusTrap({
    isActive: isMapFullscreen,
    containerRef: fullscreenDialogRef,
    initialFocusRef: fullscreenExitBtnRef,
    restoreFocusRef: expandTriggerRef,
  });

  // Esc to exit fullscreen
  useEffect(() => {
    if (!isMapFullscreen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsMapFullscreen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [isMapFullscreen]);

  // Lock body scroll while fullscreen
  useEffect(() => {
    if (!isMapFullscreen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, [isMapFullscreen]);

  // Clear stale hover when the filtered list changes
  useEffect(() => {
    setHoveredCountry(null);
  }, [filtered]);

  // List scroll refs
  const listRef = useRef<HTMLDivElement>(null);
  const fullscreenListRef = useRef<HTMLDivElement>(null);
  const pageRef = useRef(page);

  // Keep pageRef in sync with page
  useEffect(() => {
    pageRef.current = page;
  }, [page]);

  const selectedProjects = compareIds
    .map((id) => projects.find((p) => p.id === id))
    .filter(Boolean) as VCMProject[];

  const handleToggleCompare = useCallback((id: string) => {
    setCompareIds((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 2) return prev;
      return [...prev, id];
    });
    setShowCompare(false);
  }, []);

  const handleCompare = useCallback(() => {
    if (selectedProjects.length === 2) {
      setShowCompare(true);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }, [selectedProjects.length]);

  const handleClearCompare = useCallback(() => {
    setCompareIds([]);
    setShowCompare(false);
  }, []);

  const handleRemoveFromCompare = useCallback((id: string) => {
    setCompareIds((prev) => prev.filter((x) => x !== id));
    setShowCompare(false);
  }, []);

  // Auto-select first project when data loads or filters change
  useEffect(() => {
    if (paginated.length > 0 && !activeProject) {
      setActiveProject(paginated[0]);
    }
  }, [paginated, activeProject]);

  // Reset active project when filters change and active is no longer in filtered set
  useEffect(() => {
    if (activeProject && filtered.length > 0) {
      const stillVisible = filtered.some((p) => p.id === activeProject.id);
      if (!stillVisible) {
        setActiveProject(paginated[0] || null);
      }
    }
    if (filtered.length === 0) {
      setActiveProject(null);
    }
  }, [filtered, activeProject, paginated]);

  // Reset list scroll to top whenever the country filter changes
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = 0;
  }, [filters.country]);

  // Infinite scroll within the list panel
  const handleListScroll = useCallback(() => {
    if (!listRef.current || !hasMore) return;
    const { scrollTop, scrollHeight, clientHeight } = listRef.current;
    if (scrollHeight - scrollTop - clientHeight < 200) {
      setPage(pageRef.current + 1);
    }
  }, [hasMore, setPage]);

  // Same infinite-scroll behaviour, targeting the fullscreen list
  const handleFullscreenListScroll = useCallback(() => {
    if (!fullscreenListRef.current || !hasMore) return;
    const { scrollTop, scrollHeight, clientHeight } = fullscreenListRef.current;
    if (scrollHeight - scrollTop - clientHeight < 200) {
      setPage(pageRef.current + 1);
    }
  }, [hasMore, setPage]);

  // Clicking a project in the fullscreen list/map should reveal its detail
  // INSIDE the overlay
  const handleSelectProjectInFullscreen = useCallback((p: VCMProject) => {
    setActiveProject(p);
    setRightPanel('detail');
  }, [setRightPanel]);

  return {
    // Data
    projects,
    isLoading,
    isError,
    refetch,

    // Filters
    query,
    setQuery,
    filters,
    setFilter,
    clearAllFilters,
    activeFilterCount,
    filtered,
    paginated,
    page,
    setPage,
    hasMore,
    totalCount,
    filteredCount,
    filterOptions,

    // Right panel
    rightPanel,
    setRightPanel,

    // Compare
    compareIds,
    selectedProjects,
    showCompare,
    handleToggleCompare,
    handleCompare,
    handleClearCompare,
    handleRemoveFromCompare,
    setShowCompare,

    // Detail
    activeProject,
    setActiveProject,
    mobileDetailOpen,
    setMobileDetailOpen,

    // Hover highlight
    hoveredCountry,
    setHoveredCountry,

    // Fullscreen
    isMapFullscreen,
    setIsMapFullscreen,
    fullscreenDialogRef,
    fullscreenExitBtnRef,
    expandTriggerRef,

    // Scroll refs
    listRef,
    fullscreenListRef,

    // Handlers
    handleListScroll,
    handleFullscreenListScroll,
    handleSelectProjectInFullscreen,

    // Data version info
    dataVersion: data?.version,
    dataLastUpdated: data?.lastUpdated,
  };
}
