import React, { useMemo, useRef, useCallback, useEffect } from 'react';
import { AnimatePresence } from 'framer-motion';
import { ComposableMap, ZoomableGroup } from 'react-simple-maps';
import type { VCMProject } from '@/types/project';
import { aggregateByCountry, type CountryAggregate } from '@/lib/mapAggregation';
import { DATA_TO_TOPO_NAME, MANUAL_CENTROIDS } from '@/lib/countryCoordinates';
import { useWorldData } from '@/hooks/useWorldData';
import { useMapPosition } from '@/hooks/useMapPosition';
import { useMapTooltip } from '@/hooks/useMapTooltip';
import { MapGeographies } from '@/components/projects/MapGeographies';
import { MapMarkers } from '@/components/projects/MapMarkers';
import { MapSelectionChip } from '@/components/projects/MapSelectionChip';
import { MapCountryTooltip } from '@/components/projects/MapCountryTooltip';
import { MapLegend } from '@/components/projects/MapLegend';
import { MapZoomControls } from '@/components/projects/MapZoomControls';
import {
  MAP_WIDTH,
  MAP_HEIGHT,
  TOP_N_MARKERS,
  BUBBLE_MIN_R,
  BUBBLE_MAX_R,
  DEFAULT_CENTER,
  FOCUS_ZOOM,
} from '@/lib/mapConstants';

interface ProjectMapProps {
  projects: VCMProject[];
  selectedCountry: string | null;
  hoveredCountry: string | null;
  onSelectCountry: (country: string | null) => void;
  onHoverCountry: (country: string | null) => void;
  onSelectProject: (project: VCMProject) => void;
  className?: string;
}

// Wheel-zoom policy: require Ctrl/Cmd modifier (Google Maps convention).
// Why: the map lives inside a scrollable page. Capturing plain wheel events
// for zoom made the page un-scrollable while the cursor hovered over the
// map (especially after the map zoomed in on a country click — every
// subsequent wheel event hit the map and was preventDefault'd). With this
// filter d3-zoom only engages on Ctrl/Cmd + wheel, so plain wheel bubbles
// to the browser and scrolls the page as expected. Users can still zoom
// precisely via the +/- buttons in MapZoomControls.
//
// Filter semantics match d3-zoom's own filterFunc contract: return true to
// let the zoom behavior handle the event, false to ignore it.
function filterZoomEvent(e: Event): boolean {
  const mouseEvent = e as MouseEvent;
  if (typeof mouseEvent.button === 'number' && mouseEvent.button > 0) {
    return false;
  }
  if (e.type === 'wheel') {
    const we = e as WheelEvent;
    return we.ctrlKey || we.metaKey;
  }
  return true;
}

export const ProjectMap: React.FC<ProjectMapProps> = ({
  projects,
  selectedCountry,
  hoveredCountry,
  onSelectCountry,
  onHoverCountry,
  onSelectProject,
  className = '',
}) => {
  const { data: world, isLoading } = useWorldData();
  const {
    position,
    setPosition,
    positionRef,
    animateTo,
    zoomIn,
    zoomOut,
    reset,
    cancelAnim,
  } = useMapPosition();

  const {
    containerRef,
    tooltip,
    setTooltip,
    showTooltip,
    scheduleHide,
    handleTooltipEnter,
    handleTooltipLeave,
  } = useMapTooltip(onHoverCountry);

  // Aggregates
  const aggregates = useMemo(() => aggregateByCountry(projects), [projects]);

  const aggByCountry = useMemo(() => {
    const m = new Map<string, CountryAggregate>();
    for (const a of aggregates) m.set(a.country, a);
    return m;
  }, [aggregates]);

  const aggByTopoName = useMemo(() => {
    const m = new Map<string, CountryAggregate>();
    for (const a of aggregates) {
      const topoName = DATA_TO_TOPO_NAME[a.country] ?? a.country;
      m.set(topoName, a);
    }
    return m;
  }, [aggregates]);

  // Top-N countries get a scope-coloured dot. Square-root scaling so that
  // very heavy producers don't swamp the medium ones.
  const topMarkers = useMemo(() => {
    if (!world) return [] as { agg: CountryAggregate; coords: [number, number]; r: number }[];
    const top = aggregates.slice(0, TOP_N_MARKERS);
    const out: { agg: CountryAggregate; coords: [number, number]; r: number }[] = [];
    const maxCount = top[0]?.projectCount ?? 1;
    for (const agg of top) {
      const topoName = DATA_TO_TOPO_NAME[agg.country] ?? agg.country;
      const centroid =
        MANUAL_CENTROIDS[agg.country] ?? world.centroidByTopoName.get(topoName);
      if (!centroid) continue;
      const t = Math.sqrt(Math.max(agg.projectCount, 1) / maxCount);
      const r = BUBBLE_MIN_R + t * (BUBBLE_MAX_R - BUBBLE_MIN_R);
      out.push({ agg, coords: centroid, r });
    }
    return out;
  }, [world, aggregates]);

  // Interaction handlers
  const clearFocus = useCallback(() => {
    onSelectCountry(null);
    animateTo({ coordinates: DEFAULT_CENTER, zoom: 1 });
  }, [onSelectCountry, animateTo]);

  const handleSelect = useCallback(
    (agg: CountryAggregate) => {
      if (selectedCountry === agg.country) {
        clearFocus();
        return;
      }
      onSelectCountry(agg.country);
    },
    [selectedCountry, onSelectCountry, clearFocus],
  );

  const handleBackgroundClick = useCallback(() => {
    if (selectedCountry) clearFocus();
  }, [selectedCountry, clearFocus]);

  // When selectedCountry changes (from click OR external list click), snap
  // to a focused view: centered on the country, zoomed in to FOCUS_ZOOM.
  // prevSelectedRef is only updated AFTER the zoom is actually applied so
  // that a pre-selected country still triggers the zoom once world loads.
  const prevSelectedRef = useRef<string | null>(null);
  useEffect(() => {
    if (selectedCountry === prevSelectedRef.current) return;
    if (!selectedCountry) {
      animateTo({ coordinates: DEFAULT_CENTER, zoom: 1 });
      prevSelectedRef.current = null;
      return;
    }
    if (!world) return; // don't update prevSelectedRef — retry when world loads
    const topoName = DATA_TO_TOPO_NAME[selectedCountry] ?? selectedCountry;
    const c =
      MANUAL_CENTROIDS[selectedCountry] ?? world.centroidByTopoName.get(topoName);
    if (c) {
      animateTo({ coordinates: c, zoom: FOCUS_ZOOM });
      prevSelectedRef.current = selectedCountry;
    }
  }, [selectedCountry, world, animateTo]);

  return (
    <div
      ref={containerRef}
      onClick={handleBackgroundClick}
      // touch-pan-y (not touch-none) so the user can scroll the page
      // vertically with a single finger swipe over the map on touch
      // devices. Country taps still work because `tap` doesn't require
      // touch-action. Map pan on touch is disabled by default; use the
      // +/- controls or tap a country to focus/zoom.
      className={`relative w-full h-full overflow-hidden touch-pan-y bg-surface-page ${className}`}
    >
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="font-inter text-xs text-text-muted animate-pulse">
            Loading world map…
          </div>
        </div>
      )}

      {world && (
        <ComposableMap
          projection="geoMercator"
          projectionConfig={{ scale: 120 }}
          width={MAP_WIDTH}
          height={MAP_HEIGHT}
          style={{ width: '100%', height: '100%' }}
        >
          <ZoomableGroup
            zoom={position.zoom}
            center={position.coordinates}
            onMoveStart={cancelAnim}
            onMoveEnd={(p) => {
              positionRef.current = p;
              setPosition(p);
            }}
            minZoom={1}
            maxZoom={8}
            // TODO: Remove cast when @types/react-simple-maps fixes the filter signature.
            // Current @types/react-simple-maps@3.0.6 declares filter as `(element: SVGElement) => boolean`,
            // but d3-zoom's filterFunc contract is `(event: Event) => boolean`. The types package
            // has not been updated to match d3-zoom@3.0.0. See: https://github.com/DefinitelyTyped/DefinitelyTyped
            filterZoomEvent={filterZoomEvent as unknown as (element: SVGElement) => boolean}
            translateExtent={[
              [-200, -80],
              [MAP_WIDTH + 200, MAP_HEIGHT + 80],
            ]}
          >
            <MapGeographies
              topology={world.topology}
              disputedTopology={world.disputedTopology}
              aggByTopoName={aggByTopoName}
              selectedCountry={selectedCountry}
              hoveredCountry={hoveredCountry}
              showTooltip={showTooltip}
              scheduleHide={scheduleHide}
              onSelect={handleSelect}
            />

            <MapMarkers
              markers={topMarkers}
              zoom={position.zoom}
              selectedCountry={selectedCountry}
              hoveredCountry={hoveredCountry}
              showTooltip={showTooltip}
              scheduleHide={scheduleHide}
              onSelect={handleSelect}
            />
          </ZoomableGroup>
        </ComposableMap>
      )}

      <MapLegend aggregates={aggregates} totalProjects={projects.length} />
      <MapZoomControls onZoomIn={zoomIn} onZoomOut={zoomOut} onReset={reset} />

      <MapSelectionChip
        selectedCountry={selectedCountry}
        aggByCountry={aggByCountry}
        onClear={clearFocus}
      />

      <AnimatePresence>
        {tooltip && (
          <MapCountryTooltip
            agg={tooltip.agg}
            onProjectClick={(p) => {
              setTooltip(null);
              onSelectProject(p);
            }}
            onEnter={handleTooltipEnter}
            onLeave={handleTooltipLeave}
          />
        )}
      </AnimatePresence>
    </div>
  );
};
