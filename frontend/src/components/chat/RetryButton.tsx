import React from 'react';
import { Loader2 } from 'lucide-react';

interface RetryButtonProps {
  onClick: () => void;
  disabled?: boolean;
  label?: string;
}

export const RetryButton: React.FC<RetryButtonProps> = ({ onClick, disabled, label = 'Retry' }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    className={`inline-flex items-center gap-1.5 3xl:gap-2 font-poppins font-medium text-white text-xs 3xl:text-sm 4xl:text-base px-3 3xl:px-4 4xl:px-5 py-1.5 3xl:py-2 4xl:py-2.5 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white bg-brand-900 ${
      disabled ? 'opacity-70 cursor-not-allowed' : 'hover:bg-brand-hover'
    }`}
  >
    {disabled ? (
      <>
        <Loader2 className="h-3.5 w-3.5 3xl:h-4 3xl:w-4 4xl:h-5 4xl:w-5 animate-spin" />
        Retrying...
      </>
    ) : (
      label
    )}
  </button>
);
