import React from 'react';

// Layout constants for skeleton sizing
const HEADER_OFFSET_PX = 180; // Header + toolbar/margins offset for viewport height calculation
const MIN_SKELETON_HEIGHT_PX = 520; // Minimum height to ensure skeleton is visible on small screens

export const ProjectCardSkeleton: React.FC = () => (
  <div className="bg-surface-card rounded-2xl border border-border-ui shadow-xs p-5 animate-pulse">
    {/* Status + ID */}
    <div className="flex items-center gap-2 mb-3">
      <div className="h-1.5 w-1.5 bg-surface-subtle rounded-full" />
      <div className="h-3 w-14 bg-surface-subtle rounded" />
      <div className="h-3 w-8 bg-surface-subtle rounded" />
    </div>
    {/* Title */}
    <div className="h-4 w-full bg-surface-subtle rounded mb-1.5" />
    <div className="h-4 w-3/5 bg-surface-subtle rounded mb-3" />
    {/* Meta */}
    <div className="h-3 w-2/3 bg-surface-subtle rounded mb-auto" />
    {/* Credits */}
    <div className="mt-4 pt-3.5 border-t border-border-ui flex items-baseline gap-2">
      <div className="h-6 w-16 bg-surface-subtle rounded" />
      <div className="h-3 w-20 bg-surface-subtle rounded" />
    </div>
  </div>
);

interface ProjectSkeletonsProps {
  count?: number;
}

export const ProjectSkeletons: React.FC<ProjectSkeletonsProps> = ({ count = 9 }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {Array.from({ length: count }).map((_, i) => (
      <ProjectCardSkeleton key={i} />
    ))}
  </div>
);

/** Skeleton for the list item in the split-view layout */
export const ListItemSkeleton: React.FC = () => (
  <div className="animate-pulse border-b border-border-ui">
    <div className="px-4 py-3">
      <div className="flex items-center gap-1.5 mb-1">
        <div className="h-3.5 w-14 bg-surface-subtle rounded" />
        <div className="h-2.5 w-12 bg-surface-subtle rounded" />
        <div className="h-2.5 w-8 bg-surface-subtle rounded" />
      </div>
      <div className="h-3.5 w-full bg-surface-subtle rounded mb-1" />
      <div className="h-3.5 w-3/5 bg-surface-subtle rounded mb-2" />
      <div className="flex items-center gap-1.5 mb-2">
        <div className="h-4 w-20 bg-surface-subtle rounded" />
        <div className="h-2.5 w-16 bg-surface-subtle rounded" />
      </div>
      <div className="flex items-center gap-2">
        <div className="h-3 w-10 bg-surface-subtle rounded" />
        <div className="flex-1 h-1 bg-surface-subtle rounded-full" />
        <div className="h-2 w-14 bg-surface-subtle rounded" />
      </div>
    </div>
  </div>
);

/** KPI bar skeleton — matches compact summary strip */
export const KPISkeleton: React.FC = () => (
  <div className="bg-surface-card rounded-2xl border border-border-ui px-5 py-4 mb-4 animate-pulse">
    <div className="flex flex-col lg:flex-row lg:items-center gap-4 lg:gap-6">
      <div className="flex items-baseline gap-3">
        <div className="h-7 w-16 bg-surface-subtle rounded" />
        <div className="h-3 w-20 bg-surface-subtle rounded" />
      </div>
      <div className="hidden lg:block w-px h-6 bg-surface-subtle" />
      <div className="flex items-baseline gap-2">
        <div className="h-5 w-12 bg-surface-subtle rounded" />
        <div className="h-3 w-32 bg-surface-subtle rounded" />
      </div>
      <div className="hidden lg:block w-px h-6 bg-surface-subtle" />
      <div className="flex items-center gap-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="flex items-center gap-1.5">
            <div className="w-2 h-2 bg-surface-subtle rounded-full" />
            <div className="h-2.5 w-10 bg-surface-subtle rounded" />
          </div>
        ))}
      </div>
      <div className="hidden lg:block w-px h-6 bg-surface-subtle" />
      <div className="flex-1 min-w-[120px]">
        <div className="h-1.5 w-full bg-surface-subtle rounded-full" />
      </div>
    </div>
  </div>
);

/** Split-view loading skeleton */
export const SplitViewSkeleton: React.FC = () => (
  <div className="flex border border-border-ui rounded-2xl overflow-hidden bg-surface" style={{ height: `calc(100vh - ${HEADER_OFFSET_PX}px)`, minHeight: `${MIN_SKELETON_HEIGHT_PX}px` }}>
    <div className="w-[400px] border-r border-border-ui overflow-hidden flex-shrink-0">
      {Array.from({ length: 6 }).map((_, i) => (
        <ListItemSkeleton key={i} />
      ))}
    </div>
    <div className="flex-1 p-5 animate-pulse">
      <div className="flex items-center gap-1.5 mb-2">
        <div className="h-4 w-16 bg-surface-subtle rounded" />
        <div className="h-4 w-14 bg-surface-subtle rounded" />
      </div>
      <div className="h-5 w-3/4 bg-surface-subtle rounded mb-1.5" />
      <div className="h-3.5 w-20 bg-surface-subtle rounded mb-5" />
      <div className="h-5 w-16 bg-surface-subtle rounded mb-2" />
      <div className="h-2 w-full bg-surface-subtle rounded-full mb-2" />
      <div className="flex items-center gap-4 mb-6">
        <div className="h-2.5 w-20 bg-surface-subtle rounded" />
        <div className="h-2.5 w-24 bg-surface-subtle rounded" />
      </div>
      <div className="h-20 w-full bg-surface-subtle rounded-xl mb-4" />
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="flex justify-between">
            <div className="h-3 w-24 bg-surface-subtle rounded" />
            <div className="h-3 w-32 bg-surface-subtle rounded" />
          </div>
        ))}
      </div>
    </div>
  </div>
);
