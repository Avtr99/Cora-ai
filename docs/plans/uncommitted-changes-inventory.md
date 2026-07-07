# Uncommitted Changes — Reset & Restore Log

> **Date**: 2026-07-06
> **Status**: Complete. Reset to `origin/main`, pure new work restored,
> refactoring re-applied, tests passing (390/390).
>
> **Purpose**: Documents what happened, what was kept, what was discarded,
> and the final state of the working tree after the reset-and-restore operation.

## What happened

The working tree had drifted from `origin/main` in two ways:

1. **Git history rewrite** — A `git filter-branch` + interactive rebase was run
   earlier to remove Devin as a co-author from commit messages. This rewrote
   commit hashes, creating divergent histories. A subsequent `git pull` created
   merge commit `7eab961` to reconcile (content-neutral — zero file changes).

2. **Working tree reverted to pre-Devin state** — Many files in the working tree
   were byte-identical to the first commit (`ae0a2b2`), missing all fixes that
   Devin/main had committed. This affected 10 files (pure reversions) and 14
   files (mixed — our new work intertwined with missing main fixes).

The fix: back up all 51 affected files, reset to `origin/main`, copy back the
24 pure-new-work files, re-apply 5 small changes on top of main, delete 2 dead
config-split files.

## What was kept from main (10 reversion files)

These files were reverted to pre-Devin state in the working tree. After reset
to `origin/main`, they now have main's version — no action needed.

| File | Main's fixes recovered |
|------|------------------------|
| `src/agents/orchestrator.py` | Async `create()` factory, citation verifier (`renumber_citation_markers`), SQLite cache wiring |
| `docs/ARCHITECTURE.md` | SECRET_KEY auto-gen docs, token suppression paragraph, single-tier cache description |
| `documentation.md` | Unified Citation Rendering section |
| `src/agents/route_processors.py` | Route handler improvements |
| `src/agents/hybrid_route_handler.py` | Hybrid handler improvements |
| `docker-compose.yml` | Bind mount with comments, platform flag |
| `.env.example` | Provider auto-detection, chunking (1500/300 A/B-tuned), SECRET_KEY auto-gen sections |
| `frontend/src/contexts/UserContext.tsx` | Crypto-secure UUID generation |
| `scripts/ops/generate_api_key.py` | Security docstring |
| `src/agents/protocols.py` | Cache docstring |
| `src/query_processing/gemini_client.py` | Cache docstring |

## What was investigated and discarded (8 mixed files)

These files had our changes that conflicted with main's better versions.
Side-by-side comparison confirmed main's version is superior in every case.

| File | Our change | Why main's version is better |
|------|-----------|------------------------------|
| `src/config.py` | Split into 3 mixin modules | Split was 407 lines vs main's 356 — larger not smaller. Motivation (hybrid) gone. 16 of 24 extra fields dead. Loses `OPENROUTER_API_KEY` + A/B-tuned chunk defaults. |
| `src/api/lifespan.py` | Sync orchestrator init, `_l2_cache` attribute | **Bug in ours**: set `llm_client._l2_cache` but `base_rag_client.py` reads `self._sqlite_cache` — cache silently never wired. Main's async `create()` factory is correct pattern. |
| `src/api/main.py` | Manual token param parsing, removed `unquote` | Main's FastAPI `tokens: bool = True` is cleaner. Main's `unquote()` is safer (belt-and-suspenders for path traversal). |
| `src/db/sqlite_cache.py` | Sync factory (no singleton) | Main: async singleton with double-checked locking — one shared instance. Ours: new instance every call — no shared cache state. |
| `src/utils/cache.py` | `await` → sync call | Same async→sync reversion. Keep main's async. |
| `src/api/health.py` | `await` → sync call | Same async→sync reversion. Keep main's async. |
| `tests/test_sqlite_cache.py` | Sync factory tests | Main: 4 tests covering singleton + concurrency. Ours: 3 tests, no singleton tests. |
| `README.md` | Simpler version | User decision — keep main's polished version. |

## What was deleted (2 dead files)

| File | Why |
|------|-----|
| `src/config_documents.py` | Part of config split — nothing imports it (kept main's monolithic config.py) |
| `src/config_infrastructure.py` | Part of config split — nothing imports it (kept main's monolithic config.py) |

## Final working tree state

### Modified tracked files (19) — our genuine work on top of main

| File | Change |
|------|--------|
| `.gitignore` | Expanded frontend ignore patterns (dist-ssr, coverage, playwright-report, .cache, .turbo, etc.) |
| `frontend/src/components/chat/chatMessageCitations.utils.ts` | Removed stale "hybrid retrieval provides this" comment |
| `frontend/src/services/cora/types.ts` | Added `metadata?: Record<string, unknown> \| null` to `CitationDetail` interface |
| `src/agents/kb_route_handler.py` | Inlined named constants back to literal values (simpler) |
| `src/api/query_models.py` | Added `metadata: Optional[Dict[str, Any]] = None` field to `CitationDetail` model |
| `src/citations/citation_manager.py` | Added `category`, `publisher`, `registry_document_id`, `methodology_codes` to `safe_metadata_fields` |
| `src/citations/formatter.py` | Added `_curate_metadata()` method — filters VCM metadata to non-redundant fields for API payload |
| `src/config_store.py` | Added `similarity_threshold` field to `_CollectionRelevanceOverrides` |
| `src/document_loader/metadata_extractor.py` | Changed `_detect_registry()` → `_detect_registry_pattern()`, returns `RegistryPattern` not str; uses `is_registry` to split registry vs category |
| `src/document_store/indexer.py` | Added `import re`, payload index constants, image placeholder stripping for standard mode, `category` field in metadata + payload indexes, `_MIN_CHUNK_CHARS` |
| `src/document_store/jobs.py` | Added `category=meta.get("category")` in both `process_document_job` and `reindex_document_job` |
| `src/document_store/models.py` | Added `category: str \| None = None` field to `DocumentRecord` + `to_dict()` |
| `src/document_store/storage.py` | Added `category TEXT` column to schema, `_row_to_record()`, `insert_document()`, `update_document()` |
| `src/memory/pii_redactor.py` | Inlined regex patterns (removed import from `pii_patterns`), changed `subn` to callback-based `sub` |
| `src/registry_config/registry_patterns.py` | Split into thin aggregation layer re-exporting from `_registries`, `_governance`, `_categories` |
| `src/retrieval/langchain_retriever.py` | Whitespace cleanup only (trailing spaces) |
| `tests/test_citation_manager.py` | Added tests for VCM metadata surfacing + curation (163 new lines) |
| `tests/test_metadata_extractor.py` | Updated tests: `registry` → `category` for non-registry patterns (VCM Policy, ICVCM) |
| `tests/test_title_utils.py` | Updated test: `registry` → `category` for VCM Policy test case |

### Untracked files (8) — new files to commit

| File | Lines | What it does |
|------|-------|-------------|
| `migrations/005_document_category.sql` | 9 | Adds `category TEXT` column to `document_store_documents` |
| `src/registry_config/_categories.py` | 247 | 14 topic classifier patterns (Market Intelligence, VCM Policy, etc.) |
| `src/registry_config/_common.py` | 46 | Shared `RegistryPattern` dataclass + `is_registry` field + version-pattern constants |
| `src/registry_config/_governance.py` | 105 | 7 governance/standard body patterns (ICVCM, SBTi, CORSIA, etc.) |
| `src/registry_config/_registries.py` | 378 | 27 credit-issuing registry patterns (Verra, Gold Standard, CDM, etc.) |
| `docs/OPEN_SOURCE_PLAN.md` | 59 | Open source preparation plan |
| `docs/plans/revert-hybrid-retrieval.md` | 115 | Documentation of hybrid retrieval revert decision |
| `docs/plans/uncommitted-changes-inventory.md` | — | This file |

### Ignored by .gitignore (kept local, intentionally not committed)

- `AGENTS.md` — AI agent onboarding guide
- `CLAUDE.md` — Claude Code guidance
- `tests/test_secret_key_auto.py` — SECRET_KEY auto-generation self-check

## Verification

- **390 tests pass**, 0 failures
- All `src/` modules import successfully
- No references to dead config split files
- No references to reverted hybrid search
- Category field flows through entire pipeline (models → storage → jobs → indexer → metadata_extractor → citation_manager → formatter → query_models → types.ts)
- Migration 005 works for both new and existing databases
- `RegistryPattern.is_registry` field properly defined and used

## Execution summary

1. Backed up 51 affected files to `D:\Cora ai_backup_20260706` (backup removed after verification)
2. `git reset --hard origin/main` — clean baseline with all main fixes
3. Copied back 14 pure new-work tracked files from backup
4. Re-applied 5 small changes on top of main (config_store, jobs, indexer, .gitignore, chatMessageCitations)
5. Fixed duplicate `unlink` line in storage.py
6. Deleted 2 dead config split files
7. Ran full test suite — 390 passed
8. Removed backup
