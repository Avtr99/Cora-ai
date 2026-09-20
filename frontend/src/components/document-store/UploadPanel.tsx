import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, X, AlertCircle, ChevronDown } from 'lucide-react';
import {
  uploadDocumentsBatch,
  fetchConversionCapabilities,
  DOCUMENT_UPLOAD_MAX_BYTES,
  type ConversionMode,
  type ConversionCapabilities,
  type DocumentUploadBatchResult,
} from '@/services/documentStoreApi';
import { FileDropzone } from './FileDropzone';
import { StagedFilesList } from './StagedFilesList';
import { ConversionModeSelector } from './ConversionModeSelector';
import { FileTypeSummary } from './FileTypeSummary';

// ponytail: fallback only. The authoritative list comes from the server via
// /conversion-info -> upload_limits.allowed_extensions. Kept here so the
// dropzone still works before capabilities load (e.g. backend slow to start).
const FALLBACK_ALLOWED_EXTENSIONS = ['.pdf', '.md', '.txt', '.csv', '.json', '.jsonl'];

let stagedId = 0;
function nextStagedId(): string {
  stagedId += 1;
  return `staged-${stagedId}-${Date.now()}`;
}

function isAllowedFile(file: File, allowedExtensions: string[]): boolean {
  const ext = `.${file.name.split('.').pop()?.toLowerCase() ?? ''}`;
  return allowedExtensions.includes(ext);
}

interface UploadPanelProps {
  backendReady: boolean;
  onUploadComplete: () => void;
}

export const UploadPanel: React.FC<UploadPanelProps> = ({ backendReady, onUploadComplete }) => {
  const [stagedFiles, setStagedFiles] = useState<Array<{ id: string; file: File }>>([]);
  const [conversionMode, setConversionMode] = useState<ConversionMode>('standard');
  const [capabilities, setCapabilities] = useState<ConversionCapabilities | null>(null);
  const [tags, setTags] = useState('');
  const [showTags, setShowTags] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState({ done: 0, total: 0 });
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dropError, setDropError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [workerWarning, setWorkerWarning] = useState<string | null>(null);

  const maxBytes = capabilities?.upload_limits?.max_bytes ?? DOCUMENT_UPLOAD_MAX_BYTES;
  const maxMbLabel = `${Math.round(maxBytes / (1024 * 1024))} MB`;
  const allowedExtensions = capabilities?.upload_limits?.allowed_extensions ?? FALLBACK_ALLOWED_EXTENSIONS;

  // Worker-down warning: in worker-dispatch mode, if the ingest-worker is not
  // running, uploads will be accepted and queued but never processed. Surface
  // this *before* the user uploads so they can start the worker first. This is
  // a runtime liveness signal (from worker_status), distinct from the
  // deployment-capability signal (standard.available) which only says whether
  // the deployment *can* do Standard mode.
  const workerDown =
    capabilities?.worker_status?.dispatch_mode === 'worker' &&
    !capabilities?.worker_status?.alive;

  useEffect(() => {
    if (!backendReady) return;
    fetchConversionCapabilities()
      .then(setCapabilities)
      .catch(() => setCapabilities(null));
  }, [backendReady]);

  const isModeAvailable = useCallback(
    (mode: ConversionMode): boolean => {
      if (!capabilities) return mode === 'standard';
      return capabilities[mode]?.available ?? false;
    },
    [capabilities],
  );

  // Auto-fallback to standard if the selected mode is unavailable
  useEffect(() => {
    if (capabilities && !isModeAvailable(conversionMode)) {
      setConversionMode('standard');
    }
  }, [capabilities, conversionMode, isModeAvailable]);

  const handleAddFiles = useCallback((files: File[]) => {
    const maxMb = Math.round(maxBytes / (1024 * 1024));
    const valid: File[] = [];
    const invalid: string[] = [];
    const oversized: string[] = [];
    files.forEach((file) => {
      if (!isAllowedFile(file, allowedExtensions)) {
        invalid.push(file.name);
      } else if (file.size > maxBytes) {
        oversized.push(file.name);
      } else {
        valid.push(file);
      }
    });

    const errors: string[] = [];
    if (invalid.length) {
      errors.push(invalid.length === 1 ? `Skipped ${invalid[0]}: unsupported type.` : `Skipped ${invalid.length} files: unsupported types.`);
    }
    if (oversized.length) {
      errors.push(oversized.length === 1 ? `Skipped ${oversized[0]}: file is over ${maxMb} MB.` : `Skipped ${oversized.length} files: each file must be ${maxMb} MB or smaller.`);
    }
    setDropError(errors.length ? errors.join(' ') : null);

    if (valid.length) {
      setUploadSuccess(null);
      setStagedFiles((prev) => [...prev, ...valid.map((file) => ({ id: nextStagedId(), file }))]);
    }
  }, [allowedExtensions, maxBytes]);

  const handleIngest = useCallback(async () => {
    if (stagedFiles.length === 0) return;
    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    setWorkerWarning(null);
    setUploadProgress({ done: 0, total: stagedFiles.length });
    const parsedTags = tags.split(',').map((tag) => tag.trim()).filter(Boolean);
    const results = await uploadDocumentsBatch(
      stagedFiles.map((f) => f.file),
      conversionMode,
      parsedTags,
      (done) => setUploadProgress({ done, total: stagedFiles.length }),
    );
    const failures = results.filter(
      (result): result is Extract<DocumentUploadBatchResult, { ok: false }> => !result.ok,
    );
    const uploadedCount = results.length - failures.length;

    if (uploadedCount > 0) {
      const failedFiles = new Set(failures.map((f) => f.file));
      setStagedFiles((prev) => prev.filter((staged) => failedFiles.has(staged.file)));
      let successMsg = `${uploadedCount} document${uploadedCount === 1 ? '' : 's'} queued for processing.`;
      // Add cost estimate for llm_api mode
      const modeInfo = capabilities?.[conversionMode];
      if (modeInfo && modeInfo.privacy === 'external' && modeInfo.cost_per_page && modeInfo.cost_per_page !== '—') {
        const providerLabel = modeInfo.provider === 'gemini' ? 'Gemini' : 'OpenAI';
        successMsg += ` Estimated cost: ${modeInfo.cost_per_page} per page (${providerLabel} ${modeInfo.model || ''}).`;
      }
      // Surface the backend's post-upload warning (e.g. worker went down
      // between the capability check and the upload) as a separate yellow
      // banner, NOT appended to the green success message — mixing "queued
      // for processing" (positive) with "will not be processed" (warning) in
      // the same green banner is a tonal/visual conflict.
      const successResults = results.filter(
        (r): r is Extract<DocumentUploadBatchResult, { ok: true }> => r.ok,
      );
      const warning = successResults.find((r) => r.response.warning)?.response.warning;
      if (warning) {
        setWorkerWarning(warning);
      }
      setUploadSuccess(successMsg);
      setTags('');
      setShowTags(false);
      onUploadComplete();
    }
    if (failures.length > 0) {
      const details = failures.slice(0, 3).map((failure) => `${failure.file.name}: ${failure.error}`).join(' ');
      setUploadError(`${uploadedCount} of ${results.length} uploaded; ${failures.length} failed. ${details}`);
    }
    setIsUploading(false);
  }, [stagedFiles, conversionMode, tags, onUploadComplete, capabilities]);

  const clearErrors = () => {
    setUploadError(null);
    setDropError(null);
  };

  const handleRemove = useCallback((id: string) => {
    setStagedFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const handleClear = useCallback(() => {
    setStagedFiles([]);
  }, []);

  const displayError = uploadError || dropError;
  const uploadDisabled = !backendReady || stagedFiles.length === 0 || isUploading;

  const buttonLabel = useMemo(() => {
    if (!backendReady) return 'Backend not ready';
    if (isUploading) return 'Adding documents...';
    const count = stagedFiles.length ? `${stagedFiles.length} ` : '';
    return `Add ${count}file${stagedFiles.length === 1 ? '' : 's'} to knowledge base`;
  }, [backendReady, isUploading, stagedFiles.length]);

  const pdfCount = stagedFiles.filter((s) => s.file.name.toLowerCase().endsWith('.pdf')).length;
  const nonPdfCount = stagedFiles.length - pdfCount;

  return (
    <section className="bg-surface-card rounded-xl 3xl:rounded-2xl border border-border-ui shadow-xs overflow-hidden">
      <div className="px-5 3xl:px-8 4xl:px-10 py-4 3xl:py-6 4xl:py-8 border-b border-border-ui">
        <h2 className="font-poppins text-heading-2 3xl:text-xl 4xl:text-2xl font-semibold text-text-primary">Add documents</h2>
        <p className="font-inter text-caption 3xl:text-sm 4xl:text-base text-text-muted mt-0.5 3xl:mt-1">
          Stage files, then build your knowledge base in one go.
        </p>
      </div>

      <div className="p-5 3xl:p-7 4xl:p-8">
        <FileDropzone
          backendReady={backendReady}
          allowedExtensions={allowedExtensions}
          maxMbLabel={maxMbLabel}
          onFilesAdded={handleAddFiles}
        />

        {workerDown && (
          <div className="mt-3 3xl:mt-4 flex items-start gap-2 3xl:gap-2.5 rounded-lg 3xl:rounded-xl bg-semantic-warning-bg/50 border border-semantic-warning-border p-2.5 3xl:p-3.5 text-semantic-warning-text text-caption 3xl:text-[13px] 4xl:text-sm font-inter">
            <AlertCircle className="h-4 w-4 3xl:h-5 3xl:w-5 shrink-0 mt-0.5" aria-hidden="true" />
            <span className="flex-1">
              The background PDF parser is not running, so uploaded files won&apos;t be
              added to the knowledge base until it starts. Start it from your terminal: <code className="font-mono text-micro">docker compose up -d ingest-worker</code>
            </span>
          </div>
        )}

        {uploadSuccess && (
          <div className="mt-3 3xl:mt-4 flex items-start gap-2 3xl:gap-2.5 rounded-lg 3xl:rounded-xl bg-semantic-success-bg p-2.5 3xl:p-3.5 text-semantic-success-text text-caption 3xl:text-[13px] 4xl:text-sm font-inter">
            <CheckCircle2 className="h-4 w-4 3xl:h-5 3xl:w-5 shrink-0 mt-0.5" />
            <span className="flex-1">{uploadSuccess}</span>
            <button type="button" onClick={() => setUploadSuccess(null)} className="shrink-0" aria-label="Dismiss success message">
              <X className="h-4 w-4 3xl:h-5 3xl:w-5" />
            </button>
          </div>
        )}

        {workerWarning && (
          <div className="mt-3 3xl:mt-4 flex items-start gap-2 3xl:gap-2.5 rounded-lg 3xl:rounded-xl bg-semantic-warning-bg/50 border border-semantic-warning-border p-2.5 3xl:p-3.5 text-semantic-warning-text text-caption 3xl:text-[13px] 4xl:text-sm font-inter">
            <AlertCircle className="h-4 w-4 3xl:h-5 3xl:w-5 shrink-0 mt-0.5" aria-hidden="true" />
            <span className="flex-1">{workerWarning}</span>
            <button type="button" onClick={() => setWorkerWarning(null)} className="shrink-0" aria-label="Dismiss warning message">
              <X className="h-4 w-4 3xl:h-5 3xl:w-5" />
            </button>
          </div>
        )}

        {displayError && (
          <div className="mt-3 3xl:mt-4 flex items-start gap-2 3xl:gap-2.5 rounded-lg 3xl:rounded-xl bg-semantic-error-bg p-2.5 3xl:p-3.5 text-semantic-error-text text-caption 3xl:text-[13px] 4xl:text-sm font-inter">
            <AlertCircle className="h-4 w-4 3xl:h-5 3xl:w-5 shrink-0 mt-0.5" />
            <span className="flex-1">{displayError}</span>
            <button type="button" onClick={clearErrors} className="shrink-0" aria-label="Dismiss error message">
              <X className="h-4 w-4 3xl:h-5 3xl:w-5" />
            </button>
          </div>
        )}

        <StagedFilesList
          files={stagedFiles}
          isUploading={isUploading}
          onRemove={handleRemove}
          onClear={handleClear}
        />

        <div className="mt-4 3xl:mt-6 4xl:mt-8">
          {/* ponytail: the parse-mode selector is a PDF-only concept. Every other
              accepted format has exactly one correct handling determined by its
              structure (MD passes through, TXT wraps, CSV/JSON/JSONL flatten).
              Show the selector only when PDFs are present; otherwise communicate
              what will happen per file type. */}
          {stagedFiles.length === 0 ? (
            <>
              <p className="font-inter text-heading-3 3xl:text-lg 4xl:text-xl font-medium text-text-primary mb-2 3xl:mb-3">PDF parse mode</p>
              <p className="font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-secondary mb-3 3xl:mb-4">
                Only PDFs need a parse mode. Text, Markdown, and structured files (CSV, JSON) are handled automatically.
              </p>
              <ConversionModeSelector
                conversionMode={conversionMode}
                setConversionMode={setConversionMode}
                capabilities={capabilities}
              />
            </>
          ) : pdfCount === 0 ? (
            <div className="rounded-lg 3xl:rounded-xl border border-border-ui bg-surface-subtle/40 p-3 3xl:p-5 4xl:p-6">
              <p className="font-inter text-heading-3 3xl:text-lg 4xl:text-xl font-medium text-text-primary mb-1 3xl:mb-2">No parsing needed</p>
              <p className="font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-secondary">
                These files are already structured or text-based, so they&apos;ll be added directly without AI parsing.
              </p>
              <FileTypeSummary files={stagedFiles} />
            </div>
          ) : (
            <>
              <p className="font-inter text-heading-3 3xl:text-lg 4xl:text-xl font-medium text-text-primary mb-2 3xl:mb-3">PDF parse mode</p>
              {nonPdfCount > 0 && (
                <p className="font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-secondary mb-3 3xl:mb-4">
                  Applies to {pdfCount} PDF{pdfCount === 1 ? '' : 's'}. {nonPdfCount} other {nonPdfCount === 1 ? 'file' : 'files'} will be added directly.
                </p>
              )}
              <ConversionModeSelector
                conversionMode={conversionMode}
                setConversionMode={setConversionMode}
                capabilities={capabilities}
              />
              {nonPdfCount > 0 && (
                <FileTypeSummary files={stagedFiles.filter((s) => !s.file.name.toLowerCase().endsWith('.pdf'))} />
              )}
            </>
          )}
        </div>

        <button
          type="button"
          onClick={() => setShowTags((v) => !v)}
          className="mt-3 3xl:mt-4 flex items-center gap-1.5 3xl:gap-2 font-inter text-caption 3xl:text-[13px] 4xl:text-sm text-text-muted hover:text-text-primary"
        >
          <ChevronDown className={`h-3.5 w-3.5 3xl:h-4 3xl:w-4 transition-transform ${showTags ? 'rotate-180' : ''}`} />
          Optional tags
        </button>
        {showTags && (
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="e.g. legal, methodology"
            className="mt-2 3xl:mt-3 h-9 3xl:h-11 4xl:h-12 w-full rounded-lg 3xl:rounded-xl border border-border-ui bg-surface-card px-3 3xl:px-4 font-inter text-body-sm 3xl:text-[15px] 4xl:text-base text-text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
          />
        )}

        {isUploading && (
          <div className="mt-4 3xl:mt-6">
            <div className="flex items-center justify-between text-caption 3xl:text-[13px] 4xl:text-sm font-inter mb-1.5 3xl:mb-2">
              <span className="text-text-secondary">Building knowledge base</span>
              <span className="text-text-primary font-medium">{Math.round((uploadProgress.done / uploadProgress.total) * 100)}%</span>
            </div>
            <div className="h-2 3xl:h-2.5 4xl:h-3 w-full rounded-full bg-surface-subtle overflow-hidden">
              <div
                className="h-full rounded-full bg-brand-500 transition-all duration-300"
                style={{ width: `${uploadProgress.total ? (uploadProgress.done / uploadProgress.total) * 100 : 0}%` }}
              />
            </div>
          </div>
        )}

        <button
          type="button"
          disabled={uploadDisabled}
          onClick={handleIngest}
          className="mt-4 3xl:mt-6 w-full h-10 3xl:h-12 4xl:h-14 rounded-lg 3xl:rounded-xl bg-brand-700 px-4 3xl:px-6 font-inter text-body-sm 3xl:text-[15px] 4xl:text-base font-semibold text-white transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {buttonLabel}
        </button>
      </div>
    </section>
  );
};


