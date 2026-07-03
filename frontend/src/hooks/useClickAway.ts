import { useEffect, RefObject } from 'react';

export function useClickAway<T extends HTMLElement>(
  ref: RefObject<T | null>,
  onClickAway: () => void,
): void {
  useEffect(() => {
    const handlePointerDown = (event: PointerEvent) => {
      const el = ref.current;
      if (el && !el.contains(event.target as Node)) {
        onClickAway();
      }
    };

    document.addEventListener('pointerdown', handlePointerDown);
    return () => document.removeEventListener('pointerdown', handlePointerDown);
  }, [ref, onClickAway]);
}
