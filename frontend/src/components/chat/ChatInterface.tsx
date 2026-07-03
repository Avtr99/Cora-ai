import React, { useEffect, useMemo, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useActiveChat } from '@/store/chatStore.simple';
import { ChatMessageItem } from './ChatMessageItem';
import { useScrollContainer } from './useScrollContainer';
import './chat-interface.css';

// TanStack Virtual default estimate for a single message row (pixels).
// The virtualizer remeasures real DOM heights, so this only affects initial layout.
const DEFAULT_MESSAGE_ESTIMATE_SIZE = 200;

/**
 * ChatInterface renders the scrollable message list using TanStack Virtual.
 *
 * Features:
 * - Virtualized rendering for performance with many messages
 * - Auto-scroll to latest user message with smart locking
 * - MutationObserver-based scroll correction during streaming
 * - User interaction cancels auto-scroll
 * - Empty state when no active chat
 *
 * @example
 * <ChatInterface />
 */
export const ChatInterface: React.FC = () => {
  const activeChat = useActiveChat();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const { parentScrollRef, scrollContainer } = useScrollContainer(scrollContainerRef);

  const messages = useMemo(() => activeChat?.messages ?? [], [activeChat?.messages]);

  // TanStack Virtual virtualizer - point to parent scroll container
  const virtualizer = useVirtualizer({
    count: messages.length,
    // Defensively ensure a non-null scroll element is provided
    getScrollElement: () =>
      parentScrollRef.current ||
      (document.scrollingElement as HTMLElement) ||
      document.documentElement,
    estimateSize: () => DEFAULT_MESSAGE_ESTIMATE_SIZE,
    overscan: 5,
    paddingStart: 0,
    paddingEnd: 24,
  });

  // Find last user message index
  const lastUserMessageIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sender === 'user') {
        return i;
      }
    }
    return -1;
  }, [messages]);

  // Handle deterministic auto-scrolling to the user's latest question
  const isAutoScrollingRef = useRef(false);
  const previousMessageCountRef = useRef(messages.length);

  // 1. Detect when a new user message is added to trigger auto-scroll mode
  useEffect(() => {
    if (messages.length > previousMessageCountRef.current && lastUserMessageIndex !== -1) {
      isAutoScrollingRef.current = true;
    }
    previousMessageCountRef.current = messages.length;
  }, [messages.length, lastUserMessageIndex]);

  // 2. Track the message position as it streams using MutationObserver
  const isStreamingRef = useRef(false);
  useEffect(() => {
    const lastMessage = messages[messages.length - 1];
    isStreamingRef.current = !!(lastMessage && lastMessage.sender === 'bot' && (lastMessage.status === 'pending' || lastMessage.status === 'streaming'));
  }, [messages]);

  useEffect(() => {
    if (!isAutoScrollingRef.current || lastUserMessageIndex === -1) return;

    const container = parentScrollRef.current;
    if (!container) return;

    // To prevent the scroll position from jumping around due to React/Virtualizer 
    // asynchronous updates during rapid text streaming, we use a MutationObserver.
    // It watches for any DOM additions/sizing changes and instantly corrects the scroll position.

    let rafScheduled = false;

    const lockScrollPosition = () => {
      if (!isAutoScrollingRef.current) {
        rafScheduled = false;
        return;
      }

      const userMessageElement = container.querySelector(`[data-index="${lastUserMessageIndex}"]`);
      if (!userMessageElement) {
        // Fallback: tell virtualizer to find it if unmounted
        virtualizer.scrollToIndex(lastUserMessageIndex, { align: 'start', behavior: 'auto' });
        rafScheduled = false;
        return;
      }

      const containerRect = container.getBoundingClientRect();
      const messageRect = userMessageElement.getBoundingClientRect();

      const offsetFromTop = messageRect.top - containerRect.top;
      const targetOffset = 16; // Maintain the visual pt-4 padding gap

      const maxPossibleScrollTop = container.scrollHeight - container.clientHeight;
      const intendedScrollTop = container.scrollTop + (offsetFromTop - targetOffset);

      if (Math.abs(offsetFromTop - targetOffset) > 1 && intendedScrollTop <= maxPossibleScrollTop) {
        container.scrollTop = intendedScrollTop;
      } else if (intendedScrollTop > maxPossibleScrollTop && container.scrollTop !== maxPossibleScrollTop) {
        container.scrollTop = maxPossibleScrollTop;
      }
      rafScheduled = false;
    };

    // Run once immediately
    lockScrollPosition();

    // Set up observer to run synchronously whenever the DOM changes (text streams in)
    const observer = new MutationObserver(() => {
      if (!rafScheduled) {
        rafScheduled = true;
        requestAnimationFrame(lockScrollPosition);
      }
    });

    // Observe the container for any child list additions or character data changes
    observer.observe(container, {
      childList: true,
      subtree: true,
      characterData: true
    });

    let settleRAF: number | null = null;
    if (!isStreamingRef.current) {
      // Streaming finished; wait for the next two frames so the virtualizer can re-measure
      // and paint the final state before we unlock auto-scroll.
      settleRAF = requestAnimationFrame(() => {
        settleRAF = requestAnimationFrame(() => {
          isAutoScrollingRef.current = false;
          observer.disconnect();
        });
      });
    }

    return () => {
      if (settleRAF !== null) {
        cancelAnimationFrame(settleRAF);
      }
      observer.disconnect();
    };
  }, [messages.length, lastUserMessageIndex, virtualizer, parentScrollRef]);

  // 3. Cancel auto-scroll if the user manually interacts with the chat
  useEffect(() => {
    if (!scrollContainer) return;

    const handleUserInteraction = () => {
      isAutoScrollingRef.current = false;
    };

    // Listen to wheel and touch move to detect intent to manually scroll
    scrollContainer.addEventListener('wheel', handleUserInteraction, { passive: true });
    scrollContainer.addEventListener('touchmove', handleUserInteraction, { passive: true });

    return () => {
      scrollContainer.removeEventListener('wheel', handleUserInteraction);
      scrollContainer.removeEventListener('touchmove', handleUserInteraction);
    };
  }, [scrollContainer]);

  // Empty state
  if (!activeChat || activeChat.messages.length === 0) {
    return (
      <div className="w-full flex-1 py-6 flex flex-col items-center justify-center text-center">
        <div className="max-w-md space-y-4">
          <h2 className="font-poppins text-2xl text-text-primary">
            {activeChat ? 'Start the conversation' : 'Select or start a chat'}
          </h2>
          <p className="font-inter text-sm text-text-muted leading-relaxed">
            {activeChat
              ? "Ask me anything about voluntary carbon markets—methodologies, pricing, project case studies, or best practices. I'll keep track of our conversation here."
              : 'Choose an existing chat from the sidebar or create a new one to begin.'}
          </p>
        </div>
      </div>
    );
  }

  const virtualItems = virtualizer.getVirtualItems();

  return (
    <div
      ref={scrollContainerRef}
      className="w-full flex-1"
      role="log"
      aria-live="polite"
    >
      <div
        style={{
          height: `${virtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
          contain: 'layout paint',
        }}
      >
        {virtualItems.map((virtualRow) => {
          const message = messages[virtualRow.index];
          const isHighlighted = virtualRow.index === lastUserMessageIndex;

          return (
            <ChatMessageItem
              key={virtualRow.key}
              index={virtualRow.index}
              start={virtualRow.start}
              message={message}
              isHighlighted={isHighlighted}
              measure={virtualizer.measureElement}
            />
          );
        })}
      </div>
    </div>
  );
};
