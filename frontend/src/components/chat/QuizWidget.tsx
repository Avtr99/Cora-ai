import React, { useState } from 'react';
import { QuizResponse } from '@/services/coraApi';
import { Check, X, AlertCircle, ArrowRight } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface QuizWidgetProps {
  quiz: QuizResponse;
}

const LETTER_MAP = ['A', 'B', 'C', 'D', 'E', 'F'];

export const QuizWidget: React.FC<QuizWidgetProps> = ({ quiz }) => {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [isCorrect, setIsCorrect] = useState<boolean | null>(null);

  const handleOptionClick = (index: number) => {
    if (selectedIndex !== null) return;
    setSelectedIndex(index);
    setIsCorrect(index === quiz.correctIndex);
  };

  const handleTryAgain = () => {
    setSelectedIndex(null);
    setIsCorrect(null);
  };

  return (
    <motion.div 
      layout="position"
      transition={{ type: 'spring', stiffness: 350, damping: 35 }}
      className="my-4 w-full max-w-3xl bg-surface-card border border-border-ui/60 rounded-2xl p-4 sm:p-4.5 shadow-sm flex flex-col gap-3"
    >
        
      {/* Header Label - Strict Minimalism */}
      <div>
        <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-brand-500/[0.08] text-brand-700 text-2xs font-bold uppercase tracking-[0.16em] font-inter">
          Knowledge Check
        </span>
      </div>

      {/* Question */}
      <h3 className="font-inter text-text-primary font-medium text-[14.5px] leading-relaxed">
        {quiz.question}
      </h3>

      {/* Options */}
      <div className="flex flex-col gap-1.5" role="radiogroup">
        {quiz.options.map((option, index) => {
          const isSelected = selectedIndex === index;
          const isAnswered = selectedIndex !== null;
          const isThisCorrect = index === quiz.correctIndex;
          
          // Base states - Highly refined
          let stateClass = 'hover:border-brand-500/30 hover:bg-brand-500/[0.02] hover:shadow-sm border-border-ui bg-surface-card shadow-xs';
          let letterClass = 'bg-surface-page border border-border-ui/50 text-text-muted group-hover:bg-brand-100 group-hover:text-brand-700 group-hover:border-transparent rounded-md';
          
          if (isAnswered) {
            if (isSelected && isCorrect) {
              stateClass = 'border-semantic-success-icon bg-semantic-success-bg/30 shadow-sm z-10';
              letterClass = 'bg-semantic-success-icon text-white border-transparent rounded-md';
            } else if (isSelected && !isCorrect) {
              stateClass = 'border-semantic-warning-border bg-semantic-warning-bg/50 shadow-sm z-10';
              letterClass = 'bg-semantic-warning-iconBg border border-semantic-warning-border text-semantic-warning-text rounded-md';
            } else {
              stateClass = 'border-border-ui/50 bg-surface-page/30 opacity-50';
              letterClass = 'bg-transparent border border-border-ui/50 text-text-muted rounded-md';
            }
          }

          return (
            <motion.button
              key={index}
              role="radio"
              aria-checked={isSelected}
              disabled={isAnswered}
              onClick={() => handleOptionClick(index)}
              whileHover={!isAnswered ? { y: -1 } : {}}
              whileTap={!isAnswered ? { scale: 0.995 } : {}}
              className={`group relative flex items-center gap-3 text-left px-3.5 py-2 sm:px-4 sm:py-2.5 rounded-lg border transition-all duration-300 ease-out outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 ${stateClass}`}
            >
              {/* Letter Indicator */}
              <div className={`w-6 h-6 flex-shrink-0 flex items-center justify-center text-xs font-bold transition-all duration-300 ${letterClass}`}>
                {isAnswered && isSelected ? (
                  isCorrect ? <Check className="w-3.5 h-3.5" strokeWidth={2.5} /> : <X className="w-3.5 h-3.5" strokeWidth={2.5} />
                ) : (
                  LETTER_MAP[index]
                )}
              </div>

              {/* Option Text */}
              <span className={`flex-1 font-inter text-[13.5px] leading-snug transition-colors duration-300 ${isAnswered && isSelected ? 'text-text-primary' : 'text-text-secondary group-hover:text-text-primary'}`}>
                {option}
              </span>
              
            </motion.button>
          );
        })}
      </div>

      {/* Feedback Section */}
      <AnimatePresence mode="wait">
        {selectedIndex !== null && (
          <motion.div
            key="feedback"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto', transition: { type: 'spring', bounce: 0, duration: 0.3 } }}
            exit={{ opacity: 0, height: 0, transition: { duration: 0.15 } }}
            className="overflow-hidden origin-top"
          >
            <div className={`mt-1 py-3 px-3.5 sm:py-3.5 sm:px-4 rounded-xl border shadow-xs ${isCorrect ? 'bg-semantic-success-bg/40 border-semantic-success-border' : 'bg-semantic-warning-bg/50 border-semantic-warning-border'}`}>
              <div className="flex items-start gap-3">
                {isCorrect ? (
                  <div className="mt-0.5 flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center bg-semantic-success-icon text-white">
                    <Check className="w-3.5 h-3.5" strokeWidth={2.5} />
                  </div>
                ) : (
                  <div className="mt-0.5 flex-shrink-0 w-7 h-7 rounded-full flex items-center justify-center bg-semantic-warning-iconBg border border-semantic-warning-border">
                    <AlertCircle className="w-3.5 h-3.5 text-semantic-warning-icon" strokeWidth={2.5} />
                  </div>
                )}
                <div className="flex-1">
                  <h4 className={`text-xs font-bold uppercase tracking-[0.15em] mb-1 ${isCorrect ? 'text-semantic-success-text' : 'text-semantic-warning-text'}`}>
                    {isCorrect ? 'Correct' : 'Not quite right'}
                  </h4>
                  <p className={`text-sm sm:text-[13.5px] leading-relaxed ${isCorrect ? '' : 'mb-3'} ${isCorrect ? 'text-semantic-success-text/80' : 'text-semantic-warning-text/80'}`}>
                    {quiz.explanation}
                  </p>
                  
                  {!isCorrect && (
                    <motion.button
                      onClick={handleTryAgain}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      className="inline-flex items-center gap-1.5 font-inter font-semibold text-semantic-warning-text text-xs px-4 py-2 rounded-lg bg-semantic-warning-bg border border-semantic-warning-border hover:bg-semantic-warning-iconBg hover:border-semantic-warning-border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
                    >
                      Give it another shot
                      <ArrowRight className="w-3.5 h-3.5 text-semantic-warning-icon" strokeWidth={2.5} />
                    </motion.button>
                  )}
                </div>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

    </motion.div>
  );
};

