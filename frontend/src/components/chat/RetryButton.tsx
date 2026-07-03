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
    className={`inline-flex items-center gap-1.5 font-poppins font-medium text-white text-xs px-3 py-1.5 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white bg-brand-900 ${
      disabled ? 'opacity-70 cursor-not-allowed' : 'hover:bg-brand-hover'
    }`}
  >
    {disabled ? (
      <>
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Retrying...
      </>
    ) : (
      label
    )}
  </button>
);
