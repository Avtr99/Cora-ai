import React, { useEffect, useRef, useCallback } from 'react';
import type { VCMProject } from '@/types/project';
import { ProjectDetailPanel } from '@/components/projects/ProjectDetailPanel';

interface MobileProjectDetailProps {
  project: VCMProject;
  onClose: () => void;
}

/**
 * Accessible mobile project detail modal with:
 * - aria-modal="true" for screen reader modal behavior
 * - Escape key handler to close
 * - Auto-focus management
 * - Click outside to close
 */
export const MobileProjectDetail: React.FC<MobileProjectDetailProps> = ({
  project,
  onClose,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousActiveElement = useRef<Element | null>(null);
  const onCloseRef = useRef(onClose);

  // Keep onCloseRef in sync
  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  // Get all focusable elements within the dialog
  const getFocusableElements = useCallback(() => {
    if (!dialogRef.current) return [];
    const selector = [
      'button:not([disabled])',
      'a[href]',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ].join(', ');
    return Array.from(dialogRef.current.querySelectorAll<HTMLElement>(selector));
  }, []);

  // Focus management on mount/unmount.
  //
  // NOTE: This component renders a mobile-only overlay (see `lg:hidden` on the
  // root <div>). On lg+ viewports the overlay is CSS-hidden but the React
  // component is still mounted when `mobileDetailOpen === true`. We must NOT
  // lock body scroll on desktop — doing so made the whole page un-scrollable
  // after the user opened any project detail (bug: scroll bar disappeared
  // until reload). We detect the desktop viewport with matchMedia and also
  // listen for resizes so the lock is released if a user rotates a tablet /
  // resizes across the lg breakpoint while the modal is "open".
  useEffect(() => {
    // Store the element that had focus before opening
    previousActiveElement.current = document.activeElement;

    const desktopMql = window.matchMedia('(min-width: 1024px)');
    const applyForViewport = () => {
      if (desktopMql.matches) {
        // Desktop: overlay is hidden via CSS — don't touch body scroll
        // and don't steal focus from the desktop layout.
        document.body.style.overflow = '';
        return;
      }
      // Mobile: lock body scroll and focus the dialog for a11y
      document.body.style.overflow = 'hidden';
      if (dialogRef.current && document.activeElement !== dialogRef.current) {
        dialogRef.current.focus();
      }
    };

    applyForViewport();
    desktopMql.addEventListener('change', applyForViewport);

    return () => {
      desktopMql.removeEventListener('change', applyForViewport);
      document.body.style.overflow = '';

      // Restore focus to the previously focused element
      if (previousActiveElement.current instanceof HTMLElement) {
        previousActiveElement.current.focus();
      }
    };
  }, []);

  // Keyboard handling (stable effect, uses ref for onClose)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCloseRef.current();
        return;
      }

      // Focus trap: Tab/Shift+Tab cycles within modal
      if (e.key === 'Tab') {
        const focusable = getFocusableElements();
        if (focusable.length === 0) {
          e.preventDefault();
          return;
        }

        const firstElement = focusable[0];
        const lastElement = focusable[focusable.length - 1];

        if (e.shiftKey) {
          // Shift+Tab: if on first, wrap to last
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement.focus();
          }
        } else {
          // Tab: if on last, wrap to first
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement.focus();
          }
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [getFocusableElements]);

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="lg:hidden fixed inset-0 z-50 bg-black/40"
      onClick={handleOverlayClick}
    >
      <div
        ref={dialogRef}
        className="absolute right-0 top-0 bottom-0 w-full max-w-[440px] bg-surface-card shadow-xl"
        role="dialog"
        aria-modal="true"
        aria-label="Project details"
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
      >
        <ProjectDetailPanel project={project} onClose={onClose} />
      </div>
    </div>
  );
};

export default MobileProjectDetail;
