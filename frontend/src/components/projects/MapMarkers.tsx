import React from 'react';
import { Marker } from 'react-simple-maps';
import { motion } from 'framer-motion';
import type { CountryAggregate } from '@/lib/mapAggregation';
import { getMouseCoords } from '@/lib/mapConstants';
import { TEXT } from '@/lib/colors';

interface MarkerItem {
  agg: CountryAggregate;
  coords: [number, number];
  r: number;
}

interface MapMarkersProps {
  markers: MarkerItem[];
  zoom: number;
  selectedCountry: string | null;
  hoveredCountry: string | null;
  showTooltip: (agg: CountryAggregate) => void;
  scheduleHide: () => void;
  onSelect: (agg: CountryAggregate) => void;
}

export const MapMarkers: React.FC<MapMarkersProps> = ({
  markers,
  zoom,
  selectedCountry,
  hoveredCountry,
  showTooltip,
  scheduleHide,
  onSelect,
}) => {
  return (
    <>
      {markers.map(({ agg, coords, r }) => {
        const isSelected = selectedCountry === agg.country;
        const isHovered = hoveredCountry === agg.country;
        const designR = isSelected ? r + 2 : isHovered ? r + 1.2 : r;
        const targetR = designR / zoom;
        return (
          <Marker key={agg.country} coordinates={coords}>
            <motion.circle
              initial={false}
              animate={{ r: targetR }}
              transition={{ type: 'spring', stiffness: 320, damping: 24 }}
              fill={agg.dominantColor}
              fillOpacity={isSelected ? 1 : 0.85}
              stroke={TEXT.inverse}
              strokeWidth={isSelected ? 2 : 1.5}
              vectorEffect="non-scaling-stroke"
              style={{
                cursor: 'pointer',
                pointerEvents: 'auto',
                filter: isSelected || isHovered
                  ? 'var(--shadow-marker-active)'
                  : 'var(--shadow-marker)',
              }}
              onMouseEnter={() => {
                showTooltip(agg);
              }}
              onMouseLeave={scheduleHide}
              onClick={(e) => {
                getMouseCoords(e).stopPropagation();
                onSelect(agg);
              }}
            />
          </Marker>
        );
      })}
    </>
  );
};
