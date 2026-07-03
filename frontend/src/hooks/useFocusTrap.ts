import { useEffect, useRef, type RefObject } from 'react';

interface UseFocusTrapOptions {
  /** Whether the focus trap is active */
  isActive: boolean;
  /** Ref to the container element that traps focus */
  containerRef: RefObject<HTMLElement | null>;
  /** Ref to the element that should receive initial focus */
  initialFocusRef?: RefObject<HTMLElement | null>;
  /** Ref to the element to restore focus to when closing */
  restoreFocusRef?: RefObject<HTMLElement | null>;
}

/**
 * Traps focus within a container element, cycling through focusable elements.
 * Also handles initial focus and focus restoration.
 */
export function useFocusTrap({
  isActive,
  containerRef,
  initialFocusRef,
  restoreFocusRef,
}: UseFocusTrapOptions): void {
  const lastFocusedElementRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!isActive) return;

    // Store last focused element before opening
    lastFocusedElementRef.current = document.activeElement as HTMLElement;

    // Move focus to initial element after animation
    const timer = setTimeout(() => {
      initialFocusRef?.current?.focus();
    }, 100);

    const container = containerRef.current;
    const restoreTargetAtCleanup = restoreFocusRef?.current;
    if (!container) return;

    // Get all focusable elements
    const getFocusableElements = () => {
      const selectors = [
        'button:not([disabled])',
        'a[href]',
        'input:not([disabled])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])',
        '[contenteditable]',
      ].join(', ');
      return Array.from(container.querySelectorAll(selectors)) as HTMLElement[];
    };

    // Handle Tab key to trap focus
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      const focusableElements = getFocusableElements();
      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];
      const activeElement = document.activeElement;

      // Shift + Tab: if on first element, wrap to last
      if (e.shiftKey) {
        if (activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        // Tab: if on last element, wrap to first
        if (activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    };

    container.addEventListener('keydown', handleKeyDown);

    return () => {
      clearTimeout(timer);
      container.removeEventListener('keydown', handleKeyDown);
      // Restore focus to trigger button when closing
      const restoreTarget = restoreTargetAtCleanup ?? lastFocusedElementRef.current;
      if (restoreTarget && restoreTarget.isConnected && typeof restoreTarget.focus === 'function') {
        try {
          restoreTarget.focus();
        } catch (e) {
          console.warn('useFocusTrap: failed to restore focus', e);
        }
      }
    };
  }, [isActive, containerRef, initialFocusRef, restoreFocusRef]);
}
