import React from 'react';
import { motion } from 'framer-motion';
import { IconWrapper } from '@/components/icons/IconWrapper';
import ChatIcon from '@/assets/icons/chat.svg?react';
import { useChatContext } from '@/contexts/useChatContext';

interface SuggestedPromptsProps {
  prompts: string[];
  messageId: string;
}

/**
 * SuggestedPrompts displays follow-up question suggestions below a bot message.
 *
 * Design:
 * - Positioned below a soft, premium divider with extra breathing space
 * - Custom brand Chat icon as a visual anchor representing conversational next-steps
 * - Prompts appear as clickable chips with smooth hover states and a subtle lift
 */
export const SuggestedPrompts: React.FC<SuggestedPromptsProps> = ({ prompts, messageId }) => {
  const { sendMessage, isTyping } = useChatContext();

  if (!prompts || prompts.length === 0) return null;

  const handlePromptClick = (prompt: string) => {
    if (isTyping || !prompt.trim()) return;
    sendMessage(prompt.trim());
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1], delay: 0.1 }}
      className="mt-6 pt-5 border-t border-surface-subtle w-full"
    >
      {/* Label row */}
      <div className="flex items-center gap-2 mb-3">
        <div className="flex items-center justify-center w-5 h-5 rounded-md bg-brand-500/[0.08]">
          <IconWrapper Icon={ChatIcon} size={12} color="currentColor" className="text-brand-700" />
        </div>
        <span className="font-inter text-xs font-semibold text-brand-700 uppercase tracking-wider">
          Follow-up questions
        </span>
      </div>

      {/* Prompt chips */}
      <div className="flex flex-wrap gap-2">
        {prompts.map((prompt, index) => (
          <motion.button
            key={`${messageId}-prompt-${index}`}
            type="button"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.3,
              ease: [0.4, 0, 0.2, 1],
              delay: 0.15 + index * 0.06,
            }}
            whileTap={isTyping ? {} : { scale: 0.98 }}
            onClick={() => handlePromptClick(prompt)}
            disabled={isTyping}
            className={`group flex items-center gap-2 px-3.5 py-2 rounded-xl border text-left transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 ${
              isTyping
                ? 'border-border-ui bg-surface-subtle/50 cursor-not-allowed opacity-50'
                : 'border-border-ui bg-surface-card hover:bg-surface-subtle hover:shadow-sm hover:border-border-ui'
            }`}
          >
            <span className={`font-inter text-sm leading-snug ${
              isTyping ? 'text-text-muted' : 'text-text-secondary'
            }`}>
              {prompt}
            </span>
            <svg
              className="w-3.5 h-3.5 flex-shrink-0 text-text-muted"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </motion.button>
        ))}
      </div>
    </motion.div>
  );
};
