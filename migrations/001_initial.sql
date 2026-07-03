CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    conversation_id TEXT,
    message_id TEXT,
    rating TEXT NOT NULL,
    comment TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT
);

CREATE TABLE IF NOT EXISTS backend_cache (
    hash_key TEXT NOT NULL,
    handler_type TEXT NOT NULL,
    cached_data TEXT NOT NULL, -- Stored as JSON string
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (hash_key, handler_type)
);

CREATE INDEX IF NOT EXISTS idx_backend_cache_expires_at ON backend_cache(expires_at);

-- Embedding cache: durable across container restarts on the persistent volume.
-- Replaces the previous GCS-based embedding cache (cloud-only, removed).
CREATE TABLE IF NOT EXISTS embedding_cache (
    text_hash TEXT PRIMARY KEY,          -- sha256(text)
    embedding TEXT NOT NULL,             -- JSON-serialized vector
    model TEXT NOT NULL,                 -- e.g. "voyage-4-lite"
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_embedding_cache_model ON embedding_cache(model);