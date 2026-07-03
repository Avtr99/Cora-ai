export type DocumentStatus =
  | 'queued'
  | 'reading'
  | 'converting'
  | 'indexing'
  | 'indexed'
  | 'needs_review'
  | 'failed'
  | 'deleting'
  | 'deleted';

export type ConversionMode = 'standard' | 'llm_api';

export interface ConversionModeInfo {
  available: boolean;
  model?: string | null;
  provider?: string | null;
  cost_per_page: string;
  privacy: 'local' | 'external';
  speed: 'fast' | 'medium' | 'slow' | 'very_slow';
  experimental: boolean;
  conversion_prompt?: string;
}

export interface ConversionCapabilities {
  standard: ConversionModeInfo;
  llm_api: ConversionModeInfo;
  upload_limits?: {
    allowed_extensions: string[];
    max_bytes: number;
  };
}

// Static, always-true facts about each mode. Used as fallbacks so the selector
// shows meaningful cost/speed/privacy even before capabilities load from the
// backend (or when it's unreachable). The server can refine `cost` (e.g. the
// exact per-page estimate) when capabilities are available.
export const CONVERSION_OPTIONS: Array<{
  value: ConversionMode;
  label: string;
  description: string;
  defaults: { cost: string; speed: 'fast' | 'medium' | 'slow' | 'very_slow'; privacy: 'local' | 'external' };
}> = [
  {
    value: 'standard',
    label: 'Standard',
    description: 'Free, runs on your CPU. Best for most VCM documents. Reads text, headings, and tables directly from the PDF. Handles scanned pages with built-in OCR. About 1 to 2 seconds per page. For documents with complex layouts, math formulas, charts, or images, consider LLM API mode for better accuracy.',
    defaults: { cost: 'Free', speed: 'slow', privacy: 'local' },
  },
  {
    value: 'llm_api',
    label: 'LLM API',
    description: 'Higher accuracy for complex documents. Best for PDFs with mathematical formulas, charts, images, or tricky layouts that Standard mode may not capture well. Uses your configured AI provider (Gemini or OpenAI). Requires a paid API key. About $0.002 per page.',
    defaults: { cost: '~$0.002 / page', speed: 'medium', privacy: 'external' },
  },
];

export interface DocumentStoreRecord {
  id: string;
  original_filename: string;
  mime_type: string;
  extension: string;
  size_bytes: number;
  sha256: string;
  status: DocumentStatus;
  conversion_mode: ConversionMode;
  original_path: string;
  converted_path?: string | null;
  chunk_count: number;
  page_count?: number | null;
  tags: string[];
  warnings: string[];
  error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface DocumentListResponse {
  documents: DocumentStoreRecord[];
}

interface DocumentUploadResponse {
  document: DocumentStoreRecord;
  job_id: string;
}

interface MarkdownResponse {
  document_id: string;
  markdown: string;
}

const DOCUMENTS_ENDPOINT = '/api/documents';

export const DOCUMENT_UPLOAD_MAX_BYTES = 50 * 1024 * 1024;

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === 'string') return payload.detail;
    if (typeof payload?.message === 'string') return payload.message;
  } catch {
    const text = await response.text().catch(() => '');
    if (text) return text;
  }
  if (response.status === 404) return 'Document store endpoint not found. The backend may be missing document store routes or not running.';
  if (response.status >= 500) return 'Backend error. Check the server logs.';
  return `Request failed with status ${response.status}`;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  return response.json() as Promise<T>;
}

export async function fetchDocuments(filters: { status?: string; extension?: string; tag?: string } = {}): Promise<DocumentStoreRecord[]> {
  const params = new URLSearchParams();
  if (filters.status) params.set('status', filters.status);
  if (filters.extension) params.set('extension', filters.extension);
  if (filters.tag) params.set('tag', filters.tag);
  const query = params.toString();
  const data = await requestJson<DocumentListResponse>(`${DOCUMENTS_ENDPOINT}${query ? `?${query}` : ''}`);
  return data.documents;
}

export async function uploadDocument(file: File, conversionMode: ConversionMode, tags: string[]): Promise<DocumentUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('conversion_mode', conversionMode);
  formData.append('tags', JSON.stringify(tags));
  return requestJson<DocumentUploadResponse>(DOCUMENTS_ENDPOINT, {
    method: 'POST',
    body: formData,
  });
}

export type DocumentUploadBatchResult =
  | { ok: true; file: File; response: DocumentUploadResponse }
  | { ok: false; file: File; error: string };

// ponytail: cap concurrent uploads to avoid thundering-herd on the server's
// BackgroundTasks threadpool. 4 keeps the UI responsive without opening a
// connection per file. Ceiling: large batches still serialize through this
// pool; raise UPLOAD_CONCURRENCY if the backend grows a real queue.
const UPLOAD_CONCURRENCY = 4;

export async function uploadDocumentsBatch(
  files: File[],
  conversionMode: ConversionMode,
  tags: string[],
  onProgress?: (completed: number) => void,
): Promise<DocumentUploadBatchResult[]> {
  const results: DocumentUploadBatchResult[] = new Array(files.length);
  let completed = 0;
  let cursor = 0;

  async function worker() {
    while (cursor < files.length) {
      const index = cursor;
      cursor += 1;
      const file = files[index];
      try {
        const response = await uploadDocument(file, conversionMode, tags);
        results[index] = { ok: true, file, response };
      } catch (err) {
        results[index] = {
          ok: false,
          file,
          error: err instanceof Error ? err.message : 'Failed to add document.',
        };
      }
      completed += 1;
      onProgress?.(completed);
    }
  }

  const workerCount = Math.min(UPLOAD_CONCURRENCY, files.length);
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  return results;
}

export async function fetchDocumentMarkdown(documentId: string): Promise<string> {
  const data = await requestJson<MarkdownResponse>(`${DOCUMENTS_ENDPOINT}/${encodeURIComponent(documentId)}/markdown`);
  return data.markdown;
}

export async function reindexDocument(documentId: string): Promise<DocumentUploadResponse> {
  return requestJson<DocumentUploadResponse>(`${DOCUMENTS_ENDPOINT}/${encodeURIComponent(documentId)}/reindex`, {
    method: 'POST',
  });
}

export async function deleteDocument(documentId: string): Promise<DocumentUploadResponse> {
  return requestJson<DocumentUploadResponse>(`${DOCUMENTS_ENDPOINT}/${encodeURIComponent(documentId)}`, {
    method: 'DELETE',
  });
}

export async function markDocumentReviewed(documentId: string): Promise<DocumentStoreRecord> {
  return requestJson<DocumentStoreRecord>(`${DOCUMENTS_ENDPOINT}/${encodeURIComponent(documentId)}/review`, {
    method: 'POST',
  });
}

interface BulkActionResponse {
  queued: number;
  job_ids: string[];
}

export async function reindexAllDocuments(): Promise<BulkActionResponse> {
  return requestJson<BulkActionResponse>(`${DOCUMENTS_ENDPOINT}/reindex-all`, {
    method: 'POST',
  });
}

export async function clearAllDocuments(): Promise<BulkActionResponse> {
  return requestJson<BulkActionResponse>(DOCUMENTS_ENDPOINT, {
    method: 'DELETE',
  });
}

export async function fetchConversionCapabilities(): Promise<ConversionCapabilities> {
  return requestJson<ConversionCapabilities>(`${DOCUMENTS_ENDPOINT}/conversion-info`);
}
