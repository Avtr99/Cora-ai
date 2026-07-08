-- Add category column to document_store_documents.
-- Non-registry document classifications (Market Intelligence, VCM Policy,
-- ICVCM, SBTi, etc.) are stored here instead of in the registry column, so
-- the registry field only contains real credit-issuing registries (Verra,
-- Gold Standard, CDM, etc.).
--
-- Migrations are tracked in schema_migrations and only run once, so plain
-- ALTER TABLE is safe (no IF NOT EXISTS needed).

ALTER TABLE document_store_documents ADD COLUMN category TEXT;
