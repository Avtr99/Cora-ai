import { useRef, useCallback, useEffect } from 'react';

interface UseLongPressOptions {
  /** Duration in ms before the long-press fires (default: 500) */
  threshold?: number;
  /** Called when a long-press is detected */
  onLongPress: () => void;
}

/**
 * Hook that detects long-press (touch hold) gestures.
 * Returns event handlers to spread onto the target element.
 * Cancels on move (>10 px drift) to avoid false positives during scroll.
 */
export function useLongPress({ onLongPress, threshold = 500 }: UseLongPressOptions) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const firedRef = useRef(false);
  const startPos = useRef<{ x: number; y: number } | null>(null);

  const clear = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // Cleanup pending timer on unmount to prevent onLongPress firing after teardown
  useEffect(() => {
    return () => clear();
  }, [clear]);

  const onTouchStart = useCallback(
    (e: React.TouchEvent) => {
      firedRef.current = false;
      const touch = e.touches[0];
      startPos.current = { x: touch.clientX, y: touch.clientY };

      timerRef.current = setTimeout(() => {
        firedRef.current = true;
        onLongPress();
        // Provide haptic feedback if available
        if (navigator.vibrate) navigator.vibrate(30);
      }, threshold);
    },
    [onLongPress, threshold],
  );

  const onTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (!startPos.current) return;
      const touch = e.touches[0];
      const dx = Math.abs(touch.clientX - startPos.current.x);
      const dy = Math.abs(touch.clientY - startPos.current.y);
      // Cancel if finger moved more than 10px (user is scrolling)
      if (dx > 10 || dy > 10) {
        clear();
      }
    },
    [clear],
  );

  const onTouchEnd = useCallback(
    (e: React.TouchEvent) => {
      clear();
      // If long-press fired, prevent the subsequent click/tap from navigating
      if (firedRef.current) {
        e.preventDefault();
      }
    },
    [clear],
  );

  const onTouchCancel = useCallback(
    (e: React.TouchEvent) => {
      clear();
      // If long-press fired, prevent the subsequent click/tap from navigating
      if (firedRef.current) {
        e.preventDefault();
      }
    },
    [clear],
  );

  return { onTouchStart, onTouchMove, onTouchEnd, onTouchCancel };
}
