import type { ReactElement } from 'react';
import {
  ChevronDown,
  CircleAlert,
  CircleHelp,
  Database,
  GitBranch,
  Globe,
  PenLine,
  Repeat,
  ShieldCheck,
  Workflow,
} from 'lucide-react';
import type { AgentReasoningStep } from '@/types/reasoning';
import type { Message } from '@/store/chatStore.types';

const isNonEmptyString = (m: unknown): m is string => typeof m === 'string' && m.trim().length > 0;

const STEP_ICONS: Record<string, typeof CircleHelp> = {
  understand: CircleHelp,
  route: GitBranch,
  search_kb: Database,
  search_web: Globe,
  compose: PenLine,
  verify: ShieldCheck,
  fallback: Repeat,
  step: Workflow,
};

const STEP_STATUS_LABELS: Record<NonNullable<AgentReasoningStep['status']>, string> = {
  running: 'Not finished',
  complete: 'Complete',
  error: 'Failed',
  cancelled: 'Cancelled',
  skipped: 'Skipped',
  cached: 'Cached',
  fallback: 'Fallback',
};

const stepIcon = (step: AgentReasoningStep, isFailedStep: boolean) => {
  if (isFailedStep) return CircleAlert;
  return STEP_ICONS[step.kind ?? 'step'] ?? Workflow;
};

interface AgentReasoningSectionProps {
  steps: AgentReasoningStep[];
  status?: Message['status'];
}

/**
 * Collapsible "How this answer was formed" trace.
 *
 * Renders the backend's formatted reasoning_steps as an icon timeline:
 * one imperative title per step (details.title), one prod-style message line
 * (details.summary / derived), and clean source names under retrieval steps.
 */
export function AgentReasoningSection({ steps, status }: AgentReasoningSectionProps): ReactElement | null {
  const interrupted = status === 'error' || status === 'cancelled';
  // Skipped steps are dropped upstream in buildAgentReasoning.
  const visibleSteps = steps;
  if (visibleSteps.length === 0) return null;

  return (
    <details className="group mb-4 md:mb-5 3xl:mb-6 4xl:mb-8 font-inter text-xs 3xl:text-base 4xl:text-xl">
      <summary className="inline-flex min-h-6 cursor-pointer items-center gap-1.5 py-0.5 text-text-muted hover:text-text-secondary list-none select-none rounded focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2">
        <span>{interrupted ? 'Request workflow' : 'How this answer was formed'}</span>
        <ChevronDown
          aria-hidden="true"
          className="h-3 w-3 3xl:h-3.5 3xl:w-3.5 4xl:h-4 4xl:w-4 shrink-0 -rotate-90 transition-transform duration-150 group-open:rotate-0 motion-reduce:transition-none"
        />
      </summary>
      <div className="mt-2.5 md:mt-3 3xl:mt-3.5 4xl:mt-4 flex flex-col">
        {visibleSteps.map((step, idx) => {
          let stepStatus = step.status ?? 'complete';
          const isLast = idx === visibleSteps.length - 1;
          if (!step.status && isLast && (status === 'error' || status === 'cancelled')) {
            stepStatus = status;
          }
          const isFailedStep = stepStatus === 'error' || stepStatus === 'cancelled';
          const Icon = stepIcon(step, isFailedStep);
          const msgs = (step.messages ?? []).filter(isNonEmptyString);
          const sources = (step.sources ?? []).filter(isNonEmptyString);

          return (
            <div key={step.nodeId ?? idx} data-reasoning-step className="relative pb-3 3xl:pb-4 4xl:pb-5 pl-7 3xl:pl-8 4xl:pl-10 last:pb-0">
              {!isLast && (
                <span aria-hidden="true" className="absolute bottom-0 left-2 3xl:left-2.5 4xl:left-3 top-5 3xl:top-6 4xl:top-7 w-px bg-border-ui" />
              )}
              <span
                aria-hidden="true"
                className={`absolute left-0 top-[1px] flex h-[17px] w-[17px] 3xl:h-[21px] 3xl:w-[21px] 4xl:h-[25px] 4xl:w-[25px] items-center justify-center ${
                  isFailedStep ? 'text-semantic-error-icon' : 'text-text-muted'
                }`}
              >
                <Icon className="h-[15px] w-[15px] 3xl:h-[18px] 3xl:w-[18px] 4xl:h-[22px] 4xl:w-[22px]" strokeWidth={2} />
              </span>
              <div className="flex items-center gap-1.5 leading-normal">
                <span className="font-medium text-text-primary">{step.agentName || 'Processing'}</span>
                {stepStatus !== 'complete' && (
                  <span
                    className={`rounded-full border px-1.5 py-px text-[11px] 3xl:text-sm font-medium ${
                      isFailedStep
                        ? 'border-semantic-error-border text-semantic-error-text'
                        : 'border-border-ui text-text-muted'
                    }`}
                  >
                    {STEP_STATUS_LABELS[stepStatus]}
                  </span>
                )}
              </div>
              {msgs.map((msg, index) => (
                <p key={index} className="mt-0.5 leading-relaxed text-text-secondary wrap-break-word">
                  {msg.trim()}
                </p>
              ))}
              {sources.map((name, index) => (
                <p
                  key={`src-${index}`}
                  className={`mt-0.5 leading-relaxed wrap-break-word ${
                    name.startsWith('…') ? 'text-text-disabled' : 'text-text-muted'
                  }`}
                >
                  {name}
                </p>
              ))}
            </div>
          );
        })}
      </div>
    </details>
  );
}
