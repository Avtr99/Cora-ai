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
