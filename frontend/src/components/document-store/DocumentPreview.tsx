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
    <h1 className="font-poppins text-heading-3 3xl:text-lg 4xl:text-xl font-semibold text-text-primary mt-4 3xl:mt-5 mb-2" {...props}>{children}</h1>
  ),
  h2: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h2 className="font-inter text-heading-2 3xl:text-xl 4xl:text-2xl font-semibold text-text-primary mt-3.5 3xl:mt-5 mb-2" {...props}>{children}</h2>
  ),
  h3: ({ children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
    <h3 className="font-inter text-heading-3 3xl:text-lg 4xl:text-xl font-semibold text-text-primary mt-3 3xl:mt-4 mb-1.5" {...props}>{children}</h3>
  ),
  p: ({ children, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
    <p className="font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-secondary leading-relaxed mb-2.5 3xl:mb-3" {...props}>{children}</p>
  ),
  ul: ({ children, ...props }: React.HTMLAttributes<HTMLUListElement>) => (
    <ul className="list-disc pl-5 space-y-1 mb-3 font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-secondary" {...props}>{children}</ul>
  ),
  ol: ({ children, ...props }: React.OlHTMLAttributes<HTMLOListElement>) => (
    <ol className="list-decimal pl-5 space-y-1 mb-3 font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-secondary" {...props}>{children}</ol>
  ),
  li: ({ children, ...props }: React.LiHTMLAttributes<HTMLLIElement>) => (
    <li className="leading-relaxed" {...props}>{children}</li>
  ),
  code: ({ children, className, ...props }: React.HTMLAttributes<HTMLElement> & { className?: string }) => {
    const inline = typeof className === 'undefined';
    return inline ? (
      <code className="rounded bg-surface-subtle px-1 py-0.5 font-mono text-caption 3xl:text-[13px] 4xl:text-sm text-text-primary" {...props}>{children}</code>
    ) : (
      <pre className="rounded-lg bg-surface-subtle p-3 3xl:p-4 overflow-x-auto font-mono text-caption 3xl:text-[13px] 4xl:text-sm text-text-secondary leading-relaxed mb-3">
        <code className={className} {...props}>{children}</code>
      </pre>
    );
  },
  blockquote: ({ children, ...props }: React.HTMLAttributes<HTMLQuoteElement>) => (
    <blockquote className="border-l-2 3xl:border-l-4 border-border-ui pl-3 3xl:pl-4 italic text-text-muted mb-3 font-inter text-body-sm 3xl:text-base 4xl:text-lg" {...props}>{children}</blockquote>
  ),
  table: ({ children, ...props }: React.TableHTMLAttributes<HTMLTableElement>) => (
    <div className="overflow-x-auto mb-3">
      <table className="w-full table-fixed border-collapse text-caption 3xl:text-[13px] 4xl:text-sm" {...props}>{children}</table>
    </div>
  ),
  thead: ({ children, ...props }: React.HTMLAttributes<HTMLTableSectionElement>) => (
    <thead className="bg-surface-subtle" {...props}>{children}</thead>
  ),
  th: ({ children, ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) => (
    <th className="border border-border-ui px-2 3xl:px-3 py-1.5 3xl:py-2 text-left font-inter font-semibold text-caption 3xl:text-[13px] 4xl:text-sm text-text-primary break-words first:w-14 last:w-14" {...props}>{children}</th>
  ),
  td: ({ children, ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) => (
    <td className="border border-border-ui px-2 3xl:px-3 py-1.5 3xl:py-2 font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-secondary break-words first:w-14 last:w-14" {...props}>{children}</td>
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
    <div className="space-y-4 3xl:space-y-6 4xl:space-y-8">
      <div className="flex items-start justify-between gap-3 3xl:gap-4">
        <div className="min-w-0">
          <p className="font-inter text-heading-3 3xl:text-lg 4xl:text-xl font-medium text-text-primary break-all">
            {document.original_filename}
          </p>
          <p className="font-inter text-caption 3xl:text-sm 4xl:text-base text-text-muted mt-0.5">
            {document.extension.replace('.', '').toUpperCase()}
          </p>
        </div>
        <StatusBadge status={document.status} />
      </div>

      <div className="mt-3 3xl:mt-4 flex flex-wrap items-center gap-2 3xl:gap-3">
        {stats.map(({ icon: Icon, label }) => (
          <div
            key={label}
            className="inline-flex items-center gap-1.5 3xl:gap-2 rounded-md bg-surface-subtle px-2 3xl:px-3 py-1 3xl:py-1.5 text-caption 3xl:text-[13px] 4xl:text-sm font-inter text-text-secondary"
          >
            <Icon className="h-3 w-3 3xl:h-4 3xl:w-4 text-text-muted" />
            {label}
          </div>
        ))}
      </div>

      {document.status === 'needs_review' && (
        <div className="mt-3 3xl:mt-4 flex gap-2">
          <button
            type="button"
            disabled={isDisabled}
            onClick={handleMarkReviewed}
            className="inline-flex h-8 3xl:h-10 4xl:h-11 items-center gap-1.5 3xl:gap-2 rounded-lg 3xl:rounded-xl border border-semantic-success-border bg-surface-card px-3 3xl:px-4 font-inter text-xs 3xl:text-[13px] 4xl:text-sm font-medium text-semantic-success-text transition-all hover:bg-semantic-success-bg focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <CheckCircle2 className="h-3.5 w-3.5 3xl:h-4 3xl:w-4" />
            {isMarkingReviewed ? 'Marking...' : 'Mark reviewed'}
          </button>
        </div>
      )}

      {document.error && (
        <div className="mt-3 3xl:mt-4 rounded-lg 3xl:rounded-xl bg-semantic-error-bg p-2.5 3xl:p-4 font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-semantic-error-text">
          <div className="flex items-start gap-2 3xl:gap-3">
            <AlertTriangle className="h-4 w-4 3xl:h-5 3xl:w-5 shrink-0 mt-0.5" />
            <span className="flex-1 break-words whitespace-pre-wrap select-text">{document.error}</span>
            <button
              type="button"
              onClick={handleCopyError}
              className="shrink-0 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-caption 3xl:text-[13px] text-semantic-error-icon hover:bg-semantic-error-bg"
              aria-label="Copy error message"
            >
              <Copy className="h-3 w-3 3xl:h-4 3xl:w-4" />
              {copiedError ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>
      )}

      {document.warnings.length > 0 && (
        <div className="mt-3 3xl:mt-4 rounded-lg 3xl:rounded-xl bg-semantic-warning-bg p-2.5 3xl:p-4">
          <p className="font-inter text-caption 3xl:text-[13px] 4xl:text-sm font-semibold text-semantic-warning-text">Review suggested</p>
          <ul className="mt-1 3xl:mt-2 list-disc pl-4 font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-semantic-warning-text space-y-0.5 3xl:space-y-1">
            {document.warnings.map((warning) => <li key={warning}>{warning}</li>)}
          </ul>
        </div>
      )}

      <div className="mt-4 3xl:mt-6">
        <p className="mb-2 3xl:mb-3 font-inter text-heading-3 3xl:text-lg 4xl:text-xl font-semibold text-text-primary">What Cora can read</p>
        <div className="rounded-lg 3xl:rounded-xl border border-border-ui bg-surface-subtle p-3 3xl:p-5 4xl:p-6">
          {(() => {
            if (document.status !== 'indexed') {
              return (
                <p className="font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-secondary">
                  Readable text will appear when Cora finishes preparing the document.
                </p>
              );
            }
            if (markdownQuery.isLoading) {
              return (
                <div className="flex items-center gap-2 3xl:gap-3 font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-muted">
                  <div className="h-3.5 w-3.5 3xl:h-5 3xl:w-5 animate-spin rounded-full border-2 border-brand-200 border-t-brand-500" />
                  Loading preview...
                </div>
              );
            }
            if (markdownQuery.isError) {
              return <p className="font-inter text-body-sm 3xl:text-base 4xl:text-lg text-semantic-error-text">Could not load readable text.</p>;
            }
            return (
              <div className="document-preview-markdown font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-secondary">
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
