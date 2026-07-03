CREATE TABLE IF NOT EXISTS document_store_documents (
    id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    extension TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL,
    conversion_mode TEXT NOT NULL,
    original_path TEXT NOT NULL,
    converted_path TEXT,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    page_count INTEGER,
    tags_json TEXT NOT NULL DEFAULT '[]',
    warnings_json TEXT NOT NULL DEFAULT '[]',
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_document_store_documents_status ON document_store_documents(status);
CREATE INDEX IF NOT EXISTS idx_document_store_documents_extension ON document_store_documents(extension);
CREATE INDEX IF NOT EXISTS idx_document_store_documents_created_at ON document_store_documents(created_at);

CREATE TABLE IF NOT EXISTS document_store_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    message TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES document_store_documents(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_document_store_jobs_document_id ON document_store_jobs(document_id);
CREATE INDEX IF NOT EXISTS idx_document_store_jobs_status ON document_store_jobs(status);
