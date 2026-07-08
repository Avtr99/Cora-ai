-- Backfill the category column for documents that were classified before the
-- registry/category split. Older rows may store governance bodies and topic
-- classifiers in the registry column; move those names to category so the
-- registry column only contains real credit-issuing registries.
--
-- Only touch rows where category is NULL and registry matches a known
-- non-registry pattern name. Real registries and already-normalized rows are
-- left untouched.

-- Indexes keep the backfill fast on large document stores. They are also
-- useful for future queries that filter on registry/category.
CREATE INDEX IF NOT EXISTS idx_document_store_documents_registry ON document_store_documents(registry);
CREATE INDEX IF NOT EXISTS idx_document_store_documents_category ON document_store_documents(category);

UPDATE document_store_documents
SET category = registry,
    registry = NULL
WHERE category IS NULL
  AND registry IN (
    -- Governance / standard bodies
    'ICVCM',
    'SBTi',
    'CORSIA',
    'VCMI',
    'GHG Protocol',
    'CDP',
    'ICROA',
    -- Topic category classifiers
    'VCM Policy',
    'Market Intelligence',
    'REDD+ / NBS',
    'Blue Carbon',
    'Methodology Concepts',
    'Project Development',
    'SD VISta / SDGs',
    'CDR / Removals',
    'Cookstoves / Energy',
    'Quality Assessments',
    'Compliance Markets',
    'Agriculture / Soil Carbon',
    'Industrial / Waste',
    'Transportation / Fuels'
  );
