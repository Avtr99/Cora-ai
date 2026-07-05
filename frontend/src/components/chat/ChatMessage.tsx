import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Message } from '@/store/chatStore.types';
import { Copy, Check } from 'lucide-react';
import { CitationBadges } from './CitationBadges';
import { RecommendationCard, RecommendationType, Recommendation } from './RecommendationCard';
import { RECOMMENDATION_BY_ID } from './recommendations';
import './markdown-styles.css';
import { useChatContext } from '@/contexts/useChatContext';
import { useUserContext } from '@/contexts/useUserContext';
import { ChatMarkdownContent } from './ChatMarkdownContent';
import { parseCitationSources } from './chatMessageCitations.utils';
import type { CitationNumberMap } from './ChatMarkdownContent';
import { MessageFeedback } from './MessageFeedback';
import { QuizWidget } from './QuizWidget';
import { SuggestedPrompts } from './SuggestedPrompts';
import { AgentReasoningSection } from './AgentReasoningSection';
import { RetryButton } from './RetryButton';

interface ChatMessageProps {
  /** The message data to display */
  message: Message;
  /** Whether to show agent reasoning steps (default: true) */
  showAgentReasoning?: boolean;
}

/**
 * Renders a single chat message (user or bot).
 *
 * Features:
 * - User messages: clean bubble with copy button
 * - Bot messages: avatar, reasoning steps (collapsible), citations, feedback
 * - Auto-fade-in on mount for smooth UX
 * - Retry buttons for error/cancelled states
 *
 * @example
 * <ChatMessage message={message} showAgentReasoning={true} />
 */
export const ChatMessage: React.FC<ChatMessageProps> = ({ message, showAgentReasoning = true }) => {
  const isUser = message.sender === 'user';
  const [copied, setCopied] = useState(false);
  const { retryLastUserMessage, retryErrorMessage, activeChat } = useChatContext();
  const { userProfile } = useUserContext();
  const [isRetrying, setIsRetrying] = useState(false);
  const bubbleRef = useRef<HTMLDivElement | null>(null);
  const [mounted, setMounted] = useState(false);

  // Find the user's query message for feedback context.
  // Select only the messages array to avoid recomputing when unrelated chat
  // properties (e.g. title, backendConversationId) change.
  const messages = activeChat?.messages;
  const userQuery = useMemo(() => {
    if (isUser || !messages) return '';
    const messageIndex = messages.findIndex(m => m.id === message.id);
    if (messageIndex === -1) return '';
    // Find the previous user message
    for (let i = messageIndex - 1; i >= 0; i--) {
      if (messages[i].sender === 'user') {
        return messages[i].content;
      }
    }
    return '';
  }, [isUser, messages, message.id]);

  const botAnswer = !isUser ? message.content : '';
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 10);
    return () => clearTimeout(t);
  }, []);

  const steps = (!isUser && message.agentReasoning && showAgentReasoning) ? message.agentReasoning : [];

  const copyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (err) {
      console.error('Copy to clipboard failed', err);
    }
  };

  const isErrorMessage = !isUser && message.status === 'error';
  const isCancelledMessage = !isUser && message.status === 'cancelled';
  const handleRetry = async () => {
    // Targeted retry: update this error/cancelled bubble in place for the specific question
    if (isErrorMessage || isCancelledMessage) {
      try {
        setIsRetrying(true);
        await retryErrorMessage(message.id);
      } finally {
        setIsRetrying(false);
        // Scroll to the updated bubble for immediate feedback
        setTimeout(() => {
          bubbleRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          bubbleRef.current?.focus({ preventScroll: true });
        }, 50);
      }
    } else {
      // Fallback (shouldn't happen because Retry shows only on error/cancelled bubbles)
      await retryLastUserMessage();
    }
  };

  const isPending = !isUser && message.status === 'pending';

  const sourceLinks = useMemo(() => {
    if (isUser || isErrorMessage || isCancelledMessage || isPending) {
      return [];
    }
    // Try citations first (has structured details with URLs, source types, etc.)
    if (message.citations) {
      const citationLinks = parseCitationSources(message.citations);
      // If citations produced results, use them
      if (citationLinks.length > 0) {
        return citationLinks;
      }
      // Otherwise fall through to message.sources (web search often has empty citations but populated sources)
    }
    // Fallback to top-level sources (used by web search when citations.details is empty)
    if (Array.isArray(message.sources) && message.sources.length > 0) {
      return parseCitationSources({ sources: message.sources });
    }
    return [];
  }, [isUser, isErrorMessage, isCancelledMessage, isPending, message.citations, message.sources]);

  // Build a single global numbering sequence for all sources. The backend emits
  // per-type citations (KB 1..N, Web 1..M); we map those to the global index of
  // the matching source in sourceLinks so the inline markers and the source list
  // share one linear, unbroken sequence.
  const citationNumberMap = useMemo<CitationNumberMap>(() => {
    const kb: number[] = [];
    const web: number[] = [];
    sourceLinks.forEach((source, index) => {
      const globalNumber = index + 1;
      if (source.type === 'knowledge_base') {
        kb.push(globalNumber);
      } else {
        web.push(globalNumber);
      }
    });
    return { kb, web };
  }, [sourceLinks]);

  const shouldShowRecommendations = !isUser && !isErrorMessage && !isCancelledMessage && !isPending && message.triggeredRecommendationIds && message.triggeredRecommendationIds.length > 0;

  const recommendationsToShow = useMemo(() => {
    if (!shouldShowRecommendations || !message.triggeredRecommendationIds) return [];

    // Use the specific recommendation IDs that were triggered
    // Lookup is O(1) per ID using RECOMMENDATION_BY_ID map
    return message.triggeredRecommendationIds
      .map(id => RECOMMENDATION_BY_ID[id])
      .filter((rec): rec is Recommendation => Boolean(rec));
  }, [shouldShowRecommendations, message.triggeredRecommendationIds]);

  return (
    <div className="flex w-full justify-center">
      <div className="flex flex-col w-full max-w-2xl">
        {/* User message comes first */}
        {isUser && (
          <div>
            <p className="font-inter font-semibold text-lg md:text-xl leading-[1.2] md:leading-[30px] text-text-primary mb-0">{message.content}</p>
          </div>
        )}

        {!isUser && steps.length > 0 && <AgentReasoningSection steps={steps} />}

        {/* Bot Message Content */}
        {!isUser && (
          <div className="flex flex-col w-full pb-2">
            <div
              ref={bubbleRef}
              tabIndex={-1}
              className="relative">

              {isErrorMessage ? (
                <div className="flex flex-col items-start gap-2 bg-semantic-error-bg border border-semantic-error-border rounded-md p-3 text-semantic-error-text">
                  <p className="font-inter text-sm leading-relaxed">{message.content}</p>
                  <RetryButton onClick={handleRetry} disabled={isRetrying} />
                </div>
              ) : isCancelledMessage ? (
                <div className="flex flex-col items-start gap-2 bg-brand-50 border border-brand-200 rounded-md p-3 text-brand-900">
                  <p className="font-inter text-sm leading-relaxed">{message.content}</p>
                  <RetryButton onClick={handleRetry} disabled={isRetrying} />
                </div>
              ) : isPending ? (
                <div className="flex items-center gap-2 py-2 mt-1">
                  <span className="relative flex h-4 w-4 items-center justify-center">
                    <span className="animate-pulse-dot absolute inline-flex h-2 w-2 rounded-full bg-text-muted opacity-50"></span>
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-text-muted"></span>
                  </span>
                  <span className="font-inter font-normal text-sm text-text-muted">
                    {message.content || 'Analyzing request...'}
                  </span>
                </div>
              ) : (
                <ChatMarkdownContent
                  content={message.content}
                  messageId={message.id}
                  mounted={mounted}
                  copyText={copyText}
                  citationNumberMap={citationNumberMap}
                />
              )}
            </div>

            {/* Action bar: feedback (left) + copy (right) */}
            {!isErrorMessage && !isCancelledMessage && !isPending && (
              <div className="flex items-start justify-between mt-1">
                <MessageFeedback
                  messageId={message.id}
                  chatId={activeChat?.id}
                  userId={userProfile?.id}
                  userQuery={userQuery}
                  botAnswer={botAnswer}
                />
                <button
                  type="button"
                  onClick={async () => {
                    await copyText(message.content);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  }}
                  className={`flex items-center text-xs font-medium flex-shrink-0 px-2.5 py-1 rounded-md border transition-all duration-150 active:scale-[0.97] min-w-[72px] justify-center ${
                    copied 
                      ? 'text-text-primary bg-surface-subtle border-border-ui' 
                      : 'text-text-muted bg-transparent border-transparent hover:text-text-secondary hover:bg-surface-subtle hover:border-border-ui/50'
                  }`}
                  aria-label={copied ? 'Copied' : 'Copy answer'}
                  title={copied ? 'Copied' : 'Copy answer'}
                >
                  <AnimatePresence mode="wait" initial={false}>
                    {copied ? (
                      <motion.span
                        key="copied"
                        className="flex items-center gap-1"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.1 }}
                      >
                        <Check className="h-3 w-3 stroke-[2.5] text-semantic-success-icon" />
                        <span>Copied</span>
                      </motion.span>
                    ) : (
                      <motion.span
                        key="copy"
                        className="flex items-center gap-1"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.1 }}
                      >
                        <Copy className="h-3 w-3 stroke-[2]" />
                        <span>Copy</span>
                      </motion.span>
                    )}
                  </AnimatePresence>
                </button>
              </div>
            )}

            {/* Sources Section - Citation badges */}
            {sourceLinks.length > 0 && <CitationBadges sources={sourceLinks} messageId={message.id} />}

            {/* Render the QuizWidget if the backend provided a quiz for this bot message */}
            {!isUser && !isErrorMessage && !isCancelledMessage && !isPending && message.quiz && (
              <QuizWidget quiz={message.quiz} />
            )}

            {/* Render suggested follow-up prompts from the backend */}
            {!isUser && !isErrorMessage && !isCancelledMessage && !isPending && message.suggestedPrompts && (
              <SuggestedPrompts prompts={message.suggestedPrompts} messageId={message.id} />
            )}
          </div>
        )}

        {/* Recommendations based solely on triggeredRecommendations (deduped by ChatContext) */}
        {shouldShowRecommendations && recommendationsToShow.length > 0 && (
          <div className="mt-4 w-full mb-4">
            <p className="font-inter text-xs font-normal text-text-muted mb-2">You might also be interested in</p>
            <div className="flex flex-col gap-2">
              {recommendationsToShow.map(recommendation => (
                <div key={recommendation.id}>
                  <RecommendationCard recommendation={recommendation} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};



export const TypingIndicator: React.FC = () => {
  return (
    <div className="flex w-full justify-center mb-4 mt-4">
      <div className="flex max-w-2xl w-full">
        <div className="pl-2" aria-live="polite" aria-atomic="true">
          <div className="flex items-center">
            <div className="flex space-x-1">
              <div className="w-2 h-2 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
              <div className="w-2 h-2 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
              <div className="w-2 h-2 bg-brand-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
