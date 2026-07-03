import React, { useState, KeyboardEvent, useEffect, useRef } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { Square } from "lucide-react";
import { IconWrapper } from "@/components/icons/IconWrapper";
import ArrowUpIcon from "@/assets/icons/arrow-up.svg?react";
import { useChatContext } from "@/contexts/useChatContext";
import { sanitizeInput } from "@/lib/security";
import { useIsMobile } from "@/hooks/use-mobile";
import { useChatReadiness } from "@/hooks/useChatReadiness";
import { TEXT } from "@/lib/colors";

// Static constants moved to module scope to avoid recreation on every render
const LARGE_MAX_ROWS = 6;
const COMPOSER_DESKTOP_MAX_ROWS = 5;
const COMPOSER_MOBILE_MAX_ROWS = 3;

interface SearchBarProps {
  onTypingStateChange?: (isTyping: boolean) => void;
  variant?: 'large' | 'composer';
}

export const SearchBar: React.FC<SearchBarProps> = ({ onTypingStateChange, variant = 'composer' }) => {
  const [message, setMessage] = useState("");
  const { sendMessage, stopActiveRequest, isTyping } = useChatContext();
  const { chatReady, isLoading, disabledPlaceholder } = useChatReadiness();
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const isMobileViewport = useIsMobile();
  const shouldReduceMotion = useReducedMotion();

  // The composer is disabled while the backend is unreachable or while the
  // chat is not ready (no KB docs and no web search). Ongoing generations keep
  // the stop button active.
  const inputDisabled = isLoading || (!isTyping && !chatReady);

  // Notify parent components when typing state changes
  useEffect(() => {
    if (onTypingStateChange) {
      onTypingStateChange(message.length > 0);
    }
  }, [message, onTypingStateChange]);

  const handleSubmit = () => {
    const trimmedMessage = message.trim();
    if (trimmedMessage === "") return;
    // Prevent submission if the chat is not ready (backend down, no LLM, no source).
    if (inputDisabled) return;

    // Sanitize user input before sending it to the chat context
    const sanitizedMessage = sanitizeInput(trimmedMessage);

    sendMessage(sanitizedMessage);
    setMessage("");

    // Reset textarea height after submit
    if (textareaRef.current) {
      const ta = textareaRef.current;
      ta.style.height = 'auto';
      ta.style.overflowY = 'hidden';
      // Return focus to composer for quick follow-up
      ta.focus();
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleStopRequest = () => {
    if (!isTyping) return;
    stopActiveRequest();
  };

  // Cache line height to avoid repeated getComputedStyle calls (forced reflow)
  const lineHeightRef = useRef<number | null>(null);
  
  const autoGrow = (el: HTMLTextAreaElement, rowsLimit: number) => {
    // Only compute line height once per mount
    if (lineHeightRef.current === null) {
      const computed = window.getComputedStyle(el);
      const lh = parseFloat(computed.lineHeight);
      lineHeightRef.current = (Number.isNaN(lh) || lh <= 0) ? 20 : lh;
    }
    
    const maxHeight = lineHeightRef.current * rowsLimit;
    
    // Batch DOM reads before writes to minimize reflow
    el.style.height = 'auto';
    const scrollH = el.scrollHeight;
    
    // Now write
    el.style.height = `${Math.min(scrollH, maxHeight)}px`;
    el.style.overflowY = scrollH > maxHeight ? 'auto' : 'hidden';
  };

  const isLarge = variant === 'large';
  const rowsLimit = isLarge
    ? LARGE_MAX_ROWS
    : (isMobileViewport ? COMPOSER_MOBILE_MAX_ROWS : COMPOSER_DESKTOP_MAX_ROWS);

  // Keep height in sync when message changes externally (e.g., clearing)
  useEffect(() => {
    if (textareaRef.current) {
      autoGrow(textareaRef.current, rowsLimit);
    }
  }, [message, rowsLimit]);

  const containerClasses = isLarge
    ? "relative w-full max-w-5xl mx-auto"
    : "relative w-full";

  const wrapperClasses = isLarge
    ? `relative flex w-full items-center gap-3 md:gap-4 rounded-2xl md:rounded-3xl border bg-surface-card px-4 md:px-6 py-2.5 md:py-3.5 min-h-touch md:min-h-touch-lg shadow-card-md transition-colors ${inputDisabled ? 'border-border-ui bg-surface-subtle/60 opacity-80' : 'border-border-ui'}`
    : `relative flex w-full items-center gap-2 md:gap-3 rounded-xl md:rounded-3xl border bg-surface-card px-3 md:px-5 py-2 md:py-3 min-h-touch shadow-card-sm transition-colors ${inputDisabled ? 'border-border-ui bg-surface-subtle/60 opacity-80' : 'border-border-ui'}`;

  const textareaClasses = isLarge
    ? "resize-none font-inter font-normal text-sm md:text-base leading-relaxed text-text-secondary bg-transparent border-none outline-none w-full placeholder:text-text-muted disabled:opacity-60"
    : "resize-none font-inter font-normal text-sm leading-5 text-text-primary bg-transparent border-none outline-none w-full placeholder:text-text-muted disabled:opacity-60";

  const getButtonStyles = (largeVariant: boolean, typingState: boolean, isEmpty: boolean, isMobile: boolean) => {
    const baseClasses = "relative flex items-center justify-center rounded-xl transition-all duration-200 focus:outline-none disabled:opacity-60 disabled:cursor-not-allowed shrink-0";
    const sizeClasses = largeVariant 
      ? (isMobile ? "w-11 h-11" : "w-11 h-11 md:w-12 md:h-12")
      : (isMobile ? "w-11 h-11" : "w-11 h-11");
    const focusClasses = "focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-card";

    // Stop state (Active typing)
    if (typingState) {
      return {
        className: `${baseClasses} ${sizeClasses} ${focusClasses} border border-border-ui bg-surface-card hover:bg-surface-base hover:border-border-ui shadow-sm transition-all duration-200`,
        iconColor: TEXT.muted,
        showStop: true
      };
    }

    // Empty state
    if (isEmpty) {
      return {
        className: `${baseClasses} ${sizeClasses} ${focusClasses} border border-border-ui bg-surface-subtle text-text-disabled`,
        iconColor: largeVariant ? TEXT.muted : TEXT.disabled,
        showStop: false
      };
    }

    // Active send state
    return {
      className: `${baseClasses} ${sizeClasses} ${focusClasses} border border-brand-500 bg-brand-500 hover:bg-brand-700 text-white ${largeVariant ? 'shadow-card-md' : ''}`,
      iconColor: TEXT.inverse,
      showStop: false
    };
  };

  const buttonStyles = getButtonStyles(isLarge, isTyping, message.trim() === '' || inputDisabled, isMobileViewport);

  return (
    <div className="w-full">
      <div className={containerClasses}>
        {/* Glow effect background for large variant */}
        {isLarge && (
          <div 
            className="absolute inset-0 rounded-3xl opacity-40 blur-2xl pointer-events-none" 
            style={{
              background: 'var(--glow-searchbar)',
              zIndex: -1
            }}
            aria-hidden="true"
          />
        )}
        <div className={wrapperClasses}>
          <textarea
            ref={textareaRef}
            rows={1}
            value={message}
            onChange={(e) => {
              if (inputDisabled && !isTyping) return;
              setMessage(e.target.value);
              autoGrow(e.currentTarget, rowsLimit);
            }}
            onKeyDown={handleKeyDown}
            placeholder={inputDisabled ? disabledPlaceholder : (isLarge ? "Ask me anything about the VCM" : "Type your message")}
            aria-label="Chat message input"
            title={inputDisabled ? disabledPlaceholder : "Enter to send • Shift+Enter for newline"}
            disabled={inputDisabled}
            className={`${textareaClasses} flex items-center`}
            style={{
              paddingTop: isMobileViewport ? '0.25rem' : '0.375rem',
              paddingBottom: isMobileViewport ? '0.25rem' : '0.375rem'
            }}
          />

          <motion.button
            aria-label={isTyping ? "Stop generating response" : "Send message"}
            onClick={isTyping ? handleStopRequest : handleSubmit}
            title={inputDisabled ? disabledPlaceholder : (isTyping ? "Stop generating response" : "Enter to send • Shift+Enter for newline")}
            disabled={inputDisabled || (!isTyping && message.trim() === '')}
            aria-busy={isTyping}
            className={`${buttonStyles.className} group`}
            style={{ aspectRatio: '1/1' }}
            whileTap={shouldReduceMotion ? undefined : { scale: 0.92 }}
            transition={shouldReduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 500, damping: 25 }}
          >
            <div className="flex h-full w-full items-center justify-center">
              <AnimatePresence mode="popLayout" initial={false}>
                {buttonStyles.showStop ? (
                  <motion.span
                    key="stop"
                    initial={shouldReduceMotion ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.7 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={shouldReduceMotion ? { opacity: 1, scale: 1 } : { opacity: 0, scale: 0.7 }}
                    transition={shouldReduceMotion ? { duration: 0 } : { duration: 0.15 }}
                    className="flex items-center justify-center"
                  >
                    <Square className="w-3 h-3 fill-text-muted text-text-muted rounded-sm" />
                  </motion.span>
                ) : (
                  <motion.span
                    key={message.trim() === '' ? 'idle' : 'ready'}
                    initial={shouldReduceMotion ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: 4, scale: 0.85 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={shouldReduceMotion ? { opacity: 1, y: 0, scale: 1 } : { opacity: 0, y: -4, scale: 0.85 }}
                    transition={shouldReduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 500, damping: 22 }}
                    className="flex items-center justify-center"
                  >
                    <IconWrapper
                      Icon={ArrowUpIcon}
                      size={20}
                      color={buttonStyles.iconColor}
                    />
                  </motion.span>
                )}
              </AnimatePresence>
            </div>
          </motion.button>
        </div>
      </div>

      <div className="mt-3 md:mt-4 w-full">
        <p className="text-text-muted text-2xs md:text-xs font-normal text-center w-full">
          Cora is still in development and can make mistakes
        </p>
      </div>
    </div>
  );
}
