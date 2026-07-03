import React from 'react';
import { SearchX, WifiOff, RefreshCw } from 'lucide-react';

/** Shared button styles for clear filters and retry buttons */
const BUTTON_CLASSES =
  "inline-flex items-center gap-2 px-5 py-2.5 rounded-full bg-brand-900 text-white font-inter text-sm font-medium hover:bg-brand-500 transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2";

interface NoResultsProps {
  onClearFilters: () => void;
}

export const NoResults: React.FC<NoResultsProps> = ({ onClearFilters }) => (
  <div
    className="flex flex-col items-center justify-center py-16 px-4"
    role="status"
    aria-live="polite"
    aria-atomic="true"
  >
    <div className="w-16 h-16 rounded-full bg-brand-100 flex items-center justify-center mb-4">
      <SearchX className="w-7 h-7 text-brand-500" />
    </div>
    <h3 className="font-poppins font-medium text-lg text-text-primary mb-2">
      No projects found
    </h3>
    <p className="font-inter text-sm text-text-muted text-center max-w-md mb-5">
      No projects match your current filters or search query. Try adjusting your criteria or clearing all filters.
    </p>
    <button
      type="button"
      onClick={onClearFilters}
      className={BUTTON_CLASSES}
    >
      Clear all filters
    </button>
  </div>
);

interface FetchErrorProps {
  onRetry: () => void;
}

export const FetchError: React.FC<FetchErrorProps> = ({ onRetry }) => (
  <div
    className="flex flex-col items-center justify-center py-16 px-4"
    role="alert"
  >
    <div className="w-16 h-16 rounded-full bg-semantic-error-bg flex items-center justify-center mb-4">
      <WifiOff className="w-7 h-7 text-semantic-error-icon" />
    </div>
    <h3 className="font-poppins font-medium text-lg text-text-primary mb-2">
      Unable to load project data
    </h3>
    <p className="font-inter text-sm text-text-muted text-center max-w-md mb-5">
      Something went wrong while loading the project database. Please try again.
    </p>
    <button
      type="button"
      onClick={onRetry}
      className={BUTTON_CLASSES}
    >
      <RefreshCw className="w-4 h-4" />
      Retry
    </button>
  </div>
);
