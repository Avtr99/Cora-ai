import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

const BOTTOM_THRESHOLD = 64;
const TOP_BUTTON_THRESHOLD = 300;
const SCROLL_IDLE_MS = 2500;

/** Event name used to cancel the streaming auto-scroll lock in `ChatInterface`. */
export const CHAT_CANCEL_AUTOSCROLL = 'chat:cancel-autoscroll';

export interface UseChatScrollOptions {
  /** CSS selector for the scroll container. Falls back to the document element. */
  scrollContainerSelector?: string;
}

export interface ChatScrollState {
  /** True when the user is within BOTTOM_THRESHOLD px of the scroll bottom. */
  isAtBottom: boolean;
  /** True when the content is taller than the viewport (a scrollbar exists). */
  canScroll: boolean;
  /** True when the user is far enough from the top to justify a "scroll to top" action. */
  canScrollToTop: boolean;
  /** True while the user is actively scrolling (or recently finished). */
  isScrolling: boolean;
  /** Scroll smoothly (or instantly if reduced motion is preferred) to the bottom. */
  scrollToBottom: () => void;
  /** Scroll smoothly (or instantly if reduced motion is preferred) to the top. */
  scrollToTop: () => void;
}

/**
 * Tracks the scroll position of a chat container and exposes convenience
 * actions for jumping to the top or bottom of the conversation.
 *
 * - Uses a rAF-throttled scroll listener to avoid state churn.
 * - Watches the scroll container with ResizeObserver (viewport resize) and
 *   MutationObserver (content streaming in), so the button state stays correct.
 * - `scrollToBottom` does a best-effort smooth scroll and then a one-time
 *   corrective frame, because virtualized `scrollHeight` is an estimate while
 *   rows are being measured.
 * - Exposes `isScrolling` so callers can show scroll UI only while the user
 *   is actively scrolling (including touch dragging on mobile).
 */
export function useChatScroll({
  scrollContainerSelector = '[data-chat-scroll-container]',
}: UseChatScrollOptions = {}): ChatScrollState {
  const containerRef = useRef<HTMLElement | null>(null);
  const rafIdRef = useRef<number | null>(null);
  const scrollTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const smoothRef = useRef(true);

  const [isAtBottom, setIsAtBottom] = useState(false);
  const [canScroll, setCanScroll] = useState(false);
  const [canScrollToTop, setCanScrollToTop] = useState(false);
  const [isScrolling, setIsScrolling] = useState(false);

  // Detect reduced motion once on mount.
  useLayoutEffect(() => {
    smoothRef.current = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }, []);

  const compute = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight;
    const clientHeight = container.clientHeight;

    const maxScrollTop = scrollHeight - clientHeight;
    const atBottom = maxScrollTop <= 0 || scrollHeight - scrollTop - clientHeight < BOTTOM_THRESHOLD;
    const overflow = scrollHeight > clientHeight + 1;

    setIsAtBottom(atBottom);
    setCanScroll(overflow);
    setCanScrollToTop(atBottom && scrollTop > TOP_BUTTON_THRESHOLD);
  }, []);

  const scheduleCompute = useCallback(() => {
    if (rafIdRef.current !== null) return;
    rafIdRef.current = requestAnimationFrame(() => {
      rafIdRef.current = null;
      compute();
    });
  }, [compute]);

  const startScrollTimeout = useCallback(() => {
    setIsScrolling(true);
    if (scrollTimeoutRef.current) {
      clearTimeout(scrollTimeoutRef.current);
    }
    scrollTimeoutRef.current = setTimeout(() => {
      setIsScrolling(false);
    }, SCROLL_IDLE_MS);
  }, []);

  // Resolve the scroll container and set up listeners/observers.
  useEffect(() => {
    const container =
      (scrollContainerSelector
        ? document.querySelector<HTMLElement>(scrollContainerSelector)
        : null) ||
      (document.scrollingElement as HTMLElement) ||
      document.documentElement;

    containerRef.current = container;
    compute();

    const handleScroll = () => {
      scheduleCompute();
      startScrollTimeout();
    };
    container.addEventListener('scroll', handleScroll, { passive: true });

    // Touch move events fire before scroll on mobile, so this keeps the button
    // visible while the user is dragging their finger.
    container.addEventListener('touchmove', startScrollTimeout, { passive: true });

    // Recompute when the viewport size changes.
    const resizeObserver = new ResizeObserver(() => scheduleCompute());
    resizeObserver.observe(container);

    // Recompute when content grows (DOM nodes added or text streams in).
    const mutationObserver = new MutationObserver(() => scheduleCompute());
    mutationObserver.observe(container, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    return () => {
      container.removeEventListener('scroll', handleScroll);
      container.removeEventListener('touchmove', startScrollTimeout);
      resizeObserver.disconnect();
      mutationObserver.disconnect();
      if (rafIdRef.current !== null) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      if (scrollTimeoutRef.current) {
        clearTimeout(scrollTimeoutRef.current);
      }
    };
  }, [scrollContainerSelector, compute, scheduleCompute, startScrollTimeout]);

  const scrollToBottom = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const maxScrollTop = container.scrollHeight - container.clientHeight;
    if (maxScrollTop <= 0) return;

    const behavior = smoothRef.current ? 'smooth' : 'auto';
    container.scrollTo({ top: maxScrollTop, behavior });

    // Virtualized estimates may grow right after we initiate the smooth scroll.
    // Do a one-time correction shortly after to land exactly at the bottom.
    if (behavior === 'smooth') {
      const start = performance.now();
      const correct = () => {
        const elapsed = performance.now() - start;
        const currentMax = container.scrollHeight - container.clientHeight;
        if (elapsed < 600 && container.scrollTop < currentMax - BOTTOM_THRESHOLD) {
          requestAnimationFrame(correct);
        } else if (container.scrollTop < currentMax - BOTTOM_THRESHOLD) {
          container.scrollTop = currentMax;
        }
      };
      requestAnimationFrame(correct);
    }
  }, []);

  const scrollToTop = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const behavior = smoothRef.current ? 'smooth' : 'auto';
    container.scrollTo({ top: 0, behavior });
  }, []);

  return {
    isAtBottom,
    canScroll,
    canScrollToTop,
    isScrolling,
    scrollToBottom,
    scrollToTop,
  };
}
