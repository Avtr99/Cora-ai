import React, { useMemo } from 'react';
import { FileText, Layers, Calendar, AlertTriangle, CheckCircle2, Copy } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import remarkGfm from 'remark-gfm';
import { StatusBadge } from './StatusBadge';
import { fetchDocumentMarkdown, formatBytes, markDocumentReviewed } from '@/services/documentStoreApi';
import type { DocumentStoreRecord } from '@/services/documentStoreApi';

interface DocumentPreviewProps {
  document: DocumentStoreRecord;
  isBusy: boolean;
}

function formatDate(value?: string | null): string {
  if (!value) return '-';
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

const markdownComponents = {
  h1: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h1 className="font-poppins text-base font-semibold text-text-primary mt-4 mb-2" {...props}>{children}</h1>
  ),
  h2: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="font-poppins text-sm font-semibold text-text-primary mt-3.5 mb-2" {...props}>{children}</h2>
  ),
  h3: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="font-poppins text-sm font-semibold text-text-primary mt-3 mb-1.5" {...props}>{children}</h3>
  ),
  p: ({ children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="font-inter text-xs text-text-secondary leading-relaxed mb-2.5" {...props}>{children}</p>
  ),
  ul: ({ children, ...props }: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="list-disc pl-5 space-y-1 mb-3 font-inter text-xs text-text-secondary" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }: React.OlHTMLAttributes<HTMLOListElement>) => (
    <ol className="list-decimal pl-5 space-y-1 mb-3 font-inter text-xs text-text-secondary" {...props}>{children}</ol>
  ),
  li: ({ children, ...props }: React.LiHTMLAttributes<HTMLLIElement>) => (
    <li className="leading-relaxed" {...props}>{children}</li>
  ),
  code: ({ children, className, ...props }: React.HTMLAttributes<HTMLElement> & { className?: string }) => {
    const inline = typeof className === 'undefined';
    return inline ? (
      <code className="rounded bg-surface-subtle px-1 py-0.5 font-mono text-xs text-text-primary" {...props}>{children}</code>
    ) : (
      <pre className="rounded-lg bg-surface-subtle p-3 overflow-x-auto font-mono text-xs text-text-secondary leading-relaxed mb-3">
        <code className={className} {...props}>{children}</code>
      </pre>
    );
  },
  blockquote: ({ children, ...props }: React.HTMLAttributes<HTMLQuoteElement>) => (
    <blockquote className="border-l-2 border-border-ui pl-3 italic text-text-muted mb-3" {...props}>{children}</blockquote>
  ),
  table: ({ children, ...props }: React.TableHTMLAttributes<HTMLTableElement>) => (
    <div className="overflow-x-auto mb-3">
      <table className="w-full table-fixed border-collapse text-xs" {...props}>{children}</table>
    </div>
  ),
  thead: ({ children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <thead className="bg-surface-subtle" {...props}>{children}</thead>
  ),
  th: ({ children, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) => (
    <th className="border border-border-ui px-2 py-1.5 text-left font-poppins font-semibold text-xs text-text-primary break-words first:w-14 last:w-14" {...props}>{children}</th>
  ),
  td: ({ children, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
    <td className="border border-border-ui px-2 py-1.5 font-inter text-xs text-text-secondary break-words first:w-14 last:w-14" {...props}>{children}</td>
  ),
};

export const DocumentPreview: React.FC<DocumentPreviewProps> = ({ document, isBusy }) => {
  const queryClient = useQueryClient();
  const markdownQuery = useQuery({
    queryKey: ['document-store', 'markdown', document.id],
    queryFn: () => fetchDocumentMarkdown(document.id),
    enabled: document.status === 'indexed',
  });

  const [isMarkingReviewed, setIsMarkingReviewed] = React.useState(false);
  const [copiedError, setCopiedError] = React.useState(false);

  const handleMarkReviewed = React.useCallback(async () => {
    setIsMarkingReviewed(true);
    try {
      await markDocumentReviewed(document.id);
      queryClient.invalidateQueries({ queryKey: ['document-store', 'documents'] });
    } catch {
      // Error is surfaced via query invalidation; no extra UI needed
    } finally {
      setIsMarkingReviewed(false);
    }
  }, [document.id, queryClient]);

  const handleCopyError = React.useCallback(async () => {
    if (!document.error) return;
    try {
      await navigator.clipboard.writeText(document.error);
      setCopiedError(true);
      setTimeout(() => setCopiedError(false), 2000);
    } catch {
      // Clipboard not available
    }
  }, [document.error]);

  const isDisabled = isBusy || document.status === 'deleting' || isMarkingReviewed;
  const chunkLabel = document.chunk_count === 1 ? 'chunk' : 'chunks';
  const pageLabel = document.page_count === 1 ? 'page' : 'pages';

  const stats = useMemo(() => [
    { icon: FileText, label: formatBytes(document.size_bytes) },
    { icon: Layers, label: `${document.chunk_count.toLocaleString()} ${chunkLabel}` },
    ...(document.page_count ? [{ icon: FileText, label: `${document.page_count} ${pageLabel}` }] : []),
    { icon: Calendar, label: formatDate(document.created_at) },
  ], [document, chunkLabel, pageLabel]);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-poppins text-base font-medium text-text-primary break-all">
            {document.original_filename}
          </p>
          <p className="font-inter text-xs text-text-muted mt-0.5">
            {document.extension.replace('.', '').toUpperCase()}
          </p>
        </div>
        <StatusBadge status={document.status} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {stats.map(({ icon: Icon, label }) => (
          <div
            key={label}
            className="inline-flex items-center gap-1.5 rounded-md bg-surface-subtle px-2 py-1 text-xs font-inter text-text-secondary"
          >
            <Icon className="h-3 w-3 text-text-muted" />
            {label}
          </div>
        ))}
      </div>

      {document.status === 'needs_review' && (
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            disabled={isDisabled}
            onClick={handleMarkReviewed}
            className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-semantic-success-border px-3 font-inter text-xs font-semibold text-semantic-success-text hover:bg-semantic-success-bg disabled:opacity-50"
          >
            <CheckCircle2 className="h-3.5 w-3.5" />
            {isMarkingReviewed ? 'Marking...' : 'Mark reviewed'}
          </button>
        </div>
      )}

      {document.error && (
        <div className="mt-3 rounded-lg bg-semantic-error-bg p-2.5 font-inter text-xs text-semantic-error-text">
          <div className="flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
            <span className="flex-1 break-words whitespace-pre-wrap select-text">{document.error}</span>
            <button
              type="button"
              onClick={handleCopyError}
              className="shrink-0 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs text-semantic-error-icon hover:bg-semantic-error-bg"
              aria-label="Copy error message"
            >
              <Copy className="h-3 w-3" />
              {copiedError ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      )}

      {document.warnings.length > 0 && (
        <div className="mt-3 rounded-lg bg-semantic-warning-bg p-2.5">
          <p className="font-poppins text-xs font-semibold text-semantic-warning-text">Review suggested</p>
          <ul className="mt-1 list-disc pl-4 font-inter text-xs text-semantic-warning-text space-y-0.5">
            {document.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </div>
      )}

      <div className="mt-4">
        <p className="mb-2 font-poppins text-sm font-semibold text-text-primary">What Cora can read</p>
        <div className="rounded-lg border border-border-ui bg-surface-subtle p-3">
          {(() => {
            if (document.status !== 'indexed') {
              return (
                <p className="font-inter text-xs text-text-secondary">
                  Readable text will appear when Cora finishes preparing the document.
                </p>
              );
            }
            if (markdownQuery.isLoading) {
              return (
                <div className="flex items-center gap-2 font-inter text-xs text-text-muted">
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-500" />
                  Loading preview...
                </div>
              );
            }
            if (markdownQuery.isError) {
              return <p className="font-inter text-xs text-semantic-error-text">Could not load readable text.</p>;
            }
            return (
              <div className="document-preview-markdown font-inter text-xs leading-5 text-text-secondary">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  rehypePlugins={[rehypeSanitize]}
                  components={markdownComponents}
                >
                  {markdownQuery.data}
                </ReactMarkdown>
              </div>
            );
          })()}
        </div>
      </div>
    </div>
  );
};
