CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
    password_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_single_owner ON users(role) WHERE role = 'owner';
INSERT OR IGNORE INTO users (id, username, role) VALUES ('owner', 'owner', 'owner');

DROP TABLE IF EXISTS auth_sessions;
CREATE TABLE auth_sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_fingerprint TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_auth_sessions_user_id ON auth_sessions(user_id);

DROP TABLE IF EXISTS async_query_jobs;
CREATE TABLE async_query_jobs (
    job_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
CREATE INDEX idx_async_query_jobs_status ON async_query_jobs(status);
CREATE INDEX idx_async_query_jobs_expires_at ON async_query_jobs(expires_at);
CREATE INDEX idx_async_query_jobs_client_request_id ON async_query_jobs(client_request_id);

CREATE TABLE IF NOT EXISTS chats (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chats_user_updated ON chats(user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS chat_turns (
    chat_id TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    message_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    user_text TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chat_id, message_id),
    UNIQUE (chat_id, seq)
);
