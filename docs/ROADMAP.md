# Cora AI Roadmap

This file tracks planned work that has been scoped but not yet scheduled for
implementation. Items move out of this file into the active backlog when they
are picked up. Each entry includes the rationale, scope, and acceptance
criteria so an implementer (human or agent) can pick it up without re-deriving
the design.

## Active Candidates


### Add SearXNG and Serper as web search providers

**Status:** Planned — not yet scheduled.
**Owner:** Unassigned.
**Target component:** `src/agents/search_providers.py`, `src/agents/orchestrator.py`,
`src/api/settings_routes/search.py`, `src/api/settings_routes/status.py`,
`src/config.py`, `.env.example`, frontend settings UI.

#### Rationale

Web search currently supports only Tavily (paid API) and `none` (disabled).
Adding two more providers gives operators meaningful choice and strengthens
the local-first philosophy:

1. **SearXNG** — self-hostable, no API key, fully open source. Aligns with
   Cora's local-first design: an operator who already runs Qdrant and the
   backend locally can also run their own search metasearch engine with zero
   external dependencies and zero cost.
2. **Serper** — Google results via a simple REST API with a generous free tier
   (2,500 searches/month). A good commercial alternative to Tavily for
   operators who want Google-quality results without self-hosting.

#### Scope

- Create `SearXNGSearchProvider` in `src/agents/searxng_search.py`.
  SearXNG exposes a JSON API (`GET /search?format=json&q=<query>`) on any
  self-hosted instance. Configure via `SEARXNG_URL` env var.
- Create `SerperSearchProvider` in `src/agents/serper_search.py`.
  Serper uses `POST https://google.serper.dev/search` with an API key header.
  Configure via `SERPER_API_KEY` env var.
- Update `SEARCH_PROVIDER` valid values in:
  - `src/agents/orchestrator.py` — add `elif` branches for `searxng` and `serper`.
  - `src/api/settings_routes/search.py` — add to `valid_providers` tuple.
  - `src/api/settings_routes/status.py` — add config checks for each provider.
- Update `.env.example` with `SEARXNG_URL` and `SERPER_API_KEY` examples.
- Update frontend settings UI to show the new providers in the dropdown.
- Update README provider configuration section.

#### Acceptance criteria

- [ ] `SEARCH_PROVIDER=searxng` with `SEARXNG_URL=http://localhost:8080`
      returns search results from a local SearXNG instance.
- [ ] `SEARCH_PROVIDER=serper` with `SERPER_API_KEY=<key>` returns Google
      results.
- [ ] `SEARCH_PROVIDER=none` still disables web search (unchanged).
- [ ] `SEARCH_PROVIDER=tavily` still works (unchanged).
- [ ] Unknown provider falls back to a clear error, not a silent default.
- [ ] `/v1/settings/status` reports correct `search_ready` for each provider.
- [ ] `.env.example` and README updated.
- [ ] `ruff check src/` clean.
