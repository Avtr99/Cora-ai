-- Persist async query job state to SQLite so queued and in-flight jobs survive restarts.

CREATE TABLE IF NOT EXISTS async_query_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    payload TEXT NOT NULL,
    result TEXT,
    error TEXT,
    expires_at REAL,
    client_request_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_async_query_jobs_status ON async_query_jobs(status);
CREATE INDEX IF NOT EXISTS idx_async_query_jobs_expires_at ON async_query_jobs(expires_at);
CREATE INDEX IF NOT EXISTS idx_async_query_jobs_client_request_id ON async_query_jobs(client_request_id);
