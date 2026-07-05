# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Open-source release of Cora AI, a local-first RAG assistant for the Voluntary Carbon Market.
- Multi-route RAG orchestrator (knowledge base, web search, hybrid, conversational).
- Pluggable providers for LLM, embeddings, reranker, and web search.
- Document ingestion with local Docling pipeline or optional LLM API conversion.
- Streaming and async query endpoints.
- Conversation memory with HMAC-hashed user IDs.
- Citation extraction and HTML sanitization for provenance.
- Docker Compose setup for local deployment.

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
- Pinned Dockerfile base images by SHA256 digest (`node:22-alpine`, `python:3.11-slim`) for supply-chain integrity. Digest updates handled automatically by Dependabot docker ecosystem.
- Generated hash-pinned lockfiles via `uv pip compile --generate-hashes` targeting `x86_64-unknown-linux-gnu`/Python 3.11: `requirements-core.lock`, `requirements-ingestion.lock` (CPU torch via PyTorch index), `requirements-ci.lock` (core + ingestion + dev). Dockerfile and CI now install with `pip install --require-hashes` for verified reproducible builds.
- Added OpenSSF Baseline Best Practices badge to README (project 13501 on bestpractices.dev). Detected by Scorecard's CII-Best-Practices check.
- CI workflow runs on both `pull_request` and `push` to main (defense-in-depth for direct pushes / admin bypass). The push trigger will become redundant once branch protection requires PRs (Phase 2). SAST (CodeQL) runs independently via GitHub built-in scanning and is unaffected.

### Fixed

- Fixed CI/Docker torch binary mismatch: regenerated `requirements-ci.lock` with `--index-strategy unsafe-best-match --extra-index-url https://download.pytorch.org/whl/cpu` so CI pins `torch==2.12.1+cpu` / `torchvision==0.27.1+cpu`, matching the Docker image. CI install command updated to pass the PyTorch CPU index.
- Fixed import ordering in `scripts/docker/download_docling_models.py` (moved `Path` usage after docling imports).
- Resolved merge conflict in `.pre-commit-config.yaml` — kept `scripts/evaluation/` exclusion (production scripts under `scripts/docker/` are still linted).
