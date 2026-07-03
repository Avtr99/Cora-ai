import React from 'react';
import { BRAND } from '@/lib/colors';
import { MessageSquare, Pencil, Route, Search, FileText, CheckCircle } from 'lucide-react';
import type { AgentReasoningStep } from '@/types/reasoning';

const isNonEmptyString = (m: unknown): m is string => typeof m === 'string' && m.trim().length > 0;

/** Normalize step.messages into an array of non-empty strings. */
const normalizeStepMessages = (messages: unknown[] | string | undefined): string[] => {
  if (Array.isArray(messages)) return messages.filter(isNonEmptyString);
  if (typeof messages === 'string') return [messages];
  return [];
};

const friendlyLabel = (name?: string) => name || 'Processing';

const friendlyMessage = (m: string) => m.trim();

const renderStepIcon = (name?: string) => {
  const n = (name || '').toLowerCase();
  if (n.includes('intent') || n.includes('query')) return <MessageSquare className="h-3.5 w-3.5 text-brand-500" />;
  if (n.includes('clarify') || n.includes('rewrit')) return <Pencil className="h-3.5 w-3.5 text-brand-500" />;
  if (n.includes('route')) return <Route className="h-3.5 w-3.5 text-brand-500" />;
  if (n.includes('retriev') || n.includes('search')) return <Search className="h-3.5 w-3.5 text-brand-500" />;
  if (n.includes('summarize') || n.includes('findings')) return <FileText className="h-3.5 w-3.5 text-brand-500" />;
  if (n.includes('validat') || n.includes('quality') || n.includes('check')) return <CheckCircle className="h-3.5 w-3.5 text-brand-500" />;
  if (n.includes('answer') || n.includes('generat') || n.includes('draft')) return <Pencil className="h-3.5 w-3.5 text-brand-500" />;
  return <FileText className="h-3.5 w-3.5 text-brand-500" />;
};

interface AgentReasoningSectionProps {
  steps: AgentReasoningStep[];
}

export const AgentReasoningSection: React.FC<AgentReasoningSectionProps> = ({ steps }) => {
  const visibleSteps = steps.filter((step) => {
    const stepName = (step.agentName || '').toLowerCase();
    const isValidationStep = stepName.includes('validat') || stepName.includes('quality') || stepName.includes('check');
    if (!isValidationStep) return true;
    const messages = normalizeStepMessages(step.messages);
    return !messages.some((msg) => /\bskipp?ed\b/i.test(msg));
  });

  if (visibleSteps.length === 0) return null;

  return (
    <details className="-mt-1 mb-3 text-xs cursor-pointer group">
      <summary className="font-inter font-normal text-xs leading-[1.4] text-text-secondary outline-none flex items-center gap-1.5 hover:text-brand-500 transition-colors list-none select-none">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" className="flex-shrink-0">
          <path d="M6.5 2L3 6.5L6.5 6.5L6.5 10L10 5.5L6.5 5.5L6.5 2Z" fill={BRAND.primary500} stroke={BRAND.primary500} strokeWidth="0.5" />
        </svg>
        <span>How this answer was formed</span>
        <svg className="transition-transform duration-200 group-open:rotate-180" width="10" height="6" viewBox="0 0 10 6" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M1 1L5 5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </summary>
      <div className="mt-2.5 space-y-1.5 reasoning-content">
        {visibleSteps.map((step, idx) => {
          const msgs = normalizeStepMessages(step.messages);
          const primaryMsg = msgs[0] || '';
          const detailMsgs = msgs.slice(1);
          const stepName = (step.agentName || '').toLowerCase();
          const isRetrievalStep = stepName.includes('retriev') || stepName.includes('search') || stepName.includes('kb');

          return (
            <div key={idx} className="rounded-md border border-border-ui bg-surface-card p-2.5">
              <div className="flex items-center gap-1.5 mb-1.5">
                <span className="flex items-center justify-center w-5 h-5 rounded bg-brand-100">
                  {renderStepIcon(step.agentName)}
                </span>
                <span className="font-poppins font-medium text-xs text-text-primary">
                  {friendlyLabel(step.agentName)}
                </span>
              </div>
              {primaryMsg && (
                <p className="font-inter font-normal text-sm leading-[1.45] text-text-secondary mb-1">
                  {friendlyMessage(primaryMsg)}
                </p>
              )}
              {detailMsgs.length > 0 && (
                <div className="pl-1">
                  {isRetrievalStep ? (
                    <ul className="space-y-1">
                      {detailMsgs.map((msg: string, i: number) => (
                        <li key={i} className="flex items-start gap-2">
                          <span className="w-1 h-1 rounded-full bg-brand-500 mt-1.5 flex-shrink-0"></span>
                          <span className="font-inter font-normal text-xs leading-[1.45] text-text-secondary">
                            {friendlyMessage(msg)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <div className="space-y-0.5">
                      {detailMsgs.map((msg: string, i: number) => (
                        <p key={i} className="font-inter font-normal text-xs leading-[1.45] text-text-secondary">
                          {friendlyMessage(msg)}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </details>
  );
};
