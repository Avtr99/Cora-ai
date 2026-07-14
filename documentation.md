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

This is called in three places:
- `src/agents/route_processors.py:_finalize_citations` (KB, Web routes)
- `src/agents/orchestrator.py` (sync orchestrator)
- `src/agents/streaming_orchestrator.py` (streaming orchestrator, final result event only)
- `src/agents/hybrid_route_handler.py` (hybrid route, after `grounded_citations`)

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

- `src/query_processing/citation_verifier.py` (added `renumber_citation_markers`)
- `src/agents/route_processors.py` (call renumber after filter)
- `src/agents/orchestrator.py` (call renumber after filter)
- `src/agents/streaming_orchestrator.py` (call renumber after filter)
- `src/agents/hybrid_route_handler.py` (call renumber after filter)
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
```
