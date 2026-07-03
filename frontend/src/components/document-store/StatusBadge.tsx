import React from 'react';
import { CheckCircle2, Loader2, AlertTriangle } from 'lucide-react';
import type { DocumentStatus } from '@/services/documentStoreApi';

const STATUS_LABELS: Record<DocumentStatus, string> = {
  queued: 'Waiting',
  reading: 'Reading',
  converting: 'Preparing',
  indexing: 'Indexing',
  indexed: 'Ready',
  needs_review: 'Review',
  failed: 'Failed',
  deleting: 'Deleting',
  deleted: 'Deleted',
};

const STATUS_TOOLTIPS: Record<DocumentStatus, string> = {
  queued: 'Document is waiting to be processed.',
  reading: 'Reading the file content from disk.',
  converting: 'Converting the document to Markdown. This may take a while for large PDFs.',
  indexing: 'Splitting text into chunks and generating embeddings.',
  indexed: 'Document is ready to query.',
  needs_review: 'Conversion completed with warnings. Review the content before relying on answers.',
  failed: 'Processing failed. Check the error message for details.',
  deleting: 'Removing the document and its chunks from the knowledge base.',
  deleted: 'Document has been deleted.',
};

const STATUS_STYLES: Record<DocumentStatus, string> = {
  indexed: 'bg-semantic-success-bg text-semantic-success-text border-semantic-success-border',
  queued: 'bg-brand-50 text-brand-700 border-brand-100',
  reading: 'bg-brand-50 text-brand-700 border-brand-100',
  converting: 'bg-brand-50 text-brand-700 border-brand-100',
  indexing: 'bg-brand-50 text-brand-700 border-brand-100',
  deleting: 'bg-brand-50 text-brand-700 border-brand-100',
  needs_review: 'bg-semantic-warning-bg text-semantic-warning-text border-semantic-warning-border',
  failed: 'bg-semantic-error-bg text-semantic-error-text border-semantic-error-border',
  deleted: 'bg-surface-subtle text-text-muted border-surface-subtle',
};

interface StatusBadgeProps {
  status: DocumentStatus;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const processing = ['queued', 'reading', 'converting', 'indexing', 'deleting'].includes(status);
  return (
    <span
      title={STATUS_TOOLTIPS[status] ?? status}
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 border text-xs font-medium font-inter ${STATUS_STYLES[status]}`}
    >
      {status === 'indexed' && <CheckCircle2 className="h-3 w-3" />}
      {status === 'failed' && <AlertTriangle className="h-3 w-3" />}
      {processing && <Loader2 className="h-3 w-3 animate-spin" />}
      {STATUS_LABELS[status] ?? status}
    </span>
  );
};
