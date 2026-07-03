import React from 'react';
import { Geographies, Geography } from 'react-simple-maps';
import type { CountryAggregate } from '@/lib/mapAggregation';
import {
  DISPUTED_REGION_NAMES,
  DISPUTED_STROKE_DEFAULT,
  DISPUTED_STROKE_HOVER,
  DISPUTED_STROKE_HOVER_SELECTED,
  DISPUTED_STROKE_SELECTED,
  getChoroplethFill,
  HOVER_FILL_DATA,
  HOVER_FILL_EMPTY,
  HOVER_STROKE,
  NO_DATA_FILL,
  SELECTED_FILL,
  SELECTED_STROKE,
} from '@/lib/mapConstants';
import { NEUTRAL } from '@/lib/colors';

interface MapGeographiesProps {
  topology: unknown;
  disputedTopology: unknown;
  aggByTopoName: Map<string, CountryAggregate>;
  selectedCountry: string | null;
  hoveredCountry: string | null;
  showTooltip: (agg: CountryAggregate) => void;
  scheduleHide: () => void;
  onSelect: (agg: CountryAggregate) => void;
}

export const MapGeographies: React.FC<MapGeographiesProps> = ({
  topology,
  disputedTopology,
  aggByTopoName,
  selectedCountry,
  hoveredCountry,
  showTooltip,
  scheduleHide,
  onSelect,
}) => {

  return (
    <>
      {/* Main country polygons */}
      <Geographies geography={topology}>
        {({ geographies }) =>
          geographies.map((geo) => {
            const name = geo.properties.name as string;
            const agg = aggByTopoName.get(name);
            const count = agg?.projectCount ?? 0;

            const dataCountry = agg?.country ?? null;
            const isSelected = selectedCountry !== null && dataCountry === selectedCountry;
            const isHovered = hoveredCountry !== null && dataCountry === hoveredCountry;

            const baseFill = getChoroplethFill(count);
            const hoverFill = count === 0 ? HOVER_FILL_EMPTY : HOVER_FILL_DATA;

            return (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                vectorEffect="non-scaling-stroke"
                style={{
                  default: {
                    fill: isSelected ? SELECTED_FILL : isHovered ? hoverFill : baseFill,
                    stroke: isSelected ? SELECTED_STROKE : isHovered ? HOVER_STROKE : NEUTRAL[150],
                    strokeWidth: isSelected ? 1.0 : 0.6,
                    outline: 'none',
                    transition:
                      'fill 180ms ease-out, stroke 180ms ease-out, stroke-width 180ms ease-out',
                  },
                  hover: {
                    fill: isSelected ? SELECTED_FILL : hoverFill,
                    stroke: isSelected ? SELECTED_STROKE : HOVER_STROKE,
                    strokeWidth: isSelected ? 1.0 : 0.6,
                    outline: 'none',
                    cursor: count > 0 ? 'pointer' : 'default',
                  },
                  pressed: {
                    fill: SELECTED_FILL,
                    stroke: SELECTED_STROKE,
                    strokeWidth: 1.0,
                    outline: 'none',
                  },
                }}
                onMouseEnter={() => {
                  if (!agg) return;
                  showTooltip(agg);
                }}
                onMouseLeave={() => {
                  scheduleHide();
                }}
                onClick={(e) => {
                  if (!agg) return;
                  e.stopPropagation();
                  onSelect(agg);
                }}
                onKeyDown={(e) => {
                  if (!agg) return;
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelect(agg);
                  }
                }}
                tabIndex={count > 0 ? 0 : -1}
                role={count > 0 ? 'button' : undefined}
                aria-label={count > 0 ? `Select ${name}, ${count} projects` : undefined}
              />
            );
          })
        }
      </Geographies>

      {/* Disputed Areas Overlay (Indian Perspective + Google Maps dotted style) */}
      <Geographies geography={disputedTopology}>
        {({ geographies }) =>
          geographies.map((geo) => {
            const brkName = geo.properties.BRK_NAME as string;
            const originalName = geo.properties.NAME as string;

            if (brkName === 'Junagadh and Manavadar' || brkName === 'Arunachal Pradesh') return null; // Excluded

            const isIndianClaim = DISPUTED_REGION_NAMES.includes(brkName);
            const mappedCountry = isIndianClaim ? 'India' : originalName;
            const agg = aggByTopoName.get(mappedCountry);
            const count = agg?.projectCount ?? 0;

            const dataCountry = agg?.country ?? null;
            const isSelected = selectedCountry !== null && dataCountry === selectedCountry;
            const isHovered = hoveredCountry !== null && dataCountry === hoveredCountry;

            const baseFill = getChoroplethFill(count);
            const hoverFill = count === 0 ? HOVER_FILL_EMPTY : HOVER_FILL_DATA;
            const disputedStroke = isSelected ? DISPUTED_STROKE_SELECTED : DISPUTED_STROKE_DEFAULT;

            return (
              <Geography
                key={`disp-${geo.rsmKey}`}
                geography={geo}
                vectorEffect="non-scaling-stroke"
                style={{
                  default: {
                    fill: isSelected ? SELECTED_FILL : isHovered ? hoverFill : baseFill,
                    stroke: disputedStroke,
                    strokeWidth: 0.7,
                    strokeDasharray: '2 3',
                    strokeLinecap: 'round',
                    outline: 'none',
                    transition: 'fill 180ms ease-out, stroke 180ms ease-out',
                  },
                  hover: {
                    fill: isSelected ? SELECTED_FILL : hoverFill,
                    stroke: isSelected ? DISPUTED_STROKE_HOVER_SELECTED : DISPUTED_STROKE_HOVER,
                    strokeWidth: 0.8,
                    strokeDasharray: '2 3',
                    outline: 'none',
                    cursor: count > 0 ? 'pointer' : 'default',
                  },
                  pressed: {
                    fill: SELECTED_FILL,
                    stroke: DISPUTED_STROKE_HOVER_SELECTED,
                    strokeWidth: 0.7,
                    strokeDasharray: '2 3',
                    outline: 'none',
                  },
                }}
                onMouseEnter={() => {
                  if (!agg) return;
                  showTooltip(agg);
                }}
                onMouseLeave={() => {
                  scheduleHide();
                }}
                onClick={(e) => {
                  if (!agg) return;
                  e.stopPropagation();
                  onSelect(agg);
                }}
                onKeyDown={(e) => {
                  if (!agg) return;
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelect(agg);
                  }
                }}
                tabIndex={count > 0 ? 0 : -1}
                role={count > 0 ? 'button' : undefined}
                aria-label={count > 0 ? `Select ${mappedCountry}, ${count} projects` : undefined}
              />
            );
          })
        }
      </Geographies>
    </>
  );
};
