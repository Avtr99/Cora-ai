import { useNavigate } from 'react-router-dom';
import { Info } from 'lucide-react';
import { useChatReadiness } from '@/hooks/useChatReadiness';
import { useSettingsDialogStore } from '@/store/settingsDialogStore';

/**
 * Subtle inline notice shown when the chat is not ready.
 *
 * Keeps the disabled state quiet: a single line of muted text with text links
 * instead of a prominent warning card. The composer itself is greyed out to
 * communicate the disabled state.
 */
export const ChatReadinessBanner: React.FC = () => {
  const {
    chatReady,
    isLoading,
    backendUp,
    llmConfigured,
    kbReady,
    searchReady,
    webEnabled,
  } = useChatReadiness();
  const navigate = useNavigate();
  const openSettings = useSettingsDialogStore((s) => s.openSettings);

  if (isLoading || chatReady) return null;

  const openDocuments = () => navigate('/documents/');
  const openSearchSettings = () => openSettings('search');
  const openLlmSettings = () => openSettings('llm');

  if (!backendUp) {
    return (
      <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-muted">
        <Info className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
        <span>Backend is offline — start the server to use chat.</span>
        {webEnabled && (
          <span className="text-text-muted">(Web search is configured and will be ready once the backend is running.)</span>
        )}
      </div>
    );
  }

  if (!llmConfigured) {
    return (
      <div className="mb-2 flex items-center gap-2 text-xs text-text-muted">
        <Info className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
        <span>AI model not configured.</span>
        <button
          type="button"
          onClick={openLlmSettings}
          className="font-medium text-brand-700 hover:text-brand-700 hover:underline"
        >
          Configure AI model
        </button>
      </div>
    );
  }

  // No answer source (KB empty and web search disabled)
  const showAddDocs = !kbReady;
  const showEnableWeb = !searchReady;

  return (
    <div className="mb-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-text-muted">
      <Info className="h-3.5 w-3.5 shrink-0" strokeWidth={1.75} />
      <span>Chat needs documents or web search enabled to answer.</span>
      {showAddDocs && (
        <button
          type="button"
          onClick={openDocuments}
          className="font-medium text-brand-700 hover:text-brand-700 hover:underline"
        >
          Add documents
        </button>
      )}
      {showAddDocs && showEnableWeb && <span className="text-text-muted">or</span>}
      {showEnableWeb && (
        <button
          type="button"
          onClick={openSearchSettings}
          className="font-medium text-brand-700 hover:text-brand-700 hover:underline"
        >
          enable web search
        </button>
      )}
    </div>
  );
};
