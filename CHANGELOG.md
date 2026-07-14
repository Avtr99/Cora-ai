# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 1.0.1 (2026-07-14)


### Bug Fixes

* clean up review findings and enable GitHub release ([6aca83c](https://github.com/Avtr99/Cora-ai/commit/6aca83c21976ab82e70bf7760075492659aa41f1))

## [Unreleased]

## [1.0.0] - 2026-07-14

### Added

- Open-source release of Cora AI, a local-first RAG assistant for the Voluntary Carbon Market.
- Multi-route RAG orchestrator (knowledge base, web search, hybrid, conversational).
- Pluggable providers for LLM, embeddings, reranker, and web search.
- Document ingestion with local Docling pipeline or optional LLM API conversion.
- Streaming and async query endpoints.
- Conversation memory with HMAC-hashed user IDs.
- Citation extraction and HTML sanitization for provenance.
- Docker Compose setup for local deployment.
- Document `category` metadata for non-registry classifications (VCM Policy, ICVCM, Market Intelligence, etc.) alongside `registry` for credit-issuing registries.
- Curated VCM citation metadata surfaced in API responses (`registry`, `category`, `document_id`, `version_number`, `publisher`).
- Registry pattern configuration split into focused modules (`_registries`, `_governance`, `_categories`) with `is_registry` flag.
- Image placeholder stripping (`<!-- image -->`) in standard Docling conversions to reduce garbage chunks.
- `frontend/.release-it.json` — release-it configuration for automated versioning and changelog generation.
- New legal and governance docs: `docs/AI_SYSTEM_CARD.md`, `docs/ATTRIBUTION.md`, `docs/PRIVACY.md`, and `docs/TERMS.md`.
- New ingestion helpers: `src/document_store/ingestion_pool.py` and `src/document_store/logging_utils.py` for staged ingestion and structured timing logs.
- `scripts/generate_satellite_images.py` for case-study satellite imagery generation.
- Expanded test coverage for answer relevance (`tests/test_relevance_check.py`) and document-store ingestion edge cases (`tests/test_document_store.py`).

### Infrastructure

- Added GitHub Actions CI workflow for Python lint/tests, frontend lint/build, and Docker build.
- Added OpenSSF Scorecard workflow and README badge.
- Added `SECURITY.md` and `CODE_OF_CONDUCT.md`.
- Added GitHub issue templates and pull request template.
- Added README badges for license, CI, Scorecard, Python, Docker, and SDG alignment.
- Fixed `.gitignore` so `frontend/src/data/` is tracked and the frontend/Docker build works in CI.
- Removed `ruff-format` from pre-commit hooks; CI still runs `ruff` lint checks and `gitleaks` secret scanning.
- Excluded `scripts/evaluation/` from pre-commit ruff linting; these are dev-only scripts not required in CI.
- Hardened CI workflow: pinned all GitHub Actions to SHA commits, set least-privilege permissions, added job timeouts, disabled persisted checkout credentials, and made Docker build depend on earlier validation jobs.
- Changed test step from `pytest -m unit` to `pytest` since no tests currently use the `unit` marker.

### Security

- Added `.github/dependabot.yml` with security-only update strategy for pip, npm, github-actions, and docker ecosystems. Dependabot security updates stay active; routine version-bump PRs are disabled to reduce noise. Detected by Scorecard's Dependency-Update-Tool check.
- Added `.github/CODEOWNERS` mapping all paths to `@Avtr99` with explicit security-sensitive path entries. Prerequisite for branch protection ruleset (Code-Review and Branch-Protection checks).
- Pinned Dockerfile base images by SHA256 digest (`node:22-alpine`, `python:3.11-slim`) for supply-chain integrity. Digest updates are manual (Dependabot version-update PRs are disabled; security updates still open PRs for vulnerable base images).
- Generated hash-pinned lockfiles via `uv pip compile --generate-hashes` targeting `x86_64-unknown-linux-gnu`/Python 3.11: `requirements-core.lock`, `requirements-ingestion.lock` (CPU torch via PyTorch index), `requirements-ci.lock` (core + ingestion + dev). Dockerfile and CI now install with `pip install --require-hashes` for verified reproducible builds.
- Added OpenSSF Baseline Best Practices badge to README (project 13501 on bestpractices.dev). Detected by Scorecard's CII-Best-Practices check.
- CI workflow runs on both `pull_request` and `push` to main (defense-in-depth for direct pushes / admin bypass). The push trigger will become redundant once branch protection requires PRs (Phase 2). SAST (CodeQL) runs independently via GitHub built-in scanning and is unaffected.
- Added `npm audit --audit-level=high` to the frontend CI job to catch high/critical npm vulnerabilities in pull requests.
- Enforced minimum 32-byte `JWT_SECRET_KEY` length in `src/api/auth/token_utils.py` before creating or decoding HS256 tokens.
- Added targeted security tests for JWT token handling (`tests/test_token_utils.py`) and API key middleware/security headers (`tests/test_security_middleware.py`).
- Made document-store `ALTER TABLE ... ADD COLUMN` migrations idempotent in `src/db/database.py` so existing schemas created by `ensure_document_store_tables()` no longer cause migration failures on startup.

### Fixed

- Fixed metadata extraction registry/category tie-break to use `pattern.is_registry` instead of `id_patterns` presence, ensuring real registries win over non-registry patterns with ID patterns.
- Fixed historical data inconsistency in `document_store_documents` table: added migration `006_document_category_backfill.sql` to move pre-split non-registry names (governance bodies, topic classifiers) from `registry` to `category`, and added indexes on both columns for performance on large document stores.
- Fixed `MetadataExtractor.extract()` docstring to match actual return contract: corrected `version` → `version_number`, removed `title` (extracted separately in `title_utils`), and added `publisher`.
- Fixed payload index field duplication in `indexer.py`: refactored `_ensure_collection()` to iterate over the existing `_PAYLOAD_INDEX_FIELDS` constant instead of hardcoding a duplicate tuple, eliminating drift risk.
- Fixed overly generic content markers in registry/category patterns to reduce false positives:
  - Removed standalone `"trees"` from `REDD+ / NBS` category (ART/TREES registry documents are covered by the dedicated `ART` pattern).
  - Removed `"scope 1"`, `"scope 2"`, `"scope 3"` from `GHG Protocol` (these terms appear across SBTi, CDP, VCMI, and corporate disclosures).
  - Removed `"environmental registry"` from `Verra` (not Verra-specific; OxCarbon also issues on the S&P Global Environmental Registry).
- Fixed CI/Docker torch binary mismatch: regenerated `requirements-ci.lock` with `--index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cpu` so CI pins `torch==2.12.1+cpu` / `torchvision==0.27.1+cpu`, matching the Docker image. CI install command updated to pass the PyTorch CPU index.
- Fixed import ordering in `scripts/docker/download_docling_models.py` (moved `Path` usage after docling imports).
- Resolved merge conflict in `.pre-commit-config.yaml` — kept `scripts/evaluation/` exclusion (production scripts under `scripts/docker/` are still linted).
- Restored working tree to `origin/main` baseline while preserving new work: kept monolithic `src/config.py`, async SQLite cache singleton, and main's lifespan/orchestrator initialization; removed unused config-split mixins and dead `_MIN_CHUNK_CHARS` constant.
- Expanded `.gitignore` with frontend test/coverage and cache patterns.
- Removed duplicate `QDRANT_ALLOWED_FILTER_FIELDS` definition in `src/config.py`; the single remaining definition is used by the retrieval filter-field validator and schema discovery.

### Changed

- Refined ingestion pipeline in `src/document_store/indexer.py` with debounced cache invalidation and a shared `QdrantVectorStore` singleton to reduce connection churn during bulk indexing.
- `src/document_store/jobs.py` now emits per-stage ingestion timing logs and recovers documents/jobs left in-flight at startup.
- Post-generation relevance validation in `src/agents/validator.py` now receives source document titles and retrieved source chunks for stronger grounding checks.
- `src/agents/route_processor_utils.py` extracts, deduplicates, and cleans source display names (including percent-decoded filenames).
- Streaming handler (`src/agents/streaming_handler.py`) supports token-suppressed mode with retrieval-aware relevance validation and explicit non-answer fallback logic.
- Query rewriter (`src/agents/query_rewriter.py`) preserves exact VCM methodology identifiers and improves acronym/registry filter extraction.
- Tavily search provider (`src/agents/tavily_search.py`) strips common web-search prefix markers (`[PDF]`, `[DOC]`, `[web]`) from result titles.
- Fusion retrieval (`src/agents/fusion_retrieval.py`) relaxes secondary filters and falls back to unfiltered search when strict filter combinations return no results.
- Expanded frontend case-study experience: new satellite imagery, SDG alignment (`frontend/src/lib/sdg.ts`), `BeforeAfterSlider` component, and refreshed `CaseStudyPage`, `CaseStudiesPage`, `ProjectDetails`, and `CaseStudyStrengths`.
- Updated README, NOTICE, ARCHITECTURE, ROADMAP, and `documentation.md` to reflect chat readiness, settings status, and V1 capabilities.

### Removed

- `tests/test_rag_evaluation.py` one-time RAGAS/evaluation pytest harness removed (RAGAS evaluation remains available via `scripts/evaluation/evaluate_rag.py`).
- `scripts/evaluation/run_full_evaluation.py` deprecated evaluation runner removed.
- Cleaned up one-off untracked test files: `test_cache_invalidation_debounce.py`, `test_indexer_vector_store_singleton.py`, `test_ingestion_timing_logs.py`, and `test_tavily_search.py`.
- Removed stale `__pycache__` artifacts from previously deleted test files.
- Removed outdated Humbo and Mangrove frontend image assets in favor of optimized case-study imagery.
