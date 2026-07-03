import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { checkHealth } from '@/services/coraApi';
import { getConfigStatus } from '@/services/llmSettingsApi';
import { fetchDocuments } from '@/services/documentStoreApi';

/**
 * Why the chat input is blocked.
 * - backend_down:           the backend is unreachable.
 * - llm_not_configured:     backend is up but no LLM provider is set up.
 * - no_answer_source:       backend + LLM are ready, but the KB is empty and
 *                           web search is disabled.
 */
export type NotReadyReason = 'backend_down' | 'llm_not_configured' | 'no_answer_source' | null;

export interface ChatReadiness {
  /** Total indexed points in the KB collection (null if unavailable). */
  kbDocCount: number | null;
  /** True when the KB collection has zero indexed points or is unreachable. */
  kbEmpty: boolean;
  /** True when the backend reports the knowledge base has indexed documents. */
  kbReady: boolean;
  /** True when web search is configured and enabled. */
  webEnabled: boolean;
  /** True when the backend reports a web search provider other than 'none' is configured. */
  searchReady: boolean;
  /** True when at least one document is still being processed. */
  ingestionInProgress: boolean;
  /** True when the LLM provider is configured. */
  llmConfigured: boolean;
  /** True when the backend is reachable. */
  backendUp: boolean;
  /**
   * True when the chat can produce grounded answers — backend is reachable,
   * LLM is configured, and (KB has documents OR web search is enabled). When
   * false, the input is greyed out and a state-specific banner is shown.
   */
  chatReady: boolean;
  /** The specific reason the chat is not ready (null when ready). */
  notReadyReason: NotReadyReason;
  /** Placeholder text for the greyed-out input. */
  disabledPlaceholder: string;
  /** True while the status is still loading (first fetch). */
  isLoading: boolean;
}

const INGESTING_STATUSES = ['queued', 'reading', 'converting', 'indexing'];

const PLACEHOLDERS: Record<Exclude<NotReadyReason, null>, string> = {
  backend_down: 'Start the backend to use chat',
  llm_not_configured: 'Configure an AI model to use chat',
  no_answer_source: 'Add documents or enable web search to use chat',
};

/**
 * Determines whether the chat input should be active or greyed out.
 *
 * Uses an explicit health check to decide if the backend is reachable, then
 * the backend's `chat_ready` field to determine whether the chat can answer.
 */
export function useChatReadiness(): ChatReadiness {
  const healthQuery = useQuery({
    queryKey: ['chat-readiness', 'health'],
    queryFn: () => checkHealth(),
    retry: 1,
    staleTime: 0,
    refetchInterval: 5000,
    refetchOnWindowFocus: true,
  });

  const configQuery = useQuery({
    queryKey: ['chat-readiness', 'config-status'],
    queryFn: () => getConfigStatus(),
    retry: 1,
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    // Only fetch config when the backend is confirmed reachable.
    enabled: healthQuery.data?.healthy === true,
  });

  const documentsQuery = useQuery({
    queryKey: ['chat-readiness', 'documents'],
    queryFn: () => fetchDocuments(),
    refetchInterval: (query) => {
      const docs = query.state.data ?? [];
      const hasActiveJobs = docs.some((doc) => INGESTING_STATUSES.includes(doc.status));
      return hasActiveJobs ? 5000 : false;
    },
    staleTime: 30_000,
    enabled: healthQuery.data?.healthy === true,
  });

  return useMemo<ChatReadiness>(() => {
    const config = configQuery.data;
    const docs = documentsQuery.data ?? [];

    // Backend is considered down when the explicit health check fails, even if
    // TanStack Query still holds stale successful data from an earlier run.
    const backendUp = !healthQuery.isError && healthQuery.data?.healthy === true;
    const backendDown = !backendUp;

    const pointsCount = config?.qdrant?.points_count;
    const kbDocCount = typeof pointsCount === 'number' ? pointsCount : null;
    const kbEmpty = kbDocCount === null || kbDocCount === 0;

    // Trust the backend's new granular readiness flags when present.
    const kbReady = config?.kb_ready ?? !kbEmpty;
    const searchReady = config?.search_ready ?? false;
    const llmConfigured = config?.llm?.is_configured ?? false;
    const webEnabled = searchReady;

    const ingestionInProgress = docs.some((doc) => INGESTING_STATUSES.includes(doc.status));

    // Use the backend's chat_ready as primary signal; fall back to local
    // computation if the field is missing (older backend version).
    const backendChatReady = config?.chat_ready;
    const chatReady = backendChatReady !== undefined
      ? backendChatReady
      : backendUp && llmConfigured && (kbReady || webEnabled);

    // Determine the not-ready reason with priority:
    // backend down > LLM missing > no answer source.
    let notReadyReason: NotReadyReason = null;
    if (backendDown) {
      notReadyReason = 'backend_down';
    } else if (!llmConfigured) {
      notReadyReason = 'llm_not_configured';
    } else if (!chatReady) {
      notReadyReason = 'no_answer_source';
    }

    return {
      kbDocCount,
      kbEmpty,
      kbReady,
      webEnabled,
      searchReady,
      ingestionInProgress,
      llmConfigured,
      backendUp,
      chatReady,
      notReadyReason,
      disabledPlaceholder: notReadyReason ? PLACEHOLDERS[notReadyReason] : '',
      isLoading: healthQuery.isLoading || configQuery.isLoading,
    };
  }, [healthQuery.data, healthQuery.isLoading, healthQuery.isError, configQuery.data, configQuery.isLoading, documentsQuery.data]);
}
