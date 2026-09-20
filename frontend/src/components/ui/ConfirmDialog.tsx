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
      ? 'bg-semantic-error-button text-white hover:bg-semantic-error-buttonHover focus-visible:ring-focus'
      : 'bg-brand-700 text-white hover:bg-brand-hover focus-visible:ring-focus';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md 3xl:max-w-lg 4xl:max-w-xl w-[calc(100%-2rem)] rounded-xl border-border-ui bg-surface-card p-5 3xl:p-6 4xl:p-7 shadow-modal">
        <DialogHeader className="space-y-2 text-left">
          <DialogTitle className="font-poppins text-base 3xl:text-lg 4xl:text-xl font-medium leading-snug 3xl:leading-7 4xl:leading-8 text-text-primary break-all">
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription className="font-inter text-sm 3xl:text-base 4xl:text-lg leading-5 3xl:leading-6 4xl:leading-7 text-text-secondary">
              {description}
            </DialogDescription>
          )}
        </DialogHeader>
        <div className="mt-4 3xl:mt-5 4xl:mt-6 flex flex-col-reverse gap-2 3xl:gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            disabled={isConfirming}
            className="inline-flex h-9 3xl:h-10 4xl:h-11 items-center justify-center rounded-lg border border-border-ui px-4 3xl:px-5 4xl:px-6 font-poppins text-sm 3xl:text-base 4xl:text-lg font-semibold text-text-primary transition-colors hover:bg-surface-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-focus disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isConfirming}
            className={`inline-flex h-9 3xl:h-10 4xl:h-11 items-center justify-center rounded-lg px-4 3xl:px-5 4xl:px-6 font-poppins text-sm 3xl:text-base 4xl:text-lg font-semibold transition-colors focus:outline-none focus-visible:ring-2 disabled:opacity-50 ${confirmClasses}`}
          >
            {isConfirming ? `${confirmLabel}…` : confirmLabel}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
