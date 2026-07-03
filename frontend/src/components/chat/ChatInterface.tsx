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
 * - Stick-to-bottom auto-scroll on new messages (cancelled on manual scroll)
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

  // Simple stick-to-bottom: scroll to bottom when a new message is added
  // or when the last message transitions out of 'pending' (the placeholder
  // is replaced by the full answer, which is much taller). Status updates
  // only change the pending bubble's text, not its height class, so we
  // don't need to scroll on every content update.
  const stickToBottomRef = useRef(true);
  const previousMessageCountRef = useRef(messages.length);
  const previousLastMessageStatusRef = useRef<string | undefined>(undefined);

  const lastMessageStatus = messages.length > 0
    ? messages[messages.length - 1].status
    : undefined;

  useEffect(() => {
    const container = parentScrollRef.current;
    if (!container) return;
    const countChanged = messages.length > previousMessageCountRef.current;
    const lastMessageCompleted = (
      previousLastMessageStatusRef.current === 'pending' &&
      lastMessageStatus !== 'pending'
    );
    if (countChanged || lastMessageCompleted) {
      stickToBottomRef.current = true;
    }
    previousMessageCountRef.current = messages.length;
    previousLastMessageStatusRef.current = lastMessageStatus;
    if (stickToBottomRef.current) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages.length, lastMessageStatus, parentScrollRef]);

  // Cancel stick-to-bottom when the user manually scrolls up
  useEffect(() => {
    if (!scrollContainer) return;

    const handleUserInteraction = () => {
      const container = parentScrollRef.current;
      if (!container) return;
      const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      stickToBottomRef.current = distanceFromBottom < 80;
    };

    scrollContainer.addEventListener('wheel', handleUserInteraction, { passive: true });
    scrollContainer.addEventListener('touchmove', handleUserInteraction, { passive: true });

    return () => {
      scrollContainer.removeEventListener('wheel', handleUserInteraction);
      scrollContainer.removeEventListener('touchmove', handleUserInteraction);
    };
  }, [scrollContainer, parentScrollRef]);

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
