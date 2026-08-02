-- Track which job currently owns a document so no two workers (or two
-- in-process BackgroundTasks) can process/reindex/delete the same document
-- concurrently.

ALTER TABLE document_store_documents ADD COLUMN processing_job_id TEXT;

CREATE INDEX IF NOT EXISTS idx_document_store_documents_processing_job_id
    ON document_store_documents(processing_job_id);
