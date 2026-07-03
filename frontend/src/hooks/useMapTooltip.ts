import { useState, useRef, useCallback, useEffect } from 'react';
import type { CountryAggregate } from '@/lib/mapAggregation';

export interface TooltipState {
  agg: CountryAggregate;
}

export function useMapTooltip(onHoverCountry: (country: string | null) => void) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<TooltipState | null>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearHideTimer = useCallback(() => {
    if (hideTimerRef.current) {
      clearTimeout(hideTimerRef.current);
      hideTimerRef.current = null;
    }
  }, []);

  useEffect(() => () => clearHideTimer(), [clearHideTimer]);

  // Kept signature for call-sites; clientX/clientY are unused because the
  // tooltip is docked in a fixed corner (avoids occluding small countries).
  const showTooltip = useCallback(
    (agg: CountryAggregate, _clientX?: number, _clientY?: number) => {
      clearHideTimer();
      onHoverCountry(agg.country);
      setTooltip({ agg });
    },
    [clearHideTimer, onHoverCountry],
  );

  const scheduleHide = useCallback(() => {
    onHoverCountry(null);
    clearHideTimer();
    hideTimerRef.current = setTimeout(() => {
      setTooltip(null);
      hideTimerRef.current = null;
    }, 220);
  }, [onHoverCountry, clearHideTimer]);

  const handleTooltipEnter = useCallback(() => clearHideTimer(), [clearHideTimer]);
  const handleTooltipLeave = useCallback(() => {
    clearHideTimer();
    setTooltip(null);
  }, [clearHideTimer]);

  return {
    containerRef,
    tooltip,
    setTooltip,
    showTooltip,
    scheduleHide,
    handleTooltipEnter,
    handleTooltipLeave,
  };
}
