import React, { useState, useEffect, useRef } from 'react';
import { IconWrapper } from '@/components/icons/IconWrapper';
import ArrowUpIcon from '@/assets/icons/arrow-up.svg?react';

interface ScrollToTopProps {
  variant?: 'default' | 'compact';
  scrollContainerSelector?: string;
  /** When true, shifts the button up to avoid overlapping the CompareBar */
  hasCompareBar?: boolean;
}

/**
 * ScrollToTop component - Displays a button that appears when scrolling down
 * and allows users to smoothly scroll back to the top of the page
 * @param variant - 'default' for regular size (56px), 'compact' for smaller size (44px)
 * @param scrollContainerSelector - Optional CSS selector for custom scroll container
 */
export const ScrollToTop: React.FC<ScrollToTopProps> = ({ 
  variant = 'default',
  scrollContainerSelector,
  hasCompareBar = false,
}) => {
  const [isVisible, setIsVisible] = useState(false);
  const scrollElementRef = useRef<HTMLElement | Window | null>(null);

  // Show button when page is scrolled down
  const toggleVisibility = () => {
    const scrollElement = scrollElementRef.current;
    
    const scrollTop = scrollElement instanceof Window
      ? scrollElement.pageYOffset
      : (scrollElement as HTMLElement)?.scrollTop || 0;
    
    if (scrollTop > 300) {
      setIsVisible(true);
    } else {
      setIsVisible(false);
    }
  };

  // Scroll to top smoothly
  const scrollToTop = () => {
    const scrollElement = scrollElementRef.current;
    
    if (scrollElement instanceof Window) {
      scrollElement.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    } else if (scrollElement) {
      scrollElement.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    } else {
      // Fallback if ref is null
      window.scrollTo({
        top: 0,
        behavior: 'smooth'
      });
    }
  };

  // Cache scroll container element
  useEffect(() => {
    if (scrollContainerSelector) {
      const element = document.querySelector(scrollContainerSelector) as HTMLElement | null;
      scrollElementRef.current = element;
    } else {
      scrollElementRef.current = window;
    }

    // Clear ref if selector becomes undefined or element not found
    return () => {
      scrollElementRef.current = null;
    };
  }, [scrollContainerSelector]);

  // Set up scroll event listener
  useEffect(() => {
    const scrollElement = scrollElementRef.current;
    
    if (scrollElement) {
      scrollElement.addEventListener('scroll', toggleVisibility);
      return () => scrollElement.removeEventListener('scroll', toggleVisibility);
    }
  }, [scrollContainerSelector]);

  const isCompact = variant === 'compact';
  const buttonSize = isCompact ? 'w-8 h-8' : 'w-12 h-12';
  const iconSize = isCompact ? 16 : 20;
  // Shift up when CompareBar is visible so the button doesn't overlap
  const bottomClass = hasCompareBar ? 'bottom-20' : 'bottom-8';
  const position = `${bottomClass} right-8`;

  return (
    <div
      className={`fixed ${position} z-50 transition-all duration-500 ${
        isVisible 
          ? 'opacity-100 translate-y-0' 
          : 'opacity-0 translate-y-4 pointer-events-none'
      }`}
    >
      <button
        onClick={scrollToTop}
        className={`${buttonSize} flex items-center justify-center rounded-full bg-surface-card/90 backdrop-blur-sm border border-border-ui shadow-scroll-btn text-text-muted transition-all duration-200 hover:shadow-card-md active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500 focus-visible:ring-offset-surface-card`}
        aria-label="Scroll to top"
      >
        <IconWrapper
          Icon={ArrowUpIcon}
          size={iconSize}
          color="currentColor"
          aria-hidden={true}
        />
      </button>
    </div>
  );
};
