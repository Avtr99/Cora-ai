import React from 'react';

interface MapFallbackProps {
  errorMessage?: string;
}

const MapFallback: React.FC<MapFallbackProps> = ({ errorMessage }) => (
  <div
    className="absolute inset-0 flex items-center justify-center bg-surface-page"
    role={errorMessage ? 'alert' : 'status'}
    aria-live={errorMessage ? 'assertive' : 'polite'}
  >
    {errorMessage ? (
      <div className="flex flex-col items-center gap-2 text-center px-4">
        <span className="font-inter text-xs text-text-muted">{errorMessage}</span>
      </div>
    ) : (
      <div className="flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" aria-hidden="true" />
        <span className="font-inter text-xs text-text-muted">Loading world map…</span>
        <span className="sr-only">World map data is loading, please wait.</span>
      </div>
    )}
  </div>
);

export default MapFallback;
