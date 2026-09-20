import React from 'react';
import { FileText, RefreshCw, Trash2 } from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import { formatBytes } from '@/services/documentStoreApi';
import type { DocumentStoreRecord, DocumentStatus } from '@/services/documentStoreApi';

function formatDate(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

interface DocumentRowProps {
  document: DocumentStoreRecord;
  onSelect: (id: string) => void;
  onReindex: (id: string) => void;
  onDelete: (document: DocumentStoreRecord) => void;
  isReindexing: boolean;
  isDeleting: boolean;
  /** True when a reindex job has been queued but the worker hasn't picked it
   * up yet. The backend deliberately keeps the doc at its current status
   * (e.g. 'indexed') until the handler transitions it, so the UI must show
   * an optimistic 'queued' badge to give the user immediate feedback. */
  isPendingReindex?: boolean;
}

export const DocumentRow: React.FC<DocumentRowProps> = ({
  document,
  onSelect,
  onReindex,
  onDelete,
  isReindexing,
  isDeleting,
  isPendingReindex = false,
}) => {
  // Reindex is blocked while a job is in flight for this document (queued,
  // reading, converting, indexing, deleting). Delete is only blocked while a
  // delete is already running — the user should be able to delete a doc that
  // is stuck in processing to cancel it.
  const reindexDisabled =
    isReindexing ||
    ['queued', 'reading', 'converting', 'indexing', 'deleting'].includes(document.status);
  const deleteDisabled = isDeleting || document.status === 'deleting';

  // Optimistic status: when a reindex is pending but the backend hasn't
  // transitioned the doc yet, show 'queued' so the user sees feedback.
  const effectiveStatus: DocumentStatus =
    isPendingReindex && document.status === 'indexed' ? 'queued' : document.status;

  return (
    <div className="group relative border-b border-border-ui last:border-b-0 bg-surface-card transition-colors hover:bg-surface-subtle/50">
      <button
        type="button"
        onClick={() => onSelect(document.id)}
        aria-label={`Open preview of ${document.original_filename}`}
        className="absolute inset-0 z-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-focus"
      />
      <div className="relative z-10 grid grid-cols-[1fr_90px_80px_64px] sm:grid-cols-[1fr_100px_90px_64px] 3xl:grid-cols-[1fr_140px_130px_96px] 4xl:grid-cols-[1fr_160px_150px_112px] items-center gap-3 3xl:gap-4 px-4 3xl:px-6 4xl:px-8 py-3 3xl:py-4 4xl:py-5 pointer-events-none">
        <div className="flex items-center gap-3 3xl:gap-4 min-w-0 pointer-events-none">
          <div className="flex h-8 w-8 3xl:h-10 3xl:w-10 4xl:h-12 4xl:w-12 shrink-0 items-center justify-center rounded-lg 3xl:rounded-xl bg-surface-subtle text-text-muted">
            <FileText className="h-4 w-4 3xl:h-5 3xl:w-5 4xl:h-6 4xl:w-6" />
          </div>
          <div className="min-w-0">
            <p className="font-inter text-body-sm 3xl:text-base 4xl:text-lg font-medium text-text-primary line-clamp-2 break-all">
              {document.original_filename}
            </p>
            <p className="mt-0.5 font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-muted">
              {document.extension.replace('.', '').toUpperCase()} · {formatBytes(document.size_bytes)}
            </p>
          </div>
        </div>
        <div className="hidden sm:block text-right font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-muted pointer-events-none">
          {formatDate(document.created_at)}
        </div>
        <div className="text-right pointer-events-none">
          <StatusBadge status={effectiveStatus} />
        </div>
        <div className="text-right opacity-100 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity pointer-events-auto">
          <div className="flex items-center justify-end gap-1 3xl:gap-2">
            <button
              type="button"
              onClick={() => onReindex(document.id)}
              disabled={reindexDisabled}
              className="h-7 w-7 3xl:h-9 3xl:w-9 4xl:h-10 4xl:w-10 flex items-center justify-center rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-subtle disabled:opacity-50"
              aria-label="Refresh"
              title="Refresh"
            >
              <RefreshCw className={`h-3.5 w-3.5 3xl:h-4 3xl:w-4 4xl:h-5 4xl:w-5 ${isReindexing ? 'animate-spin' : ''}`} />
            </button>
            <button
              type="button"
              onClick={() => onDelete(document)}
              disabled={deleteDisabled}
              className="h-7 w-7 3xl:h-9 3xl:w-9 4xl:h-10 4xl:w-10 flex items-center justify-center rounded-lg text-text-muted hover:text-semantic-error-icon hover:bg-semantic-error-bg disabled:opacity-50"
              aria-label="Delete"
              title="Delete"
            >
              <Trash2 className="h-3.5 w-3.5 3xl:h-4 3xl:w-4 4xl:h-5 4xl:w-5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
