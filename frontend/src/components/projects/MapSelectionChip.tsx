import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { CountryAggregate } from '@/lib/mapAggregation';
import { SELECTED_FILL } from '@/lib/mapConstants';

interface MapSelectionChipProps {
  selectedCountry: string | null;
  aggByCountry: Map<string, CountryAggregate>;
  onClear: () => void;
}

export const MapSelectionChip: React.FC<MapSelectionChipProps> = ({
  selectedCountry,
  aggByCountry,
  onClear,
}) => {
  return (
    <AnimatePresence>
      {selectedCountry && (
        <motion.div
          key="country-chip"
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.18, ease: 'easeOut' }}
          onClick={(e) => e.stopPropagation()}
          className="absolute top-3 right-3 z-20"
        >
          <button
            type="button"
            onClick={onClear}
            className="group inline-flex items-center gap-2 px-3 py-1.5 bg-surface-card border border-border-ui rounded-full shadow-xs hover:shadow-card-sm transition-shadow"
            aria-label={`Clear ${selectedCountry} filter`}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: SELECTED_FILL }}
            />
            <span className="font-inter text-[11.5px] text-text-primary font-medium">
              {selectedCountry}
            </span>
            <span className="font-inter text-2xs text-text-muted tabular-nums">
              {aggByCountry.get(selectedCountry)?.projectCount ?? 0}
            </span>
            <svg
              className="w-3 h-3 text-text-muted group-hover:text-text-primary transition-colors"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden="true"
            >
              <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" />
            </svg>
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
