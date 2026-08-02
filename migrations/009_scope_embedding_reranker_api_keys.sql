-- Scope embedding/reranker API keys per subsystem (P0 shared-key fix).
--
-- Before this migration, the embeddings and reranker routes both wrote to the
-- same voyage_api_key / cohere_api_key / openai_api_key rows in app_settings.
-- The last writer won, silently overwriting the other subsystem's key. This
-- migration is the data side of the fix: it copies the legacy shared values
-- into the new per-subsystem scoped keys (embedding_* / reranker_*) so no
-- operator loses their key on upgrade. The code side (routes write scoped
-- keys only) is in the accompanying application changes.
--
-- Idempotent: each copy uses WHERE NOT EXISTS on the scoped key, so re-running
-- the migration (or running it after the operator already saved a scoped key
-- via the UI) never overwrites a scoped value with the legacy shared one.
--
-- The legacy shared rows (voyage_api_key, cohere_api_key, openai_api_key) are
-- intentionally NOT deleted here. They remain as .env-only fallbacks read by
-- the LLM env-detection path (llm_factory.py / llm_profile_manager.py) and by
-- the embeddings/reranker factories as a fallback when no scoped key is set.
-- Deleting them would break operators who rely on VOYAGE_API_KEY in .env and
-- never used the Settings UI.

-- Voyage: copy the shared key into both the embedding- and reranker-scoped keys.
INSERT INTO app_settings (key, value, updated_at)
SELECT 'embedding_voyage_api_key', value, CURRENT_TIMESTAMP
FROM app_settings
WHERE key = 'voyage_api_key'
  AND NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'embedding_voyage_api_key');

INSERT INTO app_settings (key, value, updated_at)
SELECT 'reranker_voyage_api_key', value, CURRENT_TIMESTAMP
FROM app_settings
WHERE key = 'voyage_api_key'
  AND NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'reranker_voyage_api_key');

-- Cohere: same pattern.
INSERT INTO app_settings (key, value, updated_at)
SELECT 'embedding_cohere_api_key', value, CURRENT_TIMESTAMP
FROM app_settings
WHERE key = 'cohere_api_key'
  AND NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'embedding_cohere_api_key');

INSERT INTO app_settings (key, value, updated_at)
SELECT 'reranker_cohere_api_key', value, CURRENT_TIMESTAMP
FROM app_settings
WHERE key = 'cohere_api_key'
  AND NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'reranker_cohere_api_key');

-- OpenAI: embeddings-only (the reranker has no OpenAI provider). The LLM
-- subsystem reads OPENAI_API_KEY from .env directly (env detection), so the
-- scoped key here is for the embeddings factory's fallback only.
INSERT INTO app_settings (key, value, updated_at)
SELECT 'embedding_openai_api_key', value, CURRENT_TIMESTAMP
FROM app_settings
WHERE key = 'openai_api_key'
  AND NOT EXISTS (SELECT 1 FROM app_settings WHERE key = 'embedding_openai_api_key');
