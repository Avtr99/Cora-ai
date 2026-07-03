-- App settings table for user-configurable options (LLM provider, etc.)
-- This table stores key-value pairs for application-level settings that
-- persist across restarts. API keys are stored here but never exposed via
-- the GET settings endpoint (only a boolean has_api_key is returned).

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- LLM provider configuration keys (managed by llm_factory.py):
-- llm_provider       : "gemini" | "openai_compatible"
-- llm_api_key        : API key (stored locally, never returned by GET endpoint)
-- llm_base_url       : Base URL for OpenAI-compatible providers
-- llm_model_main     : Primary model name for answer generation
-- llm_model_lite     : Lite model name for low-latency tasks (optional)
-- llm_organization   : OpenAI organization ID (optional)
