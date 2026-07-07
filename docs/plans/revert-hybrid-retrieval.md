# Hybrid Retrieval Revert Plan

## Verdict

The A/B evaluation (10 specific questions, 9 documents, 321 chunks) showed **dense retrieval slightly outperformed hybrid** on answer quality (4.50/5 vs 4.30/5). Hybrid won 1 question, dense won 2, 7 were ties. The BM25 component sometimes promoted header/TOC chunks over content chunks, introducing noise. **Hybrid retrieval is not worth the added complexity.**

## What to revert

### 1. Delete hybrid-specific files (untracked, safe to delete)

These files were created entirely for the hybrid retrieval experiment:

```
src/retrieval/hybrid_search.py
src/config_retrieval.py
scripts/reindex_hybrid.py
scripts/evaluation/ab_test_retrieval.py
scripts/evaluation/build_retrieval_dataset.py
scripts/evaluation/rag_eval.py
tests/test_hybrid_search.py
tests/test_hybrid_indexer.py
tests/test_ab_test_retrieval.py
tests/eval_questions.json
tests/eval_retrieval_dataset.json
docs/plans/hybrid-retrieval.md
results/                          (entire directory)
```

### 2. Delete Qdrant hybrid collection

```python
from qdrant_client import QdrantClient
client = QdrantClient(url="http://localhost:6333")
client.delete_collection("cora_hybrid")
```

### 3. Revert modified files that have hybrid-specific changes

These files have hybrid code mixed in. Use `git checkout -- <file>` to revert them to the last commit, OR manually remove only the hybrid-specific parts if you want to keep other changes:

**Fully hybrid — revert entirely with `git checkout`:**
- `src/retrieval/langchain_retriever.py` — added `_hybrid_search()` method, `RETRIEVAL_MODE` dispatch, hybrid imports
- `src/retrieval/fusion_retrieval.py` — added hybrid search dispatch and imports
- `src/document_store/indexer.py` — added `_is_hybrid_mode()`, `_ensure_hybrid_collection()`, `_upsert_hybrid_chunks()`, `build_hybrid_points()`

**Partially hybrid — manually remove hybrid parts only:**
- `src/config.py` — has a comment referencing `config_retrieval.RetrievalSettings` for "dense + hybrid retrieval". Remove that comment.
- `src/agents/hybrid_route_handler.py` — the diff is actually a citation filtering change, NOT hybrid retrieval. **Keep this change.**

### 4. Files that are NOT hybrid-related (do NOT revert)

These modified files contain other work (V1-fixes, bug fixes, improvements) and should be kept:

- `.env.example` — env var cleanup
- `.gitignore` — ignore patterns
- `README.md` — documentation updates
- `docker-compose.yml` — docker config
- `docs/ARCHITECTURE.md` — architecture docs
- `documentation.md` — documentation
- `frontend/src/contexts/UserContext.tsx` — frontend changes
- `frontend/src/services/cora/types.ts` — frontend types
- `scripts/ops/generate_api_key.py` — API key script
- `src/agents/kb_route_handler.py` — KB route handler changes
- `src/agents/orchestrator.py` — orchestrator changes (no hybrid code)
- `src/agents/protocols.py` — protocol changes
- `src/agents/route_processors.py` — route processor changes
- `src/api/health.py` — health check changes
- `src/api/lifespan.py` — lifespan changes (no hybrid init)
- `src/api/main.py` — API main changes
- `src/api/query_models.py` — query model changes
- `src/citations/citation_manager.py` — citation manager changes
- `src/citations/formatter.py` — citation formatter changes
- `src/config_store.py` — config store changes
- `src/db/sqlite_cache.py` — SQLite cache bug fix
- `src/document_loader/metadata_extractor.py` — metadata extractor changes
- `src/document_store/jobs.py` — job processing changes
- `src/document_store/models.py` — document model changes
- `src/document_store/storage.py` — storage changes
- `src/memory/pii_redactor.py` — PII redactor changes
- `src/query_processing/gemini_client.py` — Gemini client changes
- `src/registry_config/registry_patterns.py` — registry patterns changes
- `src/utils/cache.py` — cache utility changes
- `tests/test_citation_manager.py` — citation tests
- `tests/test_metadata_extractor.py` — metadata tests
- `tests/test_sqlite_cache.py` — SQLite cache tests
- `tests/test_title_utils.py` — title utils tests

### 5. Other untracked files (NOT hybrid, do NOT delete)

- `AGENTS.md` — agent onboarding doc
- `CLAUDE.md` — Claude Code guidance
- `docs/OPEN_SOURCE_PLAN.md` — open source plan
- `migrations/005_document_category.sql` — DB migration (category column)
- `src/config_documents.py` — document config
- `src/config_infrastructure.py` — infrastructure config
- `src/registry_config/_categories.py` — registry categories
- `src/registry_config/_common.py` — common registry config
- `src/registry_config/_governance.py` — governance registry config
- `src/registry_config/_registries.py` — registries config
- `tests/test_secret_key_auto.py` — secret key test

## Execution commands

```bash
# 1. Delete hybrid-specific files
del src\retrieval\hybrid_search.py
del src\config_retrieval.py
del scripts\reindex_hybrid.py
del scripts\evaluation\ab_test_retrieval.py
del scripts\evaluation\build_retrieval_dataset.py
del scripts\evaluation\rag_eval.py
del tests\test_hybrid_search.py
del tests\test_hybrid_indexer.py
del tests\test_ab_test_retrieval.py
del tests\eval_questions.json
del tests\eval_retrieval_dataset.json
del docs\plans\hybrid-retrieval.md
rmdir /s /q results

# 2. Delete Qdrant hybrid collection
python -c "from qdrant_client import QdrantClient; QdrantClient(url='http://localhost:6333').delete_collection('cora_hybrid')"

# 3. Revert files with hybrid-specific changes
git checkout -- src/retrieval/langchain_retriever.py
git checkout -- src/retrieval/fusion_retrieval.py
git checkout -- src/document_store/indexer.py

# 4. Remove hybrid comment from config.py (manual edit)
# Remove the line: "# - ``config_retrieval.RetrievalSettings`` - dense + hybrid retrieval, RAG,"

# 5. Verify tests pass
pytest tests/ -x
```

## After revert

- Dense-only retrieval on `cora_dense_only` collection (321 points, 9 documents)
- No hybrid collection, no BM25, no fusion code
- All other V1-fixes work preserved
- `RETRIEVAL_MODE` env var no longer used (can be removed from .env if set)
