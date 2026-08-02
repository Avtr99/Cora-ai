# Cora Chat Readiness Feature

## Overview

The chat readiness feature prevents users from interacting with the chat when the
backend is not running or when the required knowledge base (KB) / web search
configuration is missing. It also shows a meaningful empty-state answer when the
KB has no relevant documents and web search is disabled.

## Backend

### Settings status endpoint

`GET /api/v1/settings/status` is implemented in the `src/api/settings_routes/`
package (main logic in `src/api/settings_routes/status.py`). It exposes the
fields used by the frontend to decide whether the chat is usable:

- `chat_ready` — `True` when the LLM is configured and either the KB has indexed
  documents or web search is enabled (`LLM configured AND (kb_ready OR search_ready)`).
- `kb_ready` — `True` when the configured Qdrant collection has indexed
  documents (`points_count > 0`).
- `search_ready` — `True` when a web search provider other than `none` is
  configured (e.g. Tavily API key present).
- `ready` — `True` when all required providers (LLM, embeddings, reranker,
  search) are configured.
- `llm` / `embeddings` / `reranker` / `search` — per-provider status objects
  (`provider`, `has_api_key`, `model`, `is_configured`, `warning`).
- `qdrant` — Qdrant collection info (collection name, vector dimension, points
  count) or an error object if Qdrant is unreachable.
- `warnings` — List of configuration warnings (missing keys, dimension mismatch,
  unreachable Qdrant, etc.).

Backend reachability is determined separately by the frontend via the
`/health` endpoint, not by `/settings/status`.

### Empty KB response flag

`src/agents/kb_route_handler.py` sets `result["kb_empty"] = True` when the
knowledge base route retrieves zero documents and web search is disabled.
Both `src/agents/orchestrator.py` and `src/agents/streaming_orchestrator.py`
propagate this flag into the response metadata as `metadata.kb_empty`.

### Streaming KB quality checks

`KBStreamingHandler.process_stream()` supports token-emitting and token-suppressed
execution. With `tokens=false`, it evaluates the completed answer rather than the
unused token buffer. Explicit non-answers are web-supplemented, while substantive
answers are passed to the retrieval-aware relevance validator with the retrieved
source chunks. Web supplementation occurs only for an explicit non-answer or a
high-confidence irrelevant verdict; relevant KB answers remain KB-only.

## Frontend

### `useChatReadiness` hook

`frontend/src/hooks/useChatReadiness.ts` uses an explicit `/health` check plus
`GET /api/v1/settings/status` to derive the readiness state. `config` and
`documents` status queries are only enabled once the health check confirms the
backend is reachable, and the hook treats a failed health query as `backendDown`
even when TanStack Query still holds stale successful data from an earlier run.
This prevents the UI from showing a misleading "Add documents or enable web search"
message when the real issue is that the backend is offline.

- `backendUp` — whether the backend health endpoint is reachable.
- `chatReady` — whether the chat can accept input.
- `notReadyReason` — one of `backend_down`, `llm_not_configured`, or
  `no_answer_source`.
- `disabledPlaceholder` — copy shown in the disabled search bar.
- `kbDocCount`, `kbEmpty`, `webEnabled`, `ingestionInProgress` — supporting
  status data.

### `ChatReadinessBanner` component

`frontend/src/components/chat/ChatReadinessBanner.tsx` renders a subtle inline
notice above the composer when the chat is not ready. It uses muted text and
quiet text links instead of a prominent warning card, keeping the empty-state
UI unobtrusive. The backend-offline state is shown as the highest-priority
message so users do not see setup prompts when the server simply isn't running.

### `SearchBar` integration

`frontend/src/components/ui/SearchBar.tsx` disables the input and submit button
when `ready` is `False`, uses `disabledPlaceholder` as placeholder text, and
greys out the bar with a muted background/border so the disabled state is clear
without a loud warning color.

### Empty KB answer state

`frontend/src/contexts/chat/useBotResponse.ts` checks `finalResponse.metadata?.kb_empty`
and replaces the empty / non-answer fallback with an actionable message that
suggests rephrasing the question, adding documents, or enabling web search.

### Settings dialog store

`frontend/src/store/settingsDialogStore.ts` is a global Zustand store that
controls the `SettingsDialog` open state and active tab. `UserMenu.tsx` and the
chat readiness banner both use it so the settings dialog can be opened from
multiple places with a single source of truth.

### Onboarding welcome step

`frontend/src/pages/OnboardingPage.tsx` and `frontend/src/components/onboarding/WelcomeStep.tsx`
were redesigned to remove the generic three-card feature grid and replace the heavy
config-detection banner with a cleaner, centered status summary. The onboarding
load now calls `checkHealth()` first and shows the backend-down screen immediately
if the server is unreachable, instead of waiting for all settings endpoints to fail.
The progress indicator uses text labels for context, and the backend-down screen
uses a subtle icon card instead of a warning emoji.

## UX States

| State | Trigger | Banner copy | Disabled placeholder |
|-------|---------|-------------|---------------------|
| Backend down | health endpoint fails | "Backend is offline — start the server to use chat." | "Start the backend to use chat" |
| LLM not configured | backend up, LLM not set | "AI model not configured. Configure AI model" | "Configure an AI model to use chat" |
| No answer source | backend + LLM ready, KB empty and web search off | "Chat needs documents or web search enabled to answer." | "Add documents or enable web search to use chat" |

## Testing

Backend:
- `tests/test_api.py::TestAPI::test_config_status_returns_chat_readiness_fields`
  verifies the new status fields.

Frontend:
- `frontend/src/components/chat/ChatReadinessBanner.test.tsx` structural smoke
  test.
- Existing `vitest` suite covers the streaming / query services.

Run the relevant suites:

```powershell
# Backend
cd "d:/Cora ai"
pytest tests/test_api.py tests/test_citation_manager.py
ruff check src/api/settings_routes/ src/agents/kb_route_handler.py src/agents/orchestrator.py src/agents/streaming_orchestrator.py

# Frontend
cd "d:/Cora ai/frontend"
npm run test -- --run
npm run lint
npm run build
```

## Files Changed

- `src/api/settings_routes/` (package: `status.py`, `llm.py`, `embeddings.py`, `search.py`, `reranker.py`, etc.)
- `src/agents/kb_route_handler.py`
- `src/agents/orchestrator.py`
- `src/agents/streaming_orchestrator.py`
- `src/query_processing/base_rag_client.py`
- `src/utils/cache.py`
- `frontend/src/hooks/useChatReadiness.ts`
- `frontend/src/components/chat/ChatReadinessBanner.tsx`
- `frontend/src/components/ui/SearchBar.tsx`
- `frontend/src/pages/Index.tsx`
- `frontend/src/pages/OnboardingPage.tsx`
- `frontend/src/components/onboarding/WelcomeStep.tsx`
- `frontend/src/services/llmSettingsApi.ts`
- `frontend/src/services/coraApi.ts` (health check export)
- `frontend/src/services/cora/types.ts`
- `frontend/src/contexts/chat/useBotResponse.ts`
- `frontend/src/store/settingsDialogStore.ts`
- `frontend/src/components/layout/UserMenu.tsx`
- `frontend/src/components/settings/SettingsDialog.tsx`
- `tests/test_api.py`
- `frontend/src/components/chat/ChatReadinessBanner.test.tsx`

## Removal of Hardcoded Starter Prompt Answers

The three frontend starter prompts (VM0048, VCM pricing, COP 30) were previously
short-circuited by the orchestrator to static answers in
`src/utils/starter_prompts.py`. For the local self-hosted version this was
misleading when those documents were not in the KB.

- Removed the starter-prompt short-circuit from `src/agents/orchestrator.py` and
  `src/agents/streaming_orchestrator.py`.
- Moved the general query-cache helpers (`QUERY_HANDLER_TYPE`,
  `get_query_cache_key`) from `src/utils/starter_prompts.py` into
  `src/utils/cache.py`.
- Updated `src/query_processing/base_rag_client.py` to import the cache helpers
  from `src/utils/cache.py`.
- The starter prompt files (`src/utils/starter_prompts.py` and
  `scripts/ops/fetch_starter_answers.py`) have been deleted as dead code.

## LLM Provider Fallback

When the primary LLM provider hits a quota/rate-limit error (e.g. Gemini `429
RESOURCE_EXHAUSTED`), the backend can transparently fall back to the other
configured provider (e.g. OpenAI) so the chat keeps working.

### How it works

- `src/query_processing/fallback_llm_client.py` introduces `FallbackLLMClient`,
  a wrapper that implements the `LLMClient` protocol and inherits from
  `BaseRAGClient` so the streaming RAG wrapper can reuse its helpers.
- `FallbackLLMClient` catches 429 / `RESOURCE_EXHAUSTED` / `rate_limit` /
  `quota` / `circuit is open` errors from the primary provider and retries the
  same call against the fallback provider.
- `src/query_processing/llm_factory.py` builds a `FallbackLLMClient` when the
  opposite provider's API key is also configured in the environment (e.g. primary
  Gemini with `OPENAI_API_KEY` set, or primary OpenAI with `GEMINI_API_KEY` set).

### UI provider switching

Users can switch the primary provider at any time via **Settings → AI Model**
in the chat UI. The dialog supports Gemini and OpenAI-compatible presets
(OpenAI, Ollama, OpenRouter, etc.). Automatic fallback uses the other provider's
environment key.

### LLM config discriminated union

`src/query_processing/llm_config_models.py` defines a Pydantic discriminated
union that makes structurally impossible provider configs unrepresentable at
the type level. This replaces the previous `sanitize_llm_settings()` runtime
guard and the `_api_key_matches_provider()` heuristic — both deleted.

- **`GeminiConfig`** — has `provider`, `api_key`, `model_main`, `model_lite`,
  `model_relevance`. **No `base_url` or `organization` fields** — a Gemini
  config can never carry an OpenRouter URL or an OpenAI org ID.
- **`OpenAICompatibleConfig`** — has all 7 fields including `base_url` and
  `organization`. Covers OpenAI, OpenRouter, Ollama, vLLM, LM Studio, etc.
- **`LLMConfig`** — `Annotated[Union[GeminiConfig, OpenAICompatibleConfig],
  Field(discriminator="provider")]`. FastAPI uses this directly as the
  `PUT /v1/settings/llm` request body type; unknown providers get 422 at
  parse time.
- **Field validators** on `api_key` clear wrong-provider keys (e.g. an `sk-or-`
  key under a Gemini config) so the env-detection fallback can backfill the
  correct key on the next switch.
- **`validate_llm_config(raw)`** — validates a raw dict through the union
  (backed by a `TypeAdapter`). Used by `_write_llm_settings`,
  `get_llm_settings`, and `_save_profile` to validate at every write/read
  boundary.
- **`config_to_dict(config)`** — converts a validated model to a full 7-key
  dict (fills missing provider-specific fields with `None`) so dict-access
  callers (`settings["provider"]`, `settings["base_url"]`) keep working.

`get_llm_settings()` still returns a dict (not the typed model) to avoid
touching ~30 dict-access call sites across 6 consumer files. Every dict that
leaves `get_llm_settings()` was validated through the union first — no bad
config can reach callers. `_validate_llm_models()` stays as a route-handler
helper for model-name prefix checks (a separate concern from cross-field
consistency). Old corrupt DB records are handled via `extra="ignore"` — no
migration needed.

## Unified Citation Rendering

### Problem

- Inline citation markers were rendered as large, colored pill boxes that interrupted the answer text.
- The source list used two separate numbering systems: "Knowledge Base: 1, 2, 3" (purple) and "Web: 1, 2, 3" (gray), so the numbers in the answer text did not match a single source list.
- Some source labels arrived URL-encoded (e.g. `vm0047%20arr%20v1.0`) and were displayed literally, making them unreadable.

### Solution

1. **Single global numbering sequence**
   - `ChatMessage.tsx` builds a `CitationNumberMap` from `sourceLinks`. Each source gets a global number based on its position in the combined list.
   - `ChatMarkdownContent.tsx` maps backend per-type numbers (`[cite_kb: N]`, `[Web, cite: N]`) to those global numbers, so inline markers and the source list share one linear sequence.

2. **Less obtrusive inline markers**
   - `InlineCitationPill` in `chatMessageCitations.tsx` now renders small superscript numbers (`1, 2`) instead of pill boxes. They are clickable and scroll to the source list.

3. **Unified source list**
   - `CitationBadges.tsx` renders a single "Sources" section with all sources numbered continuously. Source type is still indicated by the icon and the number-circle color (KB = brand purple, Web = muted gray).

4. **URL-encoded label decoding**
   - `decodeSourceLabel` is now shared between `chatMessageCitations.utils.ts` and `CitationBadges.tsx`.
   - It handles `%20`, `+`, and double/triple encoding up to 8 passes.
   - It also byte-decodes labels safely, so a single malformed/broken `%` no longer aborts decoding of the rest of the label.
   - `processCitationPart` in `chatMessageCitations.utils.ts` now also decodes fallback source strings.

### Files Changed

- `frontend/src/components/chat/ChatMessage.tsx`
- `frontend/src/components/chat/ChatMarkdownContent.tsx`
- `frontend/src/components/chat/chatMessageCitations.tsx`
- `frontend/src/components/chat/CitationBadges.tsx`
- `frontend/src/components/chat/chatMessageCitations.utils.ts`
- `frontend/src/components/chat/chatMessageCitations.utils.test.ts`

### Backend citation marker renumbering

After `filter_citations_by_answer` removes citations that aren't grounded in
the answer, the inline `[cite_kb: N]` / `[Web, cite: N]` markers in the answer
text still reference the original source indices. `renumber_citation_markers`
in `src/query_processing/citation_verifier.py` rewrites them so `N` refers to
the position in the filtered citation list — which is what the frontend
displays. Markers referencing filtered-out sources are removed entirely.

The marker regex patterns (`CITE_KB_RE`, `CITE_WEB_RE`) and the
`unique_sources_by_type` helper are shared via `src/citations/markers.py` —
the single source of truth for parsing `[cite_kb: N]` / `[Knowledge Base,
cite: N]` / `[cite_web: N]` / `[Web, cite: N]` markers. Both the citation
filter (`src/citations/filter.py`) and the renumberer
(`src/query_processing/citation_verifier.py`) import from it so they agree
on what index `N` means. The filter also uses `extract_cited_indices` to
retain explicitly-cited sources even when snippet/name overlap heuristics
would reject them — preventing dangling markers in the final answer.

This is called in three places:
- `src/agents/route_processors.py:_finalize_citations` (KB, Web routes)
- `src/agents/orchestrator.py` (sync orchestrator)
- `src/agents/streaming_orchestrator.py` (streaming orchestrator, final result event only)
- `src/agents/hybrid_route_handler.py` (hybrid route, after `grounded_citations`)

### Source-name fallback chain

Citation source names (what the frontend renders as the source label) are
resolved from chunk metadata using a shared fallback chain across all
consumers: `title → file_name → original_filename → parent_doc → source`.
This ensures the document's extracted title (e.g. "ACM0003: A/R Large-scale
Consolidated Methodology v02.0") is preferred over the raw filename (e.g.
"AR-ACM0003_ver02.0.pdf"). The chain is applied in:

- `src/citations/extractor.py` — citation list source names
- `src/query_processing/base_rag_client.py` — LLM context `<source>` tags
- `src/query_processing/summarize_service.py` — summarize citation names
- `src/retrieval/result_processor.py` — per-source diversification (2 sites)
- `src/citations/source_type.py` — KB vs web source-type detection

`clean_source_name` in `src/citations/source_name.py` normalizes the resolved
name: strips path prefixes and file extensions, title-cases, preserves known
acronyms (VCS, IPCC, NDC, etc.), and keeps domain slashes like "A/R"
(Afforestation/Reforestation) intact rather than treating them as path
separators.

## Case Study Satellite Images Layout

The mangrove case-study page was reorganized to present the satellite section
as informational imagery, not as proof of impact. The shared attribution line
was simplified to 'Captured with Copernicus Sentinel-2'.

### What changed

- **Section title:** Renamed from `Satellite Evidence` to `Satellite images` so
  it reads as supporting visual context rather than a claim of evidence.
- **Project overview moved down:** The `About` paragraph and key project metadata
  (location, duration, methodology, project type) now sit beside the project
  boundary map, instead of appearing as a separate top section.
- **Boundary map resized:** The overview map is now a compact locator thumbnail
  (up to 220px wide on desktop). Clicking it opens the full-resolution image in a
  same-window lightbox modal that fits the image within the viewport without
  scrolling.
- **Comparison cards uniformed:** The before/after sliders now use a consistent
  `4:3` aspect ratio and equal-height rows (`auto-rows-fr`), so the three
  village-tract comparisons align.
- **Slider handle reduced:** The comparison handle is now smaller, subtler, and
  still keyboard-accessible. The existing `react-compare-slider` library remains
  responsible for drag, keyboard, and screen-reader behaviour.
- **Captions aligned:** Figcaption areas use a small minimum height on larger
  screens so the card bottoms line up even when captions wrap.

### Files Changed

- `frontend/src/pages/CaseStudyPage.tsx`
- `frontend/src/components/case-study/BeforeAfterSlider.tsx`
- `frontend/src/components/case-study/ProjectDetails.tsx`

### Frontend cleanup

- `extractDomain` in `chatMessageCitations.utils.ts` now reuses the shared
  `decodeSourceLabel` instead of duplicating the URL-decoding loop.
- The `data\` path fallback in `processCitationPart` and the `sources` array
  path both decode URL-encoded labels and strip the `data\` prefix.
- `preprocessContent` produces clean markdown links (`[kb](url)`) instead of
  double-bracketed text. Numberless markers (`[Knowledge Base]`, `[Web]`) are
  removed instead of leaving gaps in the text.
- `CITATION_INTERNAL_URL` constant is shared between `chatMessageCitations.utils.ts`
  and `ChatMarkdownContent.tsx`.

### Files Changed (backend)

- `src/citations/markers.py` (new — shared marker regex + `extract_cited_indices` + `unique_sources_by_type`)
- `src/citations/filter.py` (explicit-citation retention via shared markers)
- `src/citations/source_name.py` (slash heuristic: don't treat domain "A/R" as path separator)
- `src/citations/extractor.py` (title + original_filename in source-name fallback chain)
- `src/citations/source_type.py` (original_filename in KB detection)
- `src/citations/citation_manager.py` (original_filename in safe_metadata_fields allowlist)
- `src/query_processing/citation_verifier.py` (import from shared markers module, removed duplication)
- `src/query_processing/base_rag_client.py` (original_filename in source-name fallback chain)
- `src/query_processing/summarize_service.py` (title + original_filename in source-name fallback chain)
- `src/retrieval/result_processor.py` (original_filename in source fallback, 2 sites)
- `src/agents/route_processors.py` (call renumber after filter)
- `src/agents/orchestrator.py` (call renumber after filter)
- `src/agents/streaming_orchestrator.py` (call renumber after filter)
- `src/agents/hybrid_route_handler.py` (call renumber after filter)
- `tests/test_citation_manager.py` (3 new regression tests)
- `tests/test_citation_renumber.py` (12 new tests)

### Testing

```powershell
# Frontend
cd "d:/Cora ai/frontend"
npm run test -- --run
npm run lint
npm run build

# Backend
cd "d:/Cora ai"
pytest tests/test_citation_renumber.py tests/test_citation_manager.py
ruff check src/query_processing/citation_verifier.py src/agents/

## `frontend/src/components/chat/useChatScroll.ts`

### `useChatScroll(options?)`

Tracks the scroll position of the chat container (default selector `[data-chat-scroll-container]`) and exposes helpers for jumping to the top or bottom of a conversation.

- Returns `isAtBottom`, `canScroll`, `canScrollToTop`, `isScrolling`, `scrollToBottom`, and `scrollToTop`.
- Uses `requestAnimationFrame` throttling for the `scroll` listener and `ResizeObserver` / `MutationObserver` to keep state accurate as the chat grows.
- `isScrolling` is `true` while the user is actively scrolling and stays `true` for `2500ms` after the last scroll or `touchmove` event. This powers the `ChatScrollButton` auto-show/hide behavior and is also triggered by mobile touch dragging.
- `scrollToBottom` performs a smooth scroll and a one-time corrective frame because virtualized `scrollHeight` can change while rows are being measured.

**Used by:** `ChatScrollButton`, `ChatInterface` (only the `CHAT_CANCEL_AUTOSCROLL` event constant).
```

## Query Cache Key: Model + Corpus + Config Version

The query result cache key previously used `sha256(query)` only, so a cached
answer could be served stale after a document reingestion, or after the
embedding / reranker / answer-generation LLM model was swapped via the Settings
UI (`reload_settings()` did not invalidate the cache). This was a verified
correctness bug.

### Solution

The cache key now folds every input that can change the answer into a single
`json.dumps(..., sort_keys=True)` block (see `src/utils/cache.py`):

- the normalized query (always present),
- an optional retrieval-context fingerprint (unchanged opt-in path),
- `config_revision` — bumped on any embedding/reranker/LLM model change,
- `corpus_revision` — bumped once per ingestion batch,
- `config_version` — bumped on every `reload_settings()` call,
- the embedding provider+model+dim and reranker provider+model (read from the
  in-memory `Settings` singleton — no DB hit on the hot path).

A revision bump changes the key, so stale entries are skipped automatically;
`clear()` is still called on config changes to reclaim the space.

### New module: `src/db/revisions.py`

- `get_revisions()` — read all counters/version in one DB round-trip (defaults
  to 0 and `None` for the optional `config_version_updated_at`).
- `bump_revision(key)` — atomic UPSERT increment, returns the new value.
  Guards the theoretical 64-bit overflow by wrapping to 0.
- `bump_corpus_revision()` / `bump_config_revision()` / `bump_config_version()`
  — convenience wrappers.
- Constants `CORPUS_REVISION_KEY` / `CONFIG_REVISION_KEY` / `CONFIG_VERSION_KEY`.
  All counters are stored as integer strings in the existing `app_settings`
  table, so they persist across restarts without a dedicated migration.

### `QueryCache` changes (`src/utils/cache.py`)

- `build_cache_key(query, context_fingerprint=None)` — public key builder that
  reads `corpus_revision` / `config_revision` / `config_version` from the DB
  each call, then folds the query, optional context fingerprint, and the
  embedding/reranker model fingerprint into a stable key.
  `_build_query_cache_key` is a backwards-compatible alias.
- `_model_fingerprint()` — embedding/reranker fingerprint from the Settings
  singleton. The LLM answer-generation model is represented via
  `config_revision`.
- `config_fingerprint()` — resolved snapshot of all model-affecting settings
  (embedding, reranker, LLM provider + models). Used by the settings routes to
  take a `before` snapshot and skip the cache clear on no-op saves.
- `invalidate_query_cache_for_config_change()` — async helper that bumps
  `config_revision` and clears stale entries. Called by the settings routes
  after a model-affecting save.

### Call sites updated

- `src/config_store.py` — `reload_settings()` re-applies the DB overlay to the
  Settings singleton and bumps `config_version`. The query cache
  no longer keeps an in-memory revision snapshot, so no explicit refresh is
  needed.
- `src/document_store/indexer.py` — `invalidate_document_caches()` bumps
  `corpus_revision` (inside the debounced path, so a bulk ingestion bumps once
  per burst / batch-level) and clears the SQLite cache. The bump runs after the
  Qdrant upsert has already succeeded.
- `src/api/settings_routes/embeddings.py`, `reranker.py`, `search.py` — call
  `reload_settings()` after a save, which bumps `config_version`. They then
  call `invalidate_query_cache_for_config_change()` to bump `config_revision`
  and clear stale entries. `embeddings.py` and `reranker.py` use the
  transactional `save_app_settings()` batch write with scoped per-subsystem
  API key names (see "Scoped API keys" section below).
- `src/api/settings_routes/llm_config.py` — calls `reload_settings()` after
  saving LLM provider settings (PUT `/llm`) so `config_version` is bumped on
  any Settings UI change. Also calls `invalidate_query_cache_for_config_change()`
  to bump `config_revision` and clear stale answers.
- `src/api/settings_routes/llm_profiles.py` — calls `reload_settings()` after
  switching LLM profiles (POST `/llm/switch`) and invalidates the query cache.
  Profile resolution (DB + .env detection, api_key backfill) is centralized in
  `src/db/llm_profile_manager.py::resolve_profile_for_switch`.
- `src/api/settings_routes/llm.py` — thin router aggregator that includes the
  `llm_config`, `llm_profiles`, `llm_ollama`, and `llm_test` sub-routers. No
  business logic lives here.
- `src/query_processing/base_rag_client.py` — `persist_to_cache` now builds the
  key via `query_cache.build_cache_key` so the write path and the read path
  (`check_query_cache` / `search_and_process`) produce identical keys.
- `src/api/settings_routes/status.py` — `GET /v1/settings/status` exposes
  `corpus_revision`, `config_revision`, `config_version`, and
  `config_version_updated_at` for debugging.

### Config version on responses

`process_query_core` and `process_query_core_stream` capture `config_version`
at request start and stamp it onto the top-level `Response.config_version`
field and `QueryMetadataResponse.config_version`. The stamp is an
observability aid, not a consistency guarantee. Folding `config_version`
into the cache key ensures cached responses do not report a stale version.

### Embedding cache note

The `embedding_cache` SQLite table (migration `001_initial.sql`) is defined but
not read or written anywhere in `src/` — it is unused infrastructure, so there
is no active stale-embedding bug. No schema change was needed for this ticket.

## Scoped API keys for embeddings & reranker (P0 fix)

The embeddings and reranker Settings UI routes previously wrote to the same
`app_settings` DB rows (`voyage_api_key`, `cohere_api_key`, `openai_api_key`).
The last writer won, silently overwriting the other subsystem's key. The fix
scopes the DB keys per subsystem so the cross-contamination state is
unrepresentable at the DB level.

### New `Settings` fields (`src/config.py`)

- `EMBEDDING_VOYAGE_API_KEY`, `EMBEDDING_COHERE_API_KEY`,
  `EMBEDDING_OPENAI_API_KEY` — scoped keys written by the embeddings Settings
  UI route and read by `src/embeddings/provider_factory.py`.
- `RERANKER_VOYAGE_API_KEY`, `RERANKER_COHERE_API_KEY` — scoped keys written
  by the reranker Settings UI route and read by
  `src/retrieval/reranker_factory.py`.
- `VOYAGE_API_KEY` / `COHERE_API_KEY` / `OPENAI_API_KEY` remain as `.env`-only
  fallbacks (used by LLM env-detection in `llm_factory.py` /
  `llm_profile_manager.py` and as a fallback in the factories when no scoped
  key is set). They are no longer in `DB_SETTING_KEYS`, so the DB does not
  write back to the shared env names.

### DB key namespace (`src/config_store.py`, `src/db/app_settings.py`)

`DB_SETTING_KEYS` maps the scoped DB keys to the new Settings attributes. The
shared key names are removed from the DB overlay (kept readable in
`_KNOWN_SETTING_KEYS` so migration 009 can backfill them).

### Transactional writes

`embeddings.py` and `reranker.py` now use `save_app_settings()` (batch,
single transaction) instead of multiple `save_app_setting()` calls. A crash
mid-save can no longer leave a partial config (provider written, key not).
This also advances the P1 "transactional settings writes" item for these two
routes; `search.py` still uses the singular form and remains P1.

### Single source of truth for key-present checks

`src/api/settings_routes/helpers.py::embedding_has_api_key` /
`reranker_has_api_key` are the only place that knows the scoped-key-with-env-
fallback logic. `src/api/health.py::check_embeddings_health` delegates to
`embedding_has_api_key` instead of duplicating the per-provider branching.
Adding a new embedding provider only requires updating `helpers.py`.

### Migration 009

`migrations/009_scope_embedding_reranker_api_keys.sql` — idempotent backfill
that copies the legacy shared values into both the embedding- and reranker-
scoped keys (only when the scoped key is absent, via `WHERE NOT EXISTS`).
Legacy rows are intentionally NOT deleted; they remain as `.env`-only
fallbacks. Re-running the migration is safe.

### Tests

`tests/test_embedding_reranker_settings.py` — 5 tests pin the fix:
embeddings/reranker Voyage keys don't cross-contaminate; Cohere same; OpenAI
scoped; `has_api_key` helpers read scoped key with env fallback.

## Split Ingestion Worker

The default `docker-compose.yml` now runs a **split stack**: a query-only
`app` container (no Docling/torch/RapidOCR, ~700MB smaller) plus a separate
`ingest-worker` container that runs the heavy PDF/OCR parsing. This isolates
CPU/RAM spikes from PDF/OCR parsing away from query latency, and keeps parser
memory leaks / crashes off the request-serving process.

### Dispatch mode

`INGESTION_DISPATCH` (`src/config.py`) selects how ingestion jobs are run:

- `in_process` (default for non-Docker / single-process runs): the API process
  schedules the converter/indexer via FastAPI `BackgroundTasks`.
- `worker` (set by the Docker Compose stack): the API only inserts a `queued`
  job row in SQLite and returns `202` immediately; a separate
  `ingest-worker` process polls the job table and runs the heavy parsing.

`schedule_ingestion_job(background_tasks, job_fn, document_id, job_id)` in
`src/document_store/dispatch.py` (re-exported via `jobs.py`) is the single
dispatch point called by every route in
`src/api/document_store_routes.py`. In `worker` mode it is a no-op (the job
row is already `queued`); in `in_process` mode it adds the task to
`BackgroundTasks`.

### Worker entrypoint — `src/document_store/worker.py`

`python -m src.document_store.worker` runs an asyncio loop that:

1. On startup: runs migrations, ensures the document store tables, and calls
   `recover_interrupted_documents(recover_queued_jobs=False)` — jobs left
   `processing` by a previous worker crash are marked `failed` (a job
   interrupted mid-conversion cannot be resumed), but `queued` jobs are
   preserved so the worker picks them up after a restart.
2. Polls `claim_next_job()` (see below) on a configurable interval
   (`INGEST_WORKER_POLL_INTERVAL_SECONDS`, default 2s).
3. Dispatches each claimed job to the same async handlers the in-process path
   uses (`process_document_job`, `reindex_document_job`,
   `delete_document_job`).
4. Installs SIGINT/SIGTERM handlers for a clean drain.

### Atomic job claim — `claim_next_job()` in `src/document_store/jobs_repo.py`

`SELECT` the oldest `queued` row, then `UPDATE ... SET status = 'processing'
WHERE id = ? AND status = 'queued'` and check `rowcount == 1`. The
conditional UPDATE closes the SELECT-then-UPDATE race, so two workers
(`docker compose up --scale ingest-worker=2`) can never pick up the same job.

### Recovery — `recover_interrupted_documents(recover_queued_jobs=...)`

In `in_process` mode, `src/api/lifespan.py` calls
`recover_interrupted_documents()` at startup to flip in-flight documents and
queued/processing jobs to `failed`. In worker mode the API skips recovery
entirely — the API and worker start concurrently, and if the API marks
in-flight documents as `failed` while the worker is actively processing them,
the worker would later overwrite the status to `indexed`, leaving a transient
incorrect `failed` state in the UI. The worker owns all recovery (jobs,
documents, stale locks) on its own startup and via its periodic stale sweep.

### Compose stack

`docker compose up -d --build` starts three services:

- **`app`** — builds with `INSTALL_INGESTION=false` (query-only, no
  Docling/torch/RapidOCR, ~700MB smaller than the parser image). Serves the
  FastAPI API and the built React SPA, runs the RAG pipeline, and enqueues
  ingestion jobs as SQLite rows.
- **`ingest-worker`** — builds with `INSTALL_INGESTION=true` (full parser
  stack) and runs `python -m src.document_store.worker`, which polls the job
  table and runs the converter + indexer.
- **`qdrant`** — vector store.

`app` and `ingest-worker` share `./data` (SQLite DB + document files) and the
Qdrant service. On Windows Docker Desktop / WSL2 this bind mount does not support
SQLite WAL shared memory, so `docker-compose.yml` sets `SQLITE_JOURNAL_MODE=DELETE`
for both containers. Local dev on a real filesystem can keep the default `WAL`.





## Cross-process document lock

`src/document_store/repository.py` adds `processing_job_id` to `document_store_documents`. This gives each document a single-owner lock across the `in_process` and `worker` dispatch modes.

- `try_acquire_document_lock(document_id, job_id)` atomically sets `processing_job_id` if it is currently `NULL`.
- `release_document_lock(document_id, job_id)` clears it when a handler finishes.
- `claim_next_job()` now skips queued jobs for documents whose `processing_job_id` is already set, so a second worker cannot pick up a job for a document that is being processed by another worker (or another in-process BackgroundTask).
- `_acquire_document_lock()` in `src/document_store/handlers.py` handles non-blocking requeue in worker mode and bounded waiting in `in_process` mode. It also detects `deleting`/`deleted` documents and completes non-delete jobs cleanly instead of running them.
- `recover_interrupted_documents()` clears stale `processing_job_id` values during startup and the worker's periodic stale sweep.
- The per-document `asyncio` lock in `src/document_store/worker.py` was removed; the SQLite lock is now the single source of truth.

## Settings schema refactor — `src/config.py` + `src/config_validation.py`

`src/config.py` was reduced from 499 to 326 lines by trimming verbose
multi-line comments to tight 1-line "why" notes, removing dead code, and
extracting the one genuinely relocatable helper. The refactor is a pure
cleanup — no env vars, defaults, validators, or public API symbols changed.

### What moved

- `normalize_filter_field_name(field: str) -> str` and its two constants
  (`_FILTER_FIELD_PATTERN`, `_FILTER_FIELD_MAX_LENGTH`) moved from
  `src/config.py` into the new `src/config_validation.py`. The function
  normalizes Qdrant payload filter field names (spaces/slashes/hyphens →
  underscores) and validates characters + length. It is imported locally
  inside `Settings.get_validated_allowed_filter_fields()` to keep module-load
  order clean.

### What stayed (and why)

- The four `@field_validator` methods (`validate_positive_int`,
  `validate_positive_timeout`, `validate_sqlite_journal_mode`,
  `validate_conversion_prompt_not_empty`) remain on the `Settings` class.
  pydantic v2 registers field validators on the class at decoration time, so
  they cannot be relocated to another module.
- `allowed_document_dirs_resolved` (property) and
  `get_validated_allowed_filter_fields` (cached method) stay on `Settings`
  because they depend on instance state.
- The bottom re-export block (`get_settings`, `reload_settings`,
  `reset_settings_singleton`, `get_collection_threshold`) is unchanged — 53
  files import these symbols from `src.config`, so the public API is preserved.

### Dead code removed

- `import logging` + `logger = logging.getLogger(__name__)` — `logger` had
  zero call sites in `config.py`.
- `import re` — only used by the moved helper.

### Minor fixes (approved in the plan)

- `from pathlib import Path` hoisted from a local import inside the
  `allowed_document_dirs_resolved` property to the top-level imports.

### Comment policy applied

- Each field keeps at most one 1-line "why" note. Comments that restated the
  field name or type were removed.
- Institutional knowledge (chunk-size A/B test result, four-layer KB defense
  thresholds, ingest-worker grace-period ordering) is preserved as 1-liners
  that point to `CLAUDE.md` for detail.
- Section group headers (e.g. `# --- Qdrant ---`) are retained for scannability.

### Tests

`tests/test_config.py` (42 tests) locks the behavior of
`normalize_filter_field_name`, `Settings.get_validated_allowed_filter_fields`
(including caching), `Settings.allowed_document_dirs_resolved`, and all four
field validators. The full suite (496 tests) passes unchanged.

## Retrieval filter and routing contracts

- `src/retrieval/filter_builder.py::QdrantFilterBuilder.relax_and_retry` treats
  metadata filters as precision hints, not hard recall requirements. By default,
  every filter except `document_id` may be relaxed, including a single filter;
  the final attempt can use an unfiltered Qdrant search. Callers must still
  preserve `document_id` unless they explicitly provide a different relaxation
  policy.
- `src/retrieval/schema_discovery.py::remember_categorical_value` records a
  categorical value confirmed by a targeted Qdrant lookup. Discovery failures
  are briefly cached to avoid repeating a full sample scan during an outage;
  the failure cache expires after five seconds and ingestion invalidation clears
  both caches.
- `src/registry_config/_categories.py` content markers are shared with the
  router's KB keyword set. A marker change can therefore affect both document
  category extraction and routing. Broad domain terms should not be added to a
  category classifier solely to improve routing; use a routing-only keyword when
  needed.
