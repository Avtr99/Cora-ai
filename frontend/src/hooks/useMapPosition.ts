import { useState, useRef, useCallback, useEffect } from 'react';
import { DEFAULT_CENTER } from '@/lib/mapConstants';

export interface MapPosition {
  coordinates: [number, number];
  zoom: number;
}

type PositionTarget = MapPosition;
type PositionUpdater = (prev: PositionTarget) => PositionTarget;

export function useMapPosition() {
  const [position, setPosition] = useState<MapPosition>({
    coordinates: DEFAULT_CENTER,
    zoom: 1,
  });
  const positionRef = useRef(position);

  // Keep positionRef in sync with position state (fixes stale ref when setPosition called directly)
  useEffect(() => {
    positionRef.current = position;
  }, [position]);

  // Animated tween for smooth ease-in-out transitions when focusing a
  // country or using zoom buttons. A RAF loop interpolates from the
  // current position to the target over 600 ms using an ease-in-out
  // cubic curve, instead of snapping instantly.
  const animFrameRef = useRef<number | null>(null);

  const cancelAnim = useCallback(() => {
    if (animFrameRef.current !== null) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
  }, []);

  const animateTo = useCallback(
    (targetOrUpdater: PositionTarget | PositionUpdater) => {
      cancelAnim();

      // Compute target and animation parameters outside setPosition to avoid side-effects in updater
      const prev = positionRef.current;
      const target =
        typeof targetOrUpdater === 'function'
          ? targetOrUpdater(prev)
          : targetOrUpdater;
      const startT = performance.now();
      const [sx, sy] = prev.coordinates;
      const [tx, ty] = target.coordinates;
      const sz = prev.zoom;
      const tz = target.zoom;
      const duration = 600;
      const easeInOutCubic = (t: number) =>
        t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;

      const step = (now: number) => {
        const p = Math.min(1, (now - startT) / duration);
        const e = easeInOutCubic(p);
        const next: PositionTarget = {
          coordinates: [sx + (tx - sx) * e, sy + (ty - sy) * e],
          zoom: sz + (tz - sz) * e,
        };
        setPosition(next);
        if (p < 1) {
          animFrameRef.current = requestAnimationFrame(step);
        } else {
          animFrameRef.current = null;
        }
      };

      // Start animation loop outside of setState to avoid Strict Mode double-invocation
      animFrameRef.current = requestAnimationFrame(step);
    },
    [cancelAnim],
  );

  useEffect(() => () => cancelAnim(), [cancelAnim]);

  const zoomIn = useCallback(() => {
    animateTo((p) => ({ coordinates: p.coordinates, zoom: Math.min(p.zoom * 1.5, 8) }));
  }, [animateTo]);

  // Gentler zoom-out step (1.3 vs zoom-in's 1.5) so retreating feels more
  // gradual — users usually want finer control when pulling back for context.
  const zoomOut = useCallback(() => {
    animateTo((p) => ({ coordinates: p.coordinates, zoom: Math.max(p.zoom / 1.3, 1) }));
  }, [animateTo]);

  const reset = useCallback(() => {
    animateTo({ coordinates: DEFAULT_CENTER, zoom: 1 });
  }, [animateTo]);

  return {
    position,
    setPosition,
    positionRef,
    animateTo,
    zoomIn,
    zoomOut,
    reset,
    cancelAnim,
  };
}
