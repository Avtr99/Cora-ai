import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { FileText, X, RefreshCw, Trash2, AlertCircle, AlertTriangle, Settings as SettingsIcon } from 'lucide-react';
import ErrorBoundary from '@/components/ErrorBoundary';
import { IconWrapper } from '@/components/icons/IconWrapper';
import ChevronLeftIcon from '@/assets/icons/chevron-left.svg?react';
import { DocumentRow } from '@/components/document-store/DocumentRow';
import { DocumentPreview } from '@/components/document-store/DocumentPreview';
import { UploadPanel } from '@/components/document-store/UploadPanel';
import { DocumentFilters } from '@/components/document-store/DocumentFilters';
import { ScrollToTop } from '@/components/ui/ScrollToTop';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  clearAllDocuments,
  deleteDocument,
  fetchDocuments,
  reindexAllDocuments,
  reindexDocument,
  type DocumentStoreRecord,
} from '@/services/documentStoreApi';
import { getConfigStatus } from '@/services/llmSettingsApi';

const statusOptions = [
  { value: 'indexed', label: 'Ready' },
  { value: 'queued', label: 'Waiting' },
  { value: 'reading', label: 'Reading' },
  { value: 'converting', label: 'Preparing' },
  { value: 'indexing', label: 'Indexing' },
  { value: 'failed', label: 'Failed' },
];

type ConfirmAction = {
  title: string;
  description: string;
  confirmLabel: string;
  onConfirm: () => void;
};

const DocumentStorePage: React.FC = () => {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | null>(null);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [previewDocument, setPreviewDocument] = useState<DocumentStoreRecord | null>(null);
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);
  const [busyDocIds, setBusyDocIds] = useState<Set<string>>(() => new Set());
  const [reindexAllSnapshot, setReindexAllSnapshot] = useState<Set<string> | null>(null);
  // Track document IDs that have been queued for deletion. The backend delete
  // is asynchronous (returns 202 + background job), so we must keep refetching
  // until these IDs disappear from the list. Without this, the refetchInterval
  // sees no "pending" statuses and stops polling before the background job runs.
  const [pendingDeletionIds, setPendingDeletionIds] = useState<Set<string>>(() => new Set());
  const previewOpen = previewDocument !== null;

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 200);
    return () => clearTimeout(timer);
  }, [search]);

  const documentsQuery = useQuery({
    queryKey: ['document-store', 'documents'],
    queryFn: () => fetchDocuments(),
    refetchInterval: (query) => {
      const docs = query.state.data ?? [];
      const hasPendingDeletion = pendingDeletionIds.size > 0;
      const hasActiveJobs = docs.some((doc) => ['queued', 'reading', 'converting', 'indexing', 'deleting'].includes(doc.status));
      return hasActiveJobs || hasPendingDeletion ? 2500 : false;
    },
  });

  const configQuery = useQuery({
    queryKey: ['document-store', 'config-status'],
    queryFn: () => getConfigStatus(),
    retry: 1,
    staleTime: 30_000,
  });

  const documents = useMemo(() => documentsQuery.data ?? [], [documentsQuery.data]);
  const backendReady = useMemo(() => configQuery.data?.ready ?? false, [configQuery.data]);

  // Clean up pendingDeletionIds once the documents are actually gone from the list.
  useEffect(() => {
    if (pendingDeletionIds.size === 0) return;
    const visibleIds = new Set(documents.map((d) => d.id));
    const stillPending = new Set<string>();
    for (const id of pendingDeletionIds) {
      if (visibleIds.has(id)) stillPending.add(id);
    }
    if (stillPending.size !== pendingDeletionIds.size) {
      setPendingDeletionIds(stillPending);
    }
  }, [documents, pendingDeletionIds]);

  const reindexMutation = useMutation({
    mutationFn: reindexDocument,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['document-store', 'documents'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: (_data, documentId) => {
      setPendingDeletionIds((prev) => new Set(prev).add(documentId));
      queryClient.invalidateQueries({ queryKey: ['document-store', 'documents'] });
    },
  });

  const reindexAllMutation = useMutation({
    mutationFn: reindexAllDocuments,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['document-store', 'documents'] }),
  });

  const clearAllMutation = useMutation({
    mutationFn: clearAllDocuments,
    onSuccess: () => {
      setPendingDeletionIds((prev) => {
        const next = new Set(prev);
        for (const doc of documents) next.add(doc.id);
        return next;
      });
      queryClient.invalidateQueries({ queryKey: ['document-store', 'documents'] });
    },
  });

  const filteredDocuments = useMemo(() => {
    const q = debouncedSearch.trim().toLowerCase();
    return documents.filter((doc) => {
      const matchesStatus = !statusFilter || doc.status === statusFilter;
      const matchesType = !typeFilter || doc.extension === typeFilter;
      const matchesSearch =
        !q ||
        doc.original_filename.toLowerCase().includes(q) ||
        doc.tags.some((tag) => tag.toLowerCase().includes(q));
      return matchesStatus && matchesType && matchesSearch;
    });
  }, [documents, debouncedSearch, statusFilter, typeFilter]);

  const fileTypes = useMemo(() => Array.from(new Set(documents.map((doc) => doc.extension))).sort(), [documents]);
  const typeOptions = fileTypes.map((ext) => ({ value: ext, label: ext.replace('.', '').toUpperCase() }));

  const handleSelect = useCallback((id: string) => {
    const doc = documents.find((d) => d.id === id);
    if (doc) {
      setPreviewDocument(doc);
    }
  }, [documents]);

  const setDocBusy = useCallback((id: string, busy: boolean) => {
    setBusyDocIds((prev) => {
      const next = new Set(prev);
      if (busy) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const handleReindex = useCallback((id: string) => {
    setDocBusy(id, true);
    reindexMutation.mutate(id, {
      onSettled: () => setDocBusy(id, false),
    });
  }, [reindexMutation, setDocBusy]);

  const handleDelete = useCallback((document: DocumentStoreRecord) => {
    setConfirmAction({
      title: `Delete ${document.original_filename}?`,
      description: "This removes the document from Cora's knowledge base.",
      confirmLabel: 'Delete document',
      onConfirm: () => {
        setDocBusy(document.id, true);
        deleteMutation.mutate(document.id, {
          onSettled: () => setDocBusy(document.id, false),
        });
      },
    });
  }, [deleteMutation, setDocBusy]);

  const handleReindexAll = useCallback(() => {
    if (documents.length === 0) return;
    const snapshot = new Set(documents.map((d) => d.id));
    setConfirmAction({
      title: `Reindex all ${documents.length} document${documents.length === 1 ? '' : 's'}?`,
      description: 'This re-chunks and re-embeds every document from its converted text. Use this after changing embedding or chunk settings. Conversion is skipped if Markdown already exists.',
      confirmLabel: 'Reindex all',
      onConfirm: () => {
        setReindexAllSnapshot(snapshot);
        reindexAllMutation.mutate();
      },
    });
  }, [documents, reindexAllMutation]);

  const reindexAllProgress = useMemo(() => {
    if (!reindexAllSnapshot || !reindexAllMutation.isPending) return null;
    const total = reindexAllSnapshot.size;
    const completed = documents.filter(
      (doc) => reindexAllSnapshot.has(doc.id) && !['queued', 'reading', 'converting', 'indexing'].includes(doc.status),
    ).length;
    return { completed, total };
  }, [reindexAllSnapshot, reindexAllMutation.isPending, documents]);

  useEffect(() => {
    if (reindexAllSnapshot && !reindexAllMutation.isPending) {
      const allDone = documents.every(
        (doc) => !reindexAllSnapshot.has(doc.id) || !['queued', 'reading', 'converting', 'indexing'].includes(doc.status),
      );
      if (allDone) setReindexAllSnapshot(null);
    }
  }, [reindexAllSnapshot, reindexAllMutation.isPending, documents]);

  const handleClearAll = useCallback(() => {
    if (documents.length === 0) return;
    setConfirmAction({
      title: `Delete all ${documents.length} document${documents.length === 1 ? '' : 's'}?`,
      description: 'This permanently removes every document, its converted text, and all chunks from the vector store. This cannot be undone.',
      confirmLabel: 'Clear all',
      onConfirm: () => clearAllMutation.mutate(),
    });
  }, [documents.length, clearAllMutation]);

  const handleUploadComplete = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['document-store', 'documents'] });
  }, [queryClient]);

  const actionError = (reindexMutation.error || deleteMutation.error || reindexAllMutation.error || clearAllMutation.error) instanceof Error
    ? ((reindexMutation.error || deleteMutation.error || reindexAllMutation.error || clearAllMutation.error) as Error).message
    : null;

  const bulkBusy = reindexAllMutation.isPending || clearAllMutation.isPending;
  const anyBusy = bulkBusy || reindexMutation.isPending || deleteMutation.isPending;

  return (
    <main className="min-h-screen bg-surface-page">
      <div className="container mx-auto px-4 md:px-12 lg:px-24 pt-16 pb-8 max-w-7xl">
        <nav aria-label="Back navigation" className="mb-4 md:mb-6">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base font-semibold"
          >
            <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5" />
            <span>Document store</span>
          </Link>
        </nav>

        {configQuery.isError && (
          <div className="mb-5 flex items-center gap-3.5 rounded-xl border border-border-ui bg-surface-card px-4 py-3.5 shadow-xs">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-semantic-error-bg text-semantic-error-icon">
              <AlertTriangle className="h-4.5 w-4.5" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-poppins text-[13.5px] font-semibold text-text-primary">Backend unavailable</p>
              <p className="mt-0.5 font-inter text-[12.5px] leading-relaxed text-text-secondary">
                {configQuery.error instanceof Error ? configQuery.error.message : 'The backend isn\u2019t running. Start it with `python -m src.api.main` from the repo root, then retry.'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => configQuery.refetch()}
              className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-border-ui bg-surface-card px-3 font-inter text-xs font-semibold text-text-primary transition-colors hover:bg-surface-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:opacity-50"
              disabled={configQuery.isFetching}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${configQuery.isFetching ? 'animate-spin' : ''}`} />
              {configQuery.isFetching ? 'Retrying' : 'Retry'}
            </button>
          </div>
        )}

        {!configQuery.isError && configQuery.isSuccess && !backendReady && (
          <div className="mb-5 flex items-center gap-3.5 rounded-xl border border-border-ui bg-surface-card px-4 py-3.5 shadow-xs">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-semantic-warning-bg text-semantic-warning-icon">
              <AlertCircle className="h-4.5 w-4.5" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-poppins text-[13.5px] font-semibold text-text-primary">Finish setting up Cora</p>
              <p className="mt-0.5 font-inter text-[12.5px] leading-relaxed text-text-secondary">
                Cora is running but not fully configured. Complete setup in Settings to add documents and unlock all PDF parse modes.
              </p>
            </div>
            <Link
              to="/settings"
              className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-border-ui bg-surface-card px-3 font-inter text-xs font-semibold text-text-primary transition-colors hover:bg-surface-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
            >
              <SettingsIcon className="h-3.5 w-3.5" />
              Open Settings
            </Link>
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[1fr_360px] items-start">
          {/* Knowledge base */}
          <section className="bg-surface-card rounded-xl border border-border-ui shadow-xs overflow-hidden">
            <div className="px-5 py-4 border-b border-border-ui">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="font-poppins text-xl font-semibold text-text-primary">Knowledge base</h2>
                  <p className="font-inter text-xs text-text-muted mt-0.5">
                    {debouncedSearch || statusFilter || typeFilter
                      ? `Showing ${filteredDocuments.length} of ${documents.length} document${documents.length === 1 ? '' : 's'}`
                      : `${documents.length} document${documents.length === 1 ? '' : 's'}`}
                  </p>
                </div>
                {documents.length > 0 && (
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={handleReindexAll}
                      disabled={anyBusy}
                      className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-border-ui px-3 font-inter text-xs font-semibold text-text-primary hover:bg-surface-subtle disabled:opacity-50"
                      title="Re-chunk and re-embed all documents from their converted text"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 ${reindexAllMutation.isPending ? 'animate-spin' : ''}`} />
                      Reindex all
                    </button>
                    <button
                      type="button"
                      onClick={handleClearAll}
                      disabled={anyBusy}
                      className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-semantic-error-border px-3 font-inter text-xs font-semibold text-semantic-error-text hover:bg-semantic-error-bg disabled:opacity-50"
                      title="Delete all documents and remove them from the knowledge base"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Clear all
                    </button>
                  </div>
                )}
              </div>

              <DocumentFilters
                search={search}
                onSearchChange={setSearch}
                statusFilter={statusFilter}
                onStatusFilterChange={setStatusFilter}
                typeFilter={typeFilter}
                onTypeFilterChange={setTypeFilter}
                statusOptions={statusOptions}
                typeOptions={typeOptions}
              />
            </div>

            {reindexAllProgress && (
              <div className="flex items-center gap-3 px-5 py-2.5 border-b border-border-ui bg-brand-50/50">
                <RefreshCw className="h-3.5 w-3.5 animate-spin text-brand-500 shrink-0" />
                <span className="font-inter text-xs text-text-secondary">
                  Reindexing: {reindexAllProgress.completed} of {reindexAllProgress.total} complete
                </span>
                <div className="flex-1 h-1.5 rounded-full bg-surface-subtle overflow-hidden max-w-[200px]">
                  <div
                    className="h-full rounded-full bg-brand-500 transition-all duration-300"
                    style={{ width: `${reindexAllProgress.total ? (reindexAllProgress.completed / reindexAllProgress.total) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}

            <div role="list">
              {documents.length > 0 && !documentsQuery.isLoading && (
                <div className="hidden sm:grid grid-cols-[1fr_100px_90px_64px] gap-3 px-4 py-2 border-b border-border-ui bg-surface-base font-inter text-xs font-semibold text-text-muted uppercase tracking-wider">
                  <span>Name</span>
                  <span className="text-right">Date</span>
                  <span className="text-right">Status</span>
                  <span></span>
                </div>
              )}

              {documentsQuery.isLoading && (
                <div className="px-5 py-10 text-center">
                  <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-brand-200 border-t-brand-500" />
                  <p className="mt-3 font-inter text-sm text-text-muted">Loading documents...</p>
                </div>
              )}

              {!documentsQuery.isLoading && filteredDocuments.length === 0 && (
                <div className="px-5 py-14 text-center">
                  <div className="mx-auto h-12 w-12 flex items-center justify-center rounded-xl bg-surface-subtle text-text-muted">
                    <FileText className="h-6 w-6" />
                  </div>
                  <p className="mt-4 font-poppins text-base font-semibold text-text-primary">
                    {documents.length === 0 ? 'No documents yet' : 'No matches'}
                  </p>
                  <p className="mt-1 font-inter text-sm text-text-muted">
                    {documents.length === 0 ? 'Add documents to start building your knowledge base.' : 'Try a different search or filter.'}
                  </p>
                </div>
              )}

              {!documentsQuery.isLoading && filteredDocuments.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  document={doc}
                  onSelect={handleSelect}
                  onReindex={handleReindex}
                  onDelete={handleDelete}
                  isReindexing={busyDocIds.has(doc.id) && reindexMutation.isPending}
                  isDeleting={busyDocIds.has(doc.id) && deleteMutation.isPending}
                />
              ))}
            </div>
          </section>

          {/* Right column: Add docs */}
          <div className="space-y-5 lg:sticky lg:top-6">
            <UploadPanel
              backendReady={backendReady}
              onUploadComplete={handleUploadComplete}
            />

            {actionError && (
              <div className="flex items-start gap-2.5 rounded-xl border border-semantic-error-border bg-semantic-error-bg px-4 py-3.5">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-semantic-error-icon" aria-hidden="true" />
                <span className="flex-1 font-inter text-[12.5px] leading-relaxed text-semantic-error-text">{actionError}</span>
                <button
                  type="button"
                  onClick={() => {
                    reindexMutation.reset();
                    deleteMutation.reset();
                    reindexAllMutation.reset();
                    clearAllMutation.reset();
                  }}
                  className="mt-0.5 shrink-0 rounded-md p-0.5 text-semantic-error-text transition-colors hover:bg-semantic-error-bg hover:text-semantic-error-text focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
                  aria-label="Dismiss error"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>

          <ConfirmDialog
            open={confirmAction !== null}
            onOpenChange={(open) => { if (!open) setConfirmAction(null); }}
            title={confirmAction?.title ?? ''}
            description={confirmAction?.description}
            confirmLabel={confirmAction?.confirmLabel ?? ''}
            variant="destructive"
            onConfirm={() => {
              confirmAction?.onConfirm();
              setConfirmAction(null);
            }}
          />

          {/* Document preview modal */}
          <Dialog open={previewOpen} onOpenChange={(open) => { if (!open) setPreviewDocument(null); }}>
            <DialogContent className="max-w-5xl w-[calc(100%-2rem)] rounded-xl p-0 flex flex-col max-h-[90vh] overflow-hidden">
              <DialogHeader className="px-5 py-4 border-b border-border-ui">
                <DialogTitle className="font-poppins text-base font-semibold text-text-primary">Document preview</DialogTitle>
                <DialogDescription className="sr-only">Preview the selected document content and status.</DialogDescription>
              </DialogHeader>
              <div className="flex-1 overflow-auto p-5">
                {previewDocument ? (
                  <DocumentPreview
                    document={previewDocument}
                    isBusy={anyBusy}
                  />
                ) : (
                  <p className="text-center font-inter text-sm text-text-muted">Select a document to preview.</p>
                )}
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <ScrollToTop />
    </main>
  );
};

export default function DocumentStorePageWrapper(): JSX.Element {
  const [error, setError] = useState<Error | null>(null);

  return (
    <ErrorBoundary
      onError={(err) => setError(err)}
      fallback={
        <div className="min-h-screen bg-surface-page flex flex-col items-center justify-center p-6">
          <div
            className="w-full max-w-sm rounded-xl border border-border-ui bg-surface-card p-8 text-center shadow-card"
            role="alert"
            aria-live="assertive"
          >
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-semantic-error-bg text-semantic-error-icon">
              <AlertCircle className="h-6 w-6" aria-hidden="true" />
            </div>
            <h1 className="mt-5 font-poppins text-lg font-semibold text-text-primary">
              Document store unavailable
            </h1>
            <p className="mt-1.5 font-inter text-sm leading-relaxed text-text-secondary">
              Something went wrong while loading this page.
            </p>
            {error && (
              <div className="mt-4 rounded-lg border border-semantic-error-border bg-semantic-error-bg p-3 text-left">
                <p className="font-inter text-xs leading-relaxed text-semantic-error-text break-words">
                  {error.message}
                </p>
              </div>
            )}
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-6 inline-flex h-9 items-center gap-2 rounded-lg bg-brand-700 px-5 font-inter text-sm font-semibold text-white transition-colors hover:bg-brand-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-2"
            >
              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
              Reload
            </button>
          </div>
        </div>
      }
    >
      <DocumentStorePage />
    </ErrorBoundary>
  );
}
