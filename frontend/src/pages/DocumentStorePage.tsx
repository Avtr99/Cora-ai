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
  // Track docs awaiting worker pickup after reindex. The API route deliberately
  // keeps the doc at its current status (e.g. 'failed') until the worker claims
  // the job, so the hasActiveJobs polling gate doesn't fire. We keep polling
  // these docs until they transition to an active status or the timeout expires.
  const [pendingReindexIds, setPendingReindexIds] = useState<Map<string, number>>(() => new Map());
  const REINDEX_POLL_TIMEOUT_MS = 60_000;
  const previewOpen = previewDocument !== null;

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 200);
    return () => clearTimeout(timer);
  }, [search]);

  const documentsQuery = useQuery({
    queryKey: ['document-store', 'documents'],
    queryFn: ({ signal }) => fetchDocuments({}, signal),
    refetchInterval: (query) => {
      const docs = query.state.data ?? [];
      const hasPendingDeletion = pendingDeletionIds.size > 0;
      const hasPendingReindex = pendingReindexIds.size > 0;
      const hasActiveJobs = docs.some((doc) => ['queued', 'reading', 'converting', 'indexing', 'deleting'].includes(doc.status));
      return hasActiveJobs || hasPendingDeletion || hasPendingReindex ? 2500 : false;
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

  // Remove reindexed doc IDs from pending once the worker picks them up (doc
  // enters an active status → hasActiveJobs takes over) or the timeout expires
  // (worker down — stop polling, doc stays at its current status for retry).
  // Also remove IDs whose doc has disappeared (deleted while pending reindex)
  // so we don't keep polling for a doc that no longer exists.
  useEffect(() => {
    if (pendingReindexIds.size === 0) return;
    const now = Date.now();
    const activeStatuses = ['queued', 'reading', 'converting', 'indexing', 'deleting'];
    const next = new Map(pendingReindexIds);
    for (const [id, ts] of pendingReindexIds) {
      if (now - ts > REINDEX_POLL_TIMEOUT_MS) {
        next.delete(id);
        continue;
      }
      const doc = documents.find((d) => d.id === id);
      if (!doc || activeStatuses.includes(doc.status)) {
        next.delete(id);
      }
    }
    if (next.size !== pendingReindexIds.size) setPendingReindexIds(next);
  }, [documents, pendingReindexIds]);

  const reindexMutation = useMutation({
    mutationFn: reindexDocument,
    onSuccess: (_data, documentId) => {
      setPendingReindexIds((prev) => new Map(prev).set(documentId, Date.now()));
      queryClient.invalidateQueries({ queryKey: ['document-store', 'documents'] });
    },
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
        setPendingReindexIds((prev) => {
          const next = new Map(prev);
          const now = Date.now();
          for (const id of snapshot) next.set(id, now);
          return next;
        });
        reindexAllMutation.mutate();
      },
    });
  }, [documents, reindexAllMutation]);

  const reindexAllProgress = useMemo(() => {
    if (!reindexAllSnapshot) return null;
    const total = reindexAllSnapshot.size;
    const completed = documents.filter(
      (doc) => reindexAllSnapshot.has(doc.id)
        && !['queued', 'reading', 'converting', 'indexing'].includes(doc.status)
        && !pendingReindexIds.has(doc.id),
    ).length;
    return { completed, total };
  }, [reindexAllSnapshot, pendingReindexIds, documents]);

  useEffect(() => {
    if (!reindexAllSnapshot) return;
    const allDone = documents.every(
      (doc) => !reindexAllSnapshot.has(doc.id)
        || (!['queued', 'reading', 'converting', 'indexing'].includes(doc.status) && !pendingReindexIds.has(doc.id)),
    );
    if (allDone) setReindexAllSnapshot(null);
  }, [reindexAllSnapshot, pendingReindexIds, documents]);

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
      <div className="container mx-auto px-4 md:px-12 lg:px-24 3xl:px-24 4xl:px-32 pt-16 3xl:pt-20 4xl:pt-24 pb-8 3xl:pb-12 4xl:pb-16 max-w-7xl 3xl:max-w-[1600px] 4xl:max-w-[1800px]">
        <nav aria-label="Back navigation" className="mb-4 md:mb-6 3xl:mb-8 4xl:mb-10">
          <Link
            to="/"
            className="inline-flex items-center gap-2 3xl:gap-2.5 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base 3xl:text-lg 4xl:text-xl font-semibold"
          >
            <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5 3xl:!w-5 3xl:!h-5 4xl:!w-6 4xl:!h-6" />
            <span>Document store</span>
          </Link>
        </nav>

        {configQuery.isError && (
          <div className="mb-5 3xl:mb-8 flex items-center gap-3.5 3xl:gap-5 rounded-xl 3xl:rounded-2xl border border-border-ui bg-surface-card px-4 3xl:px-6 4xl:px-8 py-3.5 3xl:py-5 shadow-xs">
            <span className="flex h-9 w-9 3xl:h-12 3xl:w-12 4xl:h-14 4xl:w-14 shrink-0 items-center justify-center rounded-full bg-semantic-error-bg text-semantic-error-icon">
              <AlertTriangle className="h-4.5 w-4.5 3xl:h-6 3xl:w-6" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-inter text-heading-3 3xl:text-lg 4xl:text-xl font-semibold text-text-primary">Backend unavailable</p>
              <p className="mt-0.5 font-inter text-caption 3xl:text-sm 4xl:text-base text-text-secondary">
                {configQuery.error instanceof Error ? configQuery.error.message : 'The backend isn\u2019t running. Start it with `python -m src.api.main` from the repo root, then retry.'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => configQuery.refetch()}
              className="inline-flex h-8 3xl:h-10 4xl:h-12 shrink-0 items-center gap-1.5 3xl:gap-2 rounded-lg 3xl:rounded-xl border border-border-ui bg-surface-card px-3 3xl:px-4 font-inter text-ui 3xl:text-sm 4xl:text-base font-semibold text-text-primary transition-colors hover:bg-surface-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:opacity-50"
              disabled={configQuery.isFetching}
            >
              <RefreshCw className={`h-3.5 w-3.5 3xl:h-4 3xl:w-4 4xl:h-5 4xl:w-5 ${configQuery.isFetching ? 'animate-spin' : ''}`} />
              {configQuery.isFetching ? 'Retrying' : 'Retry'}
            </button>
          </div>
        )}

        {!configQuery.isError && configQuery.isSuccess && !backendReady && (
          <div className="mb-5 3xl:mb-8 flex items-center gap-3.5 3xl:gap-5 rounded-xl 3xl:rounded-2xl border border-border-ui bg-surface-card px-4 3xl:px-6 4xl:px-8 py-3.5 3xl:py-5 shadow-xs">
            <span className="flex h-9 w-9 3xl:h-12 3xl:w-12 4xl:h-14 4xl:w-14 shrink-0 items-center justify-center rounded-full bg-semantic-warning-bg text-semantic-warning-icon">
              <AlertCircle className="h-4.5 w-4.5 3xl:h-6 3xl:w-6" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="font-inter text-heading-3 3xl:text-lg 4xl:text-xl font-semibold text-text-primary">Finish setting up Cora</p>
              <p className="mt-0.5 font-inter text-caption 3xl:text-sm 4xl:text-base text-text-secondary">
                Cora is running but not fully configured. Complete setup in Settings to add documents and unlock all PDF parse modes.
              </p>
            </div>
            <Link
              to="/settings"
              className="inline-flex h-8 3xl:h-10 4xl:h-12 shrink-0 items-center gap-1.5 3xl:gap-2 rounded-lg 3xl:rounded-xl border border-border-ui bg-surface-card px-3 3xl:px-4 font-inter text-ui 3xl:text-sm 4xl:text-base font-semibold text-text-primary transition-colors hover:bg-surface-subtle focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
            >
              <SettingsIcon className="h-3.5 w-3.5 3xl:h-4 3xl:w-4 4xl:h-5 4xl:w-5" />
              Open Settings
            </Link>
          </div>
        )}

        <div className="grid gap-5 3xl:gap-8 4xl:gap-10 lg:grid-cols-[1fr_360px] 3xl:grid-cols-[1fr_440px] 4xl:grid-cols-[1fr_520px] items-start">
          {/* Knowledge base */}
          <section className="bg-surface-card rounded-xl 3xl:rounded-2xl border border-border-ui shadow-xs overflow-hidden">
            <div className="px-5 3xl:px-8 4xl:px-10 py-4 3xl:py-6 4xl:py-8 border-b border-border-ui">
              <div className="flex items-center justify-between gap-3 3xl:gap-4">
                <div>
                  <h2 className="font-poppins text-heading-2 3xl:text-xl 4xl:text-2xl font-semibold text-text-primary">Knowledge base</h2>
                  <p className="font-inter text-caption 3xl:text-sm 4xl:text-base text-text-muted mt-0.5 3xl:mt-1">
                    {debouncedSearch || statusFilter || typeFilter
                      ? `Showing ${filteredDocuments.length} of ${documents.length} document${documents.length === 1 ? '' : 's'}`
                      : `${documents.length} document${documents.length === 1 ? '' : 's'}`}
                  </p>
                </div>
                {documents.length > 0 && (
                  <div className="flex items-center gap-2 3xl:gap-3">
                    <button
                      type="button"
                      onClick={handleReindexAll}
                      disabled={anyBusy}
                      className="inline-flex h-8 3xl:h-10 4xl:h-12 items-center gap-1.5 3xl:gap-2 rounded-lg 3xl:rounded-xl border border-border-ui px-3 3xl:px-4 4xl:px-5 font-inter text-ui 3xl:text-sm 4xl:text-base font-semibold text-text-primary hover:bg-surface-subtle disabled:opacity-50"
                      title="Re-chunk and re-embed all documents from their converted text"
                    >
                      <RefreshCw className={`h-3.5 w-3.5 3xl:h-4 3xl:w-4 4xl:h-5 4xl:w-5 ${reindexAllMutation.isPending ? 'animate-spin' : ''}`} />
                      Reindex all
                    </button>
                    <button
                      type="button"
                      onClick={handleClearAll}
                      disabled={anyBusy}
                      className="inline-flex h-8 3xl:h-10 4xl:h-12 items-center gap-1.5 3xl:gap-2 rounded-lg 3xl:rounded-xl border border-semantic-error-border px-3 3xl:px-4 4xl:px-5 font-inter text-ui 3xl:text-sm 4xl:text-base font-semibold text-semantic-error-text hover:bg-semantic-error-bg disabled:opacity-50"
                      title="Delete all documents and remove them from the knowledge base"
                    >
                      <Trash2 className="h-3.5 w-3.5 3xl:h-4 3xl:w-4 4xl:h-5 4xl:w-5" />
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
              <div className="flex items-center gap-3 3xl:gap-4 px-5 3xl:px-8 4xl:px-10 py-2.5 3xl:py-4 border-b border-border-ui bg-brand-50/50">
                <RefreshCw className="h-3.5 w-3.5 3xl:h-5 3xl:w-5 4xl:h-6 4xl:w-6 animate-spin text-brand-500 shrink-0" />
                <span className="font-inter text-caption 3xl:text-sm 4xl:text-base text-text-secondary">
                  Reindexing: {reindexAllProgress.completed} of {reindexAllProgress.total} complete
                </span>
                <div className="flex-1 h-1.5 3xl:h-2 4xl:h-2.5 rounded-full bg-surface-subtle overflow-hidden max-w-[200px] 3xl:max-w-[280px] 4xl:max-w-[320px]">
                  <div
                    className="h-full rounded-full bg-brand-500 transition-all duration-300"
                    style={{ width: `${reindexAllProgress.total ? (reindexAllProgress.completed / reindexAllProgress.total) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}

            <div role="list">
              {documents.length > 0 && !documentsQuery.isLoading && (
                <div className="hidden sm:grid grid-cols-[1fr_100px_90px_64px] 3xl:grid-cols-[1fr_140px_130px_96px] 4xl:grid-cols-[1fr_160px_150px_112px] gap-3 3xl:gap-4 px-4 3xl:px-6 4xl:px-8 py-2 3xl:py-3 border-b border-border-ui bg-surface-base font-inter text-overline 3xl:text-xs 4xl:text-sm uppercase tracking-wider font-semibold text-text-muted">
                  <span>Name</span>
                  <span className="text-right">Date</span>
                  <span className="text-right">Status</span>
                  <span></span>
                </div>
              )}

              {documentsQuery.isLoading && (
                <div className="px-5 3xl:px-8 py-10 3xl:py-14 4xl:py-16 text-center">
                  <div className="mx-auto h-6 w-6 3xl:h-8 3xl:w-8 4xl:h-10 4xl:w-10 animate-spin rounded-full border-2 border-brand-200 border-t-brand-500" />
                  <p className="mt-3 3xl:mt-4 font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-muted">Loading documents...</p>
                </div>
              )}

              {!documentsQuery.isLoading && filteredDocuments.length === 0 && (
                <div className="px-5 3xl:px-8 py-14 3xl:py-20 4xl:py-24 text-center">
                  <div className="mx-auto h-12 w-12 3xl:h-16 3xl:w-16 4xl:h-20 4xl:w-20 flex items-center justify-center rounded-xl 3xl:rounded-2xl bg-surface-subtle text-text-muted">
                    <FileText className="h-6 w-6 3xl:h-8 3xl:w-8 4xl:h-10 4xl:w-10" />
                  </div>
                  <p className="mt-3 3xl:mt-4 font-inter text-heading-3 3xl:text-lg 4xl:text-xl font-semibold text-text-primary">
                    {documents.length === 0 ? 'No documents yet' : 'No matches'}
                  </p>
                  <p className="mt-0.5 3xl:mt-1 font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-muted">
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
                  isReindexing={(busyDocIds.has(doc.id) && reindexMutation.isPending) || pendingReindexIds.has(doc.id)}
                  isDeleting={busyDocIds.has(doc.id) && deleteMutation.isPending}
                  isPendingReindex={pendingReindexIds.has(doc.id)}
                />
              ))}
            </div>
          </section>

          {/* Right column: Add docs */}
          <div className="space-y-5 3xl:space-y-8 4xl:space-y-10 lg:sticky lg:top-6 3xl:top-8 4xl:top-10">
            <UploadPanel
              backendReady={backendReady}
              onUploadComplete={handleUploadComplete}
            />

            {actionError && (
              <div className="flex items-start gap-2.5 3xl:gap-3 rounded-xl 3xl:rounded-2xl border border-semantic-error-border bg-semantic-error-bg px-4 3xl:px-5 py-3.5 3xl:py-4 4xl:py-5">
                <AlertTriangle className="mt-0.5 h-4 w-4 3xl:h-5 3xl:w-5 shrink-0 text-semantic-error-icon" aria-hidden="true" />
                <span className="flex-1 font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-semantic-error-text">{actionError}</span>
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
            <DialogContent className="max-w-5xl 3xl:max-w-6xl 4xl:max-w-7xl w-[calc(100%-2rem)] rounded-xl 3xl:rounded-2xl p-0 flex flex-col max-h-[90vh] overflow-hidden">
              <DialogHeader className="px-5 3xl:px-8 4xl:px-10 py-4 3xl:py-6 border-b border-border-ui">
                <DialogTitle className="font-poppins text-heading-3 3xl:text-lg 4xl:text-xl font-semibold text-text-primary">Document preview</DialogTitle>
                <DialogDescription className="sr-only">Preview the selected document content and status.</DialogDescription>
              </DialogHeader>
              <div className="flex-1 overflow-auto p-5 3xl:p-8 4xl:p-10">
                {previewDocument ? (
                  <DocumentPreview
                    document={previewDocument}
                    isBusy={anyBusy}
                  />
                ) : (
                  <p className="text-center font-inter text-body-sm text-text-muted">Select a document to preview.</p>
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
            <h1 className="mt-5 font-poppins text-heading-1 font-semibold text-text-primary">
              Document store unavailable
            </h1>
            <p className="mt-1.5 font-inter text-body-sm leading-relaxed text-text-secondary">
              Something went wrong while loading this page.
            </p>
            {error && (
              <div className="mt-4 rounded-lg border border-semantic-error-border bg-semantic-error-bg p-3 text-left">
                <p className="font-inter text-caption text-semantic-error-text break-words">
                  {error.message}
                </p>
              </div>
            )}
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-6 inline-flex h-9 items-center gap-2 rounded-lg bg-brand-700 px-5 font-inter text-body-sm font-semibold text-white transition-colors hover:bg-brand-hover focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 focus-visible:ring-offset-2"
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
