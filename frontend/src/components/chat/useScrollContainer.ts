import { useLayoutEffect, useRef, useState } from 'react';

/**
 * Discovers the nearest scrollable ancestor or a container marked with
 * `data-chat-scroll-container`.  Returns both a React ref and a state value
 * so the container is available for event listeners and DOM queries.
 */
export function useScrollContainer(containerRef: React.RefObject<HTMLElement | null>) {
  const parentScrollRef = useRef<HTMLElement | null>(null);
  const [scrollContainer, setScrollContainer] = useState<HTMLElement | null>(null);

  useLayoutEffect(() => {
    // 1. Look for an explicit scroll container marker
    const explicit = document.querySelector<HTMLElement>('[data-chat-scroll-container]');
    if (explicit) {
      parentScrollRef.current = explicit;
      setScrollContainer(explicit);
      return;
    }

    // 2. Walk up the DOM tree for overflow-y: auto|scroll
    if (containerRef.current) {
      let parent = containerRef.current.parentElement;
      while (parent) {
        const overflow = window.getComputedStyle(parent).overflowY;
        if (overflow === 'auto' || overflow === 'scroll') {
          parentScrollRef.current = parent;
          setScrollContainer(parent);
          break;
        }
        parent = parent.parentElement;
      }
    }

    // 3. Fallbacks — never leave the ref null
    if (!parentScrollRef.current) {
      if (containerRef.current) {
        parentScrollRef.current = containerRef.current;
        setScrollContainer(containerRef.current);
        console.warn('⚠️ Using scrollContainerRef as fallback scroll container');
      } else {
        const docScroll = (document.scrollingElement as HTMLElement) || document.documentElement;
        parentScrollRef.current = docScroll;
        setScrollContainer(docScroll);
        console.warn('⚠️ Using document scrollingElement as final fallback scroll container');
      }
    }
  }, [containerRef]);

  return { parentScrollRef, scrollContainer };
}
