import React from 'react';
import { FileText, RefreshCw, Trash2 } from 'lucide-react';
import { StatusBadge } from './StatusBadge';
import { formatBytes } from '@/services/documentStoreApi';
import type { DocumentStoreRecord } from '@/services/documentStoreApi';

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
}

export const DocumentRow: React.FC<DocumentRowProps> = ({
  document,
  onSelect,
  onReindex,
  onDelete,
  isReindexing,
  isDeleting,
}) => {
  const busy = isReindexing || isDeleting || document.status === 'deleting';

  return (
    <div className="group relative border-b border-border-ui last:border-b-0 bg-surface-card transition-colors hover:bg-surface-subtle/50">
      <button
        type="button"
        onClick={() => onSelect(document.id)}
        aria-label={`Open preview of ${document.original_filename}`}
        className="absolute inset-0 z-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500"
      />
      <div className="relative z-10 grid grid-cols-[1fr_90px_80px_64px] sm:grid-cols-[1fr_100px_90px_64px] items-center gap-3 px-4 py-3 pointer-events-none">
        <div className="flex items-center gap-3 min-w-0 pointer-events-none">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-subtle text-text-muted">
            <FileText className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <p className="font-inter text-sm font-medium text-text-primary line-clamp-2 break-all">
              {document.original_filename}
            </p>
            <p className="mt-0.5 font-inter text-xs text-text-muted">
              {document.extension.replace('.', '').toUpperCase()} · {formatBytes(document.size_bytes)}
            </p>
          </div>
        </div>
        <div className="hidden sm:block text-right font-inter text-xs text-text-muted pointer-events-none">
          {formatDate(document.created_at)}
        </div>
        <div className="text-right pointer-events-none">
          <StatusBadge status={document.status} />
        </div>
        <div className="text-right opacity-100 md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100 transition-opacity pointer-events-auto">
          <div className="flex items-center justify-end gap-1">
            <button
              type="button"
              onClick={() => onReindex(document.id)}
              disabled={busy}
              className="h-7 w-7 flex items-center justify-center rounded-lg text-text-muted hover:text-brand-700 hover:bg-brand-50 disabled:opacity-50"
              aria-label="Refresh"
              title="Refresh"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isReindexing ? 'animate-spin' : ''}`} />
            </button>
            <button
              type="button"
              onClick={() => onDelete(document)}
              disabled={busy}
              className="h-7 w-7 flex items-center justify-center rounded-lg text-text-muted hover:text-semantic-error-icon hover:bg-semantic-error-bg disabled:opacity-50"
              aria-label="Delete"
              title="Delete"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
