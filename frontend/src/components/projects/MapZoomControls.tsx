import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';

interface MapZoomControlsProps {
  onZoomIn: () => void;
  onZoomOut: () => void;
  onReset: () => void;
}

export const MapZoomControls: React.FC<MapZoomControlsProps> = ({ onZoomIn, onZoomOut, onReset }) => {
  const shouldReduceMotion = useReducedMotion();
  return (
    <motion.div
      initial={shouldReduceMotion ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.25, ease: 'easeOut', delay: 0.15 }}
      onClick={(e) => e.stopPropagation()}
      className="absolute bottom-3 right-3 z-20 flex flex-col bg-surface-card/90 backdrop-blur-sm border border-border-ui rounded-xl shadow-xs overflow-hidden"
      role="group"
      aria-label="Map zoom controls"
    >
      <ZoomBtn onClick={onZoomIn} label="Zoom in">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M12 5v14M5 12h14" />
        </svg>
      </ZoomBtn>
      <div className="h-px bg-surface-subtle" aria-hidden="true" />
      <ZoomBtn onClick={onZoomOut} label="Zoom out">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
          <path d="M5 12h14" />
        </svg>
      </ZoomBtn>
      <div className="h-px bg-surface-subtle" aria-hidden="true" />
      <ZoomBtn onClick={onReset} label="Reset view">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 12a9 9 0 1 0 3-6.7" />
          <path d="M3 4v4h4" />
        </svg>
      </ZoomBtn>
    </motion.div>
  );
};

const ZoomBtn: React.FC<{ onClick: () => void; label: string; children: React.ReactNode }> = ({
  onClick,
  label,
  children,
}) => (
  <button
    type="button"
    onClick={onClick}
    aria-label={label}
    className="w-8 h-8 flex items-center justify-center text-text-secondary hover:bg-brand-100/60 hover:text-brand-700 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500"
  >
    {children}
  </button>
);
