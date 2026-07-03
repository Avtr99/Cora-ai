import React, { useCallback } from 'react';
import { ChatMessage } from './ChatMessage';
import type { Message } from '@/store/chatStore.types';

interface ChatMessageItemProps {
  index: number;
  start: number;
  message: Message;
  isHighlighted: boolean;
  measure: (el: Element) => void;
}

/**
 * Stable, memoized message item for virtualized rendering.
 * Prevents remounts that cause flicker during scroll.
 */
export const ChatMessageItem = React.memo(({
  index,
  start,
  message,
  isHighlighted,
  measure,
}: ChatMessageItemProps) => {
  const isStreaming = message.status === 'streaming' || message.status === 'pending';

  const setRef = useCallback((node: HTMLDivElement | null) => {
    if (node && !isStreaming) {
      measure(node);
    }
  }, [measure, isStreaming]);

  return (
    <div
      data-index={index}
      ref={setRef}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        transform: `translate3d(0, ${start}px, 0)`,
        willChange: 'transform',
        backfaceVisibility: 'hidden',
        contain: 'layout paint',
      }}
      className="pb-2"
    >
      <div className={isHighlighted ? 'pt-4' : ''}>
        <ChatMessage message={message} />
      </div>
    </div>
  );
});

ChatMessageItem.displayName = 'ChatMessageItem';
