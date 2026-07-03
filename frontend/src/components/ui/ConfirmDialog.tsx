import React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';

export type ConfirmVariant = 'destructive' | 'neutral';

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  variant?: ConfirmVariant;
  onConfirm: () => void;
  isConfirming?: boolean;
}

/**
 * Design-system confirmation dialog.
 *
 * Wraps the Shadcn/Radix dialog primitive with consistent Cora tokens,
 * typography, and button styling. Destructive confirmations use a red
 * confirm button; neutral confirmations use the brand color.
 */
export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel = 'Cancel',
  variant = 'destructive',
  onConfirm,
  isConfirming = false,
}) => {
  const confirmClasses =
    variant === 'destructive'
      ? 'bg-semantic-error-button text-white hover:bg-semantic-error-buttonHover focus-visible:ring-brand-500'
      : 'bg-brand-700 text-white hover:bg-brand-hover focus-visible:ring-brand-500';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md w-[calc(100%-2rem)] rounded-xl border-border-ui bg-surface-card p-5 shadow-modal">
        <DialogHeader className="space-y-2 text-left">
          <DialogTitle className="font-poppins text-base font-medium leading-snug text-text-primary break-all">
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription className="font-inter text-sm leading-5 text-text-secondary">
              {description}
            </DialogDescription>
          )}
        </DialogHeader>
        <div className="mt-4 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={isConfirming}
            className="inline-flex h-9 items-center justify-center rounded-lg border border-border-ui px-4 font-poppins text-sm font-semibold text-text-primary transition-colors hover:bg-surface-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isConfirming}
            className={`inline-flex h-9 items-center justify-center rounded-lg px-4 font-poppins text-sm font-semibold transition-colors focus:outline-none focus-visible:ring-2 disabled:opacity-50 ${confirmClasses}`}
          >
            {isConfirming ? `${confirmLabel}…` : confirmLabel}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
