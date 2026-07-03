import React, { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { ThumbsUp, ThumbsDown, Loader2 } from 'lucide-react';
import {
  submitFeedback,
  FEEDBACK_TAGS,
  type FeedbackRating,
  type FeedbackTag,
} from '@/services/feedbackApi';

interface MessageFeedbackProps {
  messageId: string;
  chatId?: string;
  userId?: string;
  userQuery?: string;
  botAnswer?: string;
}

interface FeedbackStatus {
  type: 'success' | 'error';
  text: string;
}

/**
 * MessageFeedback - Thumbs up / thumbs down widget rendered below each completed
 * bot response. On thumbs-down it reveals an inline tag-chip panel with an
 * optional comment box before submission.
 */
export const MessageFeedback: React.FC<MessageFeedbackProps> = ({
  messageId,
  chatId,
  userId,
  userQuery,
  botAnswer,
}) => {
  const shouldReduceMotion = useReducedMotion();
  const [selectedRating, setSelectedRating] = useState<FeedbackRating | null>(null);
  const [isNegativePanelOpen, setIsNegativePanelOpen] = useState(false);
  const [selectedTags, setSelectedTags] = useState<Set<FeedbackTag>>(new Set());
  const [comment, setComment] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [status, setStatus] = useState<FeedbackStatus | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Abort in-flight requests on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      abortRef.current = null;
    };
  }, []);

  const getErrorMessage = (error: unknown) => {
    if (error instanceof Error && error.message.trim()) {
      return error.message;
    }
    return 'Failed to submit feedback. Please try again.';
  };

  const isAbortError = (error: unknown) =>
    (error instanceof DOMException && error.name === 'AbortError') ||
    (typeof error === 'object' && error !== null && 'name' in error && error.name === 'AbortError');

  const handleThumbsUp = async () => {
    if (isSubmitted || isSubmitting) return;

    setSelectedRating('positive');
    setIsNegativePanelOpen(false);
    setSelectedTags(new Set());
    setComment('');
    setStatus(null);
    setIsSubmitting(true);

    try {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      await submitFeedback({ messageId, chatId, userId, rating: 'positive', userQuery, botAnswer }, controller.signal);

      setIsSubmitted(true);
      setStatus({ type: 'success', text: 'Thanks for the feedback.' });
    } catch (error) {
      if (isAbortError(error)) return;
      setStatus({ type: 'error', text: getErrorMessage(error) });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleThumbsDown = () => {
    if (isSubmitted || isSubmitting) return;

    setSelectedRating('negative');
    setStatus(null);
    setIsNegativePanelOpen(true);

    // Focus the panel after next paint
    setTimeout(() => textareaRef.current?.focus(), 50);
  };

  const handleTagToggle = (tag: FeedbackTag) => {
    setSelectedTags((previous) => {
      const next = new Set(previous);
      if (next.has(tag)) {
        next.delete(tag);
      } else {
        next.add(tag);
      }
      return next;
    });
  };

  const handleCancel = () => {
    if (isSubmitting) return;
    setIsNegativePanelOpen(false);
    setSelectedRating(null);
    setSelectedTags(new Set());
    setComment('');
    setStatus(null);
  };

  const handleSubmit = async () => {
    if (!isNegativePanelOpen || isSubmitting || isSubmitted) return;

    setStatus(null);
    setIsSubmitting(true);

    try {
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      await submitFeedback(
        {
          messageId,
          chatId,
          userId,
          rating: 'negative',
          tags: Array.from(selectedTags),
          comment: comment.trim(),
          userQuery,
          botAnswer,
        },
        controller.signal
      );

      setIsSubmitted(true);
      setIsNegativePanelOpen(false);
      setStatus({ type: 'success', text: 'Thanks for the feedback.' });
    } catch (error) {
      if (isAbortError(error)) return;
      setStatus({ type: 'error', text: getErrorMessage(error) });
    } finally {
      setIsSubmitting(false);
    }
  };

  // Derived helpers
  const isPositiveActive = selectedRating === 'positive';
  const isNegativeActive = selectedRating === 'negative';
  const isNegativeSelected = isNegativeActive || isNegativePanelOpen;
  const submitDisabled = selectedTags.size === 0 && !comment.trim();

  return (
    <div className="flex flex-col gap-1.5">
      {/* Thumbs row */}
      <div className="flex items-center gap-0.5">
        {/* Thumbs Up */}
        <button
          type="button"
          disabled={isSubmitted || isSubmitting}
          onClick={handleThumbsUp}
          aria-label="Good response"
          aria-pressed={isPositiveActive}
          title="Good response"
          className={`flex items-center justify-center w-6 h-6 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
            ${isPositiveActive
              ? 'text-semantic-success-icon'
              : isSubmitted || isSubmitting
                ? 'text-text-disabled cursor-not-allowed'
                : 'text-text-muted hover:text-semantic-success-icon hover:bg-semantic-success-bg'
            }`}
        >
          <motion.span
            animate={
              shouldReduceMotion
                ? { scale: 1, rotate: 0 }
                : isPositiveActive
                  ? { scale: [1, 1.3, 1], rotate: [0, -8, 0] }
                  : { scale: 1, rotate: 0 }
            }
            transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.35, ease: 'easeOut' }}
            className="inline-flex"
          >
            <ThumbsUp
              className="h-3.5 w-3.5"
              fill={isPositiveActive ? 'currentColor' : 'none'}
              strokeWidth={isPositiveActive ? 0 : 1.75}
            />
          </motion.span>
        </button>

        {/* Thumbs Down */}
        <button
          type="button"
          disabled={isSubmitted || isSubmitting}
          onClick={handleThumbsDown}
          aria-label="Bad response"
          aria-pressed={isNegativeSelected}
          title="Bad response"
          className={`flex items-center justify-center w-6 h-6 rounded transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
            ${isNegativeSelected
              ? 'text-semantic-error-icon'
              : isSubmitted || isSubmitting
                ? 'text-text-disabled cursor-not-allowed'
                : 'text-text-muted hover:text-semantic-error-icon hover:bg-semantic-error-bg'
            }`}
        >
          <motion.span
            animate={
              shouldReduceMotion
                ? { x: 0 }
                : isNegativeSelected
                  ? { x: [0, -2, 2, -2, 2, 0] }
                  : { x: 0 }
            }
            transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.35, ease: 'easeInOut' }}
            className="inline-flex"
          >
            <ThumbsDown
              className="h-3.5 w-3.5"
              fill={isNegativeSelected ? 'currentColor' : 'none'}
              strokeWidth={isNegativeSelected ? 0 : 1.75}
            />
          </motion.span>
        </button>

        {/* Success confirmation text */}
        {status?.type === 'success' && (
          <motion.span
            initial={shouldReduceMotion ? { opacity: 1, x: 0 } : { opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }}
            className="ml-2 font-inter text-xs text-semantic-success-icon font-medium select-none"
          >
            {status.text}
          </motion.span>
        )}

        {/* Error confirmation text */}
        {status?.type === 'error' && (
          <motion.span
            initial={shouldReduceMotion ? { opacity: 1, x: 0 } : { opacity: 0, x: -4 }}
            animate={{ opacity: 1, x: 0 }}
            transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.2, ease: 'easeOut' }}
            className="ml-2 font-inter text-xs text-semantic-error-text font-medium select-none"
          >
            {status.text}
          </motion.span>
        )}
      </div>

      {/* Slide-down negative feedback panel */}
      {isNegativePanelOpen && (
        <div
          className="mt-0.5 rounded-xl border border-border-ui bg-surface-card p-3.5 shadow-sm"
          role="group"
          aria-label="Tell us what went wrong"
        >
          <p className="font-inter text-xs font-medium text-text-secondary mb-2.5">
            What went wrong?
          </p>

          {/* Tag chips */}
          <div className="flex flex-wrap gap-1.5 mb-3" role="group" aria-label="Feedback categories">
            {FEEDBACK_TAGS.map((tag) => {
              const selected = selectedTags.has(tag);
              return (
                <button
                  key={tag}
                  type="button"
                  onClick={() => handleTagToggle(tag)}
                  aria-pressed={selected}
                  className={`inline-flex items-center px-2.5 py-1 rounded-full font-inter text-xs font-medium border transition-all duration-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2
                    ${selected
                      ? 'border-brand-900 bg-brand-100 text-brand-900'
                      : 'border-border-ui bg-surface-card text-text-muted hover:border-brand-200 hover:text-brand-900'
                    }`}
                >
                  {selected && (
                    <svg
                      className="mr-1 h-2.5 w-2.5 flex-shrink-0"
                      viewBox="0 0 10 8"
                      fill="none"
                      aria-hidden="true"
                    >
                      <path
                        d="M1 4L3.5 6.5L9 1"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  )}
                  {tag}
                </button>
              );
            })}
          </div>

          {/* Optional comment */}
          <textarea
            ref={textareaRef}
            value={comment}
            onChange={(e) => setComment(e.target.value.slice(0, 500))}
            placeholder="Tell us more (optional)"
            rows={2}
            className="w-full px-3 py-2 rounded-lg border border-border-ui font-inter text-xs text-text-primary placeholder:text-text-muted bg-surface-card outline-none resize-none leading-relaxed focus:border-brand-900 focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 transition-all"
          />

          {/* Actions */}
          <div className="flex items-center justify-end gap-2 mt-2.5">
            <button
              type="button"
              onClick={handleCancel}
              disabled={isSubmitting}
              aria-disabled={isSubmitting}
              className="font-inter text-xs text-text-muted hover:text-text-secondary transition-colors px-2 py-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:text-text-muted"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={submitDisabled || isSubmitting}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-brand-900 text-white font-inter text-xs font-semibold hover:bg-brand-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
            >
              Submit
            </button>
          </div>
        </div>
      )}

      {/* Submitting overlay-state (if panel was open) */}
      {isSubmitting && isNegativePanelOpen && (
        <div className="flex items-center gap-1.5 text-text-muted">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span className="font-inter text-xs">Submitting…</span>
        </div>
      )}
    </div>
  );
};
