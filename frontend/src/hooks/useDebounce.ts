import { useRef, useEffect, useCallback } from 'react';

/**
 * Returns a debounced version of the provided function.
 * Automatically cleans up pending timeouts on unmount.
 * Uses a ref to store the latest function to avoid stale closures.
 */
export interface DebouncedCallback<T extends (...args: unknown[]) => void> {
  (...args: Parameters<T>): void;
  cancel(): void;
}

export function useDebounce<T extends (...args: unknown[]) => void>(
  fn: T,
  delay: number
): DebouncedCallback<T> {
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const latestFnRef = useRef<T>(fn);

  // Keep latestFnRef in sync with fn changes
  useEffect(() => {
    latestFnRef.current = fn;
  }, [fn]);

  useEffect(() => {
    return () => {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = undefined;
    };
  }, []);

  const debounced = useCallback(
    (...args: Parameters<T>) => {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => latestFnRef.current(...args), delay);
    },
    [delay]
  ) as DebouncedCallback<T>;

  debounced.cancel = useCallback(() => {
    clearTimeout(timeoutRef.current);
    timeoutRef.current = undefined;
  }, []);

  return debounced;
}
