-- Add VCM metadata columns to document_store_documents.
-- These are extracted once during conversion and persisted, so the indexer
-- and RAG citation pipeline read from a single source of truth instead of
-- re-extracting on every use.
--
-- Migrations are tracked in schema_migrations and only run once, so plain
-- ALTER TABLE is safe (no IF NOT EXISTS needed).

ALTER TABLE document_store_documents ADD COLUMN title TEXT;
ALTER TABLE document_store_documents ADD COLUMN registry TEXT;
ALTER TABLE document_store_documents ADD COLUMN publisher TEXT;
ALTER TABLE document_store_documents ADD COLUMN document_id TEXT;
ALTER TABLE document_store_documents ADD COLUMN version_number TEXT;
