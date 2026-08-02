# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Bug Fixes

* **citations:** fix source names showing filenames instead of document titles — the citation extractor's fallback chain was missing `title` and `original_filename`, so it fell through to `source` (the raw filename). Now uses `title → file_name → original_filename → parent_doc → source` consistently across all 6 consumers (`extractor.py`, `base_rag_client.py`, `summarize_service.py`, `result_processor.py` ×2, `source_type.py`)
* **citations:** fix `A/R` (Afforestation/Reforestation) being treated as a path separator in `clean_source_name` — domain slashes in document titles like "ACM0003: A/R Large-scale Consolidated Methodology v02.0" are now preserved
* **citations:** fix explicitly-cited sources being dropped by the citation filter — `[cite_kb: N]` / `[cite_web: N]` markers in the answer now force-retain the referenced source even when snippet/name overlap heuristics would reject it
* **citations:** extract shared marker-parsing utility to `src/citations/markers.py` — eliminates 3 copies of the citation marker regex and 2 different index-mapping conventions between the filter and the renumberer, preventing dangling `[cite_kb: N]` references on duplicate source names

## [1.1.2](https://github.com/Avtr99/Cora-ai/compare/v1.1.1...v1.1.2) (2026-07-30)


### Bug Fixes

* **security:** update vulnerable Python dependencies in lockfiles ([b156773](https://github.com/Avtr99/Cora-ai/commit/b156773)). Fixes pyasn1 (0.6.3→0.6.4), torch (2.12.1→2.13.0), torchvision (0.27.1→0.28.0), setuptools (81.0.0→83.0.0), filelock (3.29.5→3.32.2), aiohttp (3.14.1→3.14.3)
* **security:** revert react-router-dom to 6.x to fix GHSA-qwww-vcr4-c8h2 ([fd3de6b](https://github.com/Avtr99/Cora-ai/commit/fd3de6b)). The bump to 7.18.2 introduced the vulnerability; 6.x is not affected
* **security:** add osv-scanner.toml to document false positives and non-exploitable vulnerabilities for OSSF scorecard

## [1.1.1](https://github.com/Avtr99/Cora-ai/compare/v1.1.0...v1.1.1) (2026-07-30)


### Bug Fixes

* **release:** move release tooling to repo root and sync backend version ([8fb5f05](https://github.com/Avtr99/Cora-ai/commit/8fb5f05308caf724f1586ca5aa53de0713b65745))
* **release:** stage parent-dir CHANGELOG into the release commit ([96b56db](https://github.com/Avtr99/Cora-ai/commit/96b56dbd376c9e23627598836adaa286b8d10f6a))

# [1.1.0](https://github.com/Avtr99/Cora-ai/compare/v1.0.3...v1.1.0) (2026-07-30)


### Bug Fixes

* **chat:** exclude interactive elements from composer focus capture and track scroll correction rAF ([d63bab6](https://github.com/Avtr99/Cora-ai/commit/d63bab6aa4fb71dc5a4bd1259781c21f9914f13c))


### Features

* **chat:** add floating scroll button and composer focus helpers; fix case study responsive layout ([78f7508](https://github.com/Avtr99/Cora-ai/commit/78f75084ac4085b323483aa8ee5ed2ea841d1bb0))
* **chat:** sign and verify conversation history across turns ([ea6ca2e](https://github.com/Avtr99/Cora-ai/commit/ea6ca2eda74eae65ad7908472f13145485e224b1))

## [1.0.3](https://github.com/Avtr99/Cora-ai/compare/v1.0.2...v1.0.3) (2026-07-14)

## [1.0.2](https://github.com/Avtr99/Cora-ai/compare/v1.0.1...v1.0.2) (2026-07-14)

## 1.0.1 (2026-07-14)


### Bug Fixes

* clean up review findings and enable GitHub release ([6aca83c](https://github.com/Avtr99/Cora-ai/commit/6aca83c21976ab82e70bf7760075492659aa41f1))

## [Unreleased]

### Added

- **LLM config discriminated union.** `src/query_processing/llm_config_models.py` defines a Pydantic discriminated union (`GeminiConfig` | `OpenAICompatibleConfig`) that makes structurally impossible provider configs unrepresentable at the type level. `GeminiConfig` has no `base_url`/`organization` fields, so a Gemini config can never carry an OpenRouter URL. Field validators on `api_key` clear wrong-provider keys (e.g. an `sk-or-` key under Gemini). The union is the `PUT /v1/settings/llm` request body type (FastAPI returns 422 for unknown providers) and validates every DB read and profile write via `validate_llm_config()`. `get_llm_settings()` still returns a dict (no caller changes). Old corrupt DB records are handled via `extra="ignore"` — no migration needed.
- **Split ingestion worker stack.** Docker Compose now runs a query-only `app` container (no Docling/torch/RapidOCR, ~700MB smaller) plus a separate `ingest-worker` container that runs the heavy PDF/OCR parsing. `INGESTION_DISPATCH` (`in_process` | `worker`) selects whether ingestion runs as a FastAPI `BackgroundTask` in the API process or is queued in SQLite for the worker. The worker (`python -m src.document_store.worker`) polls the job table with atomic `claim_next_job()` (conditional `UPDATE ... WHERE status = 'queued'`), supports horizontal scaling (`docker compose up --scale ingest-worker=2`), and recovers `processing` jobs as `failed` on restart while preserving `queued` jobs. New modules: `src/document_store/{dispatch,worker,jobs_repo,recovery,handlers,uploads,files,errors,schema,repository,docling_warmup}.py`. New doc: `docs/SCALING_INGESTION.md`.
- **Query cache key now folds model + corpus + config revisions.** Previously the cache key was `sha256(query)` only, so a cached answer could be served stale after a document reingestion or after the embedding/reranker/LLM model was swapped via the Settings UI. The key now includes `config_revision` (bumped on any embedding/reranker/LLM model change), `corpus_revision` (bumped once per ingestion batch), `config_version` (bumped on every `reload_settings()` call), and the embedding/reranker model fingerprint. New module `src/db/revisions.py` provides atomic UPSERT bump counters persisted in the `app_settings` table. `invalidate_query_cache_for_config_change()` is called by every settings route after a model-affecting save. `GET /v1/settings/status` exposes the three counters and `config_version_updated_at` for debugging. `config_version` is also stamped onto every query response (`Response.config_version`, `QueryMetadataResponse.config_version`) as an observability aid.
- **Idempotent async query jobs.** `POST /v1/query/async` now accepts an optional `client_request_id` (idempotency key, max 128 chars). Re-submitting the same key returns the existing in-flight or completed job instead of creating a duplicate. The async job queue is now SQLite-backed (`src/db/async_query_jobs.py`, migration `007_async_query_jobs.sql`) so queued and in-flight jobs survive restarts and can be resumed. New migration `008_document_processing_job.sql` adds the document processing job table for the worker dispatch path.
- **Reasoning model support in OpenAI-compatible client.** `src/query_processing/openai_client.py` now detects GPT-5.x / o1 / o3 / o4 series models and routes them through `max_completion_tokens` instead of `max_tokens`, and omits `temperature` / `top_p` for models that reject those parameters. `_is_valid_model()` and `_resolve_model()` provide safer model-name fallbacks.
- **Provider toggle refresh after settings save.** `ProviderToggle` now fetches available providers via `react-query` and invalidates the `['llm', 'providers']` query key after a switch, so model names stay in sync. `SettingsDialog` skips the model-main reset on the initial settings load (via `skipModelResetRef`) so the user's configured model isn't replaced with the preset default.
- **Worker heartbeat and upload warnings.** `GET /v1/documents/capabilities` now returns a `worker_status` object (`dispatch_mode`, `alive`). The frontend warns before uploading when `INGESTION_DISPATCH=worker` and no ingest-worker heartbeat is detected. The API also logs a startup warning in the same condition.
- **Config version on responses.** `process_query_core` and `process_query_core_stream` capture `config_version` at request start and stamp it onto the top-level response and metadata. Folding `config_version` into the cache key ensures cached responses do not report a stale version.
- New tests: `tests/test_config.py` (config validation), `tests/test_llm_client.py` (LLM client behavior), expanded `tests/test_async_query_jobs.py` and `tests/test_document_store.py`.

### Changed

- **LLM settings routes refactored.** The 550-line `src/api/settings_routes/llm.py` is now a 21-line `APIRouter` aggregator. New focused modules: `llm_config.py` (GET/PUT `/llm`), `llm_profiles.py` (POST `/llm/switch`, GET `/llm/providers`), `llm_ollama.py` (GET `/llm/models`), `llm_test.py` (POST `/llm/test`), `llm_service.py` (shared write/validate helpers), `helpers.py` (shared request models). Shared profile logic moved to `src/db/llm_profile_manager.py` (`detect_env_providers`, `build_available_providers`, `resolve_profile_for_switch`, `resolve_default_models`). `resolve_profile_for_switch` now calls `detect_env_providers` once instead of twice.
- **LLM config validation moved to types.** `sanitize_llm_settings()` and `_api_key_matches_provider()` deleted — replaced by the Pydantic discriminated union's field validators and `extra="ignore"`. `LLMSettingsUpdate` class deleted — replaced by `LLMConfig` union as the `PUT /llm` request body. Dead code `save_llm_settings()` and `_write_settings_to_db()` deleted — they bypassed validation entirely. Invalid provider now returns 422 (FastAPI parse-time rejection) instead of 400 (manual runtime check). `_write_llm_settings` and `get_llm_settings` validate through `validate_llm_config()` before persisting/returning.
- **Document store decomposed.** `src/document_store/storage.py` (652 lines removed) and `jobs.py` (423 lines removed) split into focused modules: `repository.py` (document CRUD), `jobs_repo.py` (job records + atomic worker claiming), `schema.py` (table definitions), `uploads.py` (upload validation + save), `files.py` (filesystem helpers), `handlers.py` (conversion/reindex/delete handlers), `dispatch.py` (in_process vs worker dispatch), `recovery.py` (interrupted document recovery), `errors.py` (typed conversion errors), `docling_warmup.py` (lazy Docling model warmup). `src/api/document_store_routes.py` now calls `schedule_ingestion_job()` for every route instead of adding `BackgroundTask` directly.
- **Config schema cleanup.** `src/config.py` no longer holds `normalize_filter_field_name` (moved to new `src/config_validation.py`). Field validators and derived helpers are now co-located with the `Settings` schema. `src/config_store.py` `reload_settings()` now bumps `config_version` on every call.
- **SQLite DB moved to named volume.** `docker-compose.yml` mounts the SQLite DB on a named volume (`cora_db_data` → `/app/db`) instead of the `./data` bind mount. Windows Docker Desktop / WSL2 bind mounts do not support the POSIX locking SQLite needs for concurrent access from `app` + `ingest-worker`. `DATABASE_URL` updated to `sqlite:////app/db/cora.db`. `SQLITE_JOURNAL_MODE=WAL` is set for the named volume (the Linux VM filesystem supports it). Document files stay on the `./data` bind mount. `src/db/database.py` simplified to use the configured journal mode directly; runtime WAL/bind-mount detection removed.
- **CI builds both images.** The CI workflow now builds the `app` image (`INSTALL_INGESTION=false`) and the `ingest-worker` image (`INSTALL_INGESTION=true`) with separate GHA cache scopes. Job timeout raised from 20 to 30 minutes.
- **Conversational handler uses client lite model.** `src/agents/conversational_handler.py` now uses the configured client's lite model instead of hardcoding a Gemini model name, so OpenRouter/OpenAI providers don't receive a Gemini model string.
- **Documentation updated.** `documentation.md` now documents the cache revision system, split ingestion worker, LLM route refactor, and config validation module. `docs/ARCHITECTURE.md` updated with the split-process deployable architecture, named volume, and worker dispatch flow. `README.md` updated with the split stack, env var table, and scaling-ingestion link. `AGENTS.md` and `CLAUDE.md` updated with the split stack, `INGESTION_DISPATCH`, and named-volume guidance.

### Fixed

- **Reindex UI feedback.** Reindex of a `failed` document now shows immediate feedback (spinner + status transition) without requiring a manual page refresh. The frontend keeps polling the documents list after a reindex action until the worker picks up the job (doc enters an active status) or a 60s timeout expires (worker down). Previously, polling stopped before the worker transitioned the doc to `converting`, so the UI appeared frozen until a manual refresh. Same fix applied to "Reindex all" — the progress bar now stays visible while docs await worker pickup instead of disappearing instantly.
- **Citation source-name decoding.** Frontend `chatMessageCitations.utils.ts` now uses a byte-level `safePercentDecode()` so a single malformed `%` no longer aborts decoding of the rest of the label. Previously `decodeURIComponent` threw on a broken `%` sequence and left `%20` visible in source labels (e.g. `vm0048%20reducing%20emissio..`). Up to 8 decode passes handle double/triple encoding. UTF-16 surrogate pairs round-trip correctly.
- **Conversion capabilities in worker mode.** `get_conversion_capabilities()` now reports Standard conversion as available when `INGESTION_DISPATCH=worker`, even though the query-only `app` container does not install Docling. The worker container has the parser stack.
- **Worker recovery ownership.** In `worker`-dispatch mode the API skips `recover_interrupted_documents()` on startup — the worker owns all recovery (jobs, documents, stale locks). If the API marked in-flight documents as failed while the worker was actively processing them, the worker would later overwrite the status.
- **Reindex job no longer pre-sets `queued` status.** The document stays at its current status (e.g. `failed` or `indexed`) until the worker picks up the reindex job. Pre-setting `queued` would leave the document stuck if the worker crashed mid-job, and the doc would fall outside `_INTERRUPTED_STATUSES` and never be recovered.

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
