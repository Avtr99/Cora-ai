-- Add category column to document_store_documents.
-- Non-registry document classifications (Market Intelligence, VCM Policy,
-- ICVCM, SBTi, etc.) are stored here instead of in the registry column, so
-- the registry field only contains real credit-issuing registries (Verra,
-- Gold Standard, CDM, etc.).
--
-- The migration runner skips ADD COLUMN statements for columns that already
-- exist, so this remains safe even if another code path created the table
-- schema before migrations ran.

ALTER TABLE document_store_documents ADD COLUMN category TEXT;
