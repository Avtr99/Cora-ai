import React from 'react';
import { ArrowDown, ArrowUp } from 'lucide-react';
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion';
import { useChatScroll, CHAT_CANCEL_AUTOSCROLL } from './useChatScroll';

interface ChatScrollButtonProps {
  /** Whether the chat currently has messages. When false, the button is always hidden. */
  hasMessages: boolean;
}

/**
 * Floating scroll toggle for the chat composer.
 *
 * - Centered above the composer, works for mobile, tablet, and desktop without
 *   duplicating positioning logic.
 * - Appears while the user is actively scrolling and auto-hides shortly after scrolling stops.
 * - Shows a down arrow when the user has scrolled away from the latest content.
 * - Flips to an up arrow when pinned to the bottom of a long conversation.
 * - Dispatches `CHAT_CANCEL_AUTOSCROLL` so a manual jump wins over the streaming
 *   auto-scroll lock in `ChatInterface`.
 */
export const ChatScrollButton: React.FC<ChatScrollButtonProps> = ({ hasMessages }) => {
  const { isAtBottom, canScroll, canScrollToTop, isScrolling, scrollToBottom, scrollToTop } = useChatScroll();
  const shouldReduceMotion = useReducedMotion();

  const showDown = hasMessages && canScroll && !isAtBottom;
  const showUp = hasMessages && canScroll && isAtBottom && canScrollToTop;
  const visible = (showDown || showUp) && isScrolling;

  const handleClick = () => {
    window.dispatchEvent(new CustomEvent(CHAT_CANCEL_AUTOSCROLL));
    if (showDown) {
      scrollToBottom();
    } else {
      scrollToTop();
    }
  };

  const label = showDown ? 'Scroll to latest' : 'Scroll to top';

  return (
    <AnimatePresence>
      {visible && (
        <motion.button
          type="button"
          initial={{ opacity: 0, y: 8, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.9 }}
          transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.2 }}
          whileTap={shouldReduceMotion ? undefined : { scale: 0.92 }}
          onClick={handleClick}
          aria-label={label}
          title={label}
          className="absolute left-1/2 -translate-x-1/2 -top-12 md:-top-10 z-30 flex items-center justify-center h-11 w-11 md:h-8 md:w-8 rounded-full bg-white/90 backdrop-blur-sm border border-border-ui shadow-scroll-btn text-text-muted transition-all duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.12)] hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-white"
        >
          {showDown ? <ArrowDown className="h-5 w-5 md:h-4 md:w-4" aria-hidden="true" /> : <ArrowUp className="h-5 w-5 md:h-4 md:w-4" aria-hidden="true" />}
        </motion.button>
      )}
    </AnimatePresence>
  );
};
