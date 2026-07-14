# Cora AI System Card

## Model Overview

- **System name:** Cora AI
- **Version:** See `CHANGELOG.md` and Git tags in the repository.
- **Developer / Owner:** Akshay Rajesh
- **Contact:** hello@cora-ai.org
- **License:** Apache 2.0
- **Repository:** https://github.com/Avtr99/Cora-ai

Cora is a local-first, self-hostable multi-agent RAG (Retrieval-Augmented Generation) system for the Voluntary Carbon Market (VCM). It answers user questions grounded in uploaded documents, with citations and optional web search augmentation. Cora does not train or fine-tune models; it uses pre-trained, pluggable third-party models via API or local inference.

## Intended Use

- **Primary intended uses:** Educational question-answering on VCM documents, including methodologies, standards, registry documents, and project data. It helps users understand, compare, and trace claims back to source documents.
- **Intended users:** Sustainability analysts, carbon-market researchers, registry staff, project developers, and learners.
- **Out-of-scope uses:**
  - Financial, legal, or compliance decisions without independent verification.
  - Real-time market trading or automated pricing.
  - Substitute for authoritative registry records or legal documents.
  - General-purpose chatbot use outside the configured document domain.

## System Architecture

Cora is built around a modular, provider-agnostic pipeline:

- **LLM provider** (answer generation, routing, query rewriting): Pluggable. Default is Google Gemini 2.5 Flash via `google-genai`. Alternatives include OpenAI, OpenRouter, Ollama, vLLM, LM Studio, or any OpenAI-compatible endpoint.
- **Embedding provider:** Pluggable. Default is Voyage `voyage-4-lite` (1024d). Alternatives include Cohere, OpenAI, and Ollama (local).
- **Reranker:** Pluggable. Default is Voyage `rerank-2.5`. Alternatives include Cohere rerank or `none` (fully offline).
- **Vector store:** Qdrant (local Docker or self-hosted).
- **Persistent cache and state:** SQLite.
- **Web search:** Optional. Default is Tavily. Can be disabled (`SEARCH_PROVIDER=none`) for offline use.
- **Document parsing:** Docling classical pipeline (local CPU) by default. Optional `llm_api` mode for complex layouts can be pointed at a local vLLM server.
- **Orchestration:** Multi-agent pipeline (QueryRewriter → Router → RouteProcessor → Answer + optional Validator).

See `docs/ARCHITECTURE.md` and `README.md` for full architecture diagrams and deployment details.

## Data

Cora does not use a training dataset and does not fine-tune models. The data flow is:

1. **User-uploaded documents** (PDFs, CSVs, etc.) are parsed, chunked, and stored in a local Qdrant vector store.
2. **Queries** are embedded and matched against the local vector store.
3. **Retrieved chunks** are passed to the LLM to generate a cited answer.
4. **Optional web search** fetches public snippets when local documents are insufficient.

There is no external data collection beyond user-provided documents and optional search snippets. By default, all persistent state lives locally (SQLite + Qdrant). No training data is collected or redistributed.

## Chunking and Retrieval Configuration

- **Chunk size:** 1500 characters
- **Chunk overlap:** 300 characters
- **Top-K after reranking:** 15
- **Rerank score threshold:** 0.2
- **KB minimum top relevance score:** 0.4

The chunk size and overlap were selected through an internal A/B test. The test compared chunk sizes of 600, 800, 1000, 1200, 1500, and 2000 characters across 15 representative VCM queries. An OpenRouter Gemini judge scored each configuration for faithfulness and completeness. The 1500/300 configuration minimized hedging and performed best on the combined metric. This is documented in the `CHUNK_SIZE` / `CHUNK_OVERLAP` block in `src/config.py` and in `.env.example`.

## Performance Metrics and Evaluation

Cora is evaluated with the following metrics and scripts:

| Metric | Purpose | Location |
|---|---|---|
| RAGAS Faithfulness | Measures whether the answer is grounded in retrieved context | `scripts/evaluation/evaluate_rag.py` |
| RAGAS Answer Relevancy | Measures whether the answer addresses the question | `scripts/evaluation/evaluate_rag.py` |
| RAGAS Context Precision | Measures relevance of retrieved chunks | `scripts/evaluation/evaluate_rag.py` |
| RAGAS Context Recall | Measures coverage of relevant retrieved chunks | `scripts/evaluation/evaluate_rag.py` |
| Grounding Overlap Score | Cheap, no-LLM token-overlap heuristic between answer and citations | `src/evaluation/grounding_metrics.py` |
| Latency | Query response time | `scripts/evaluation/evaluate_rag.py` |

To run the evaluation:

```bash
python scripts/evaluation/evaluate_rag.py --dataset scripts/evaluation/test_queries.json
```

Test queries are provided in `scripts/evaluation/test_queries.json`. Evaluation output files are generated locally and are not committed (they are excluded by `.gitignore` because they may contain user documents and API-dependent results). The evaluation methodology and scripts are in the repository.

## Limitations and Failure Modes

- **Hallucination:** The LLM can generate plausible but incorrect or unsupported statements. Users are instructed to verify responses against the cited sources.
- **Coverage gaps:** The system can only answer from the documents in the knowledge base. If the topic is not covered, it falls back to web search or reports that the information is not found.
- **Citation errors:** The model may cite a document that is topically adjacent but does not directly answer the question.
- **Provider dependency:** Quality and availability depend on the configured LLM/embedding provider. Local providers may be slower or less capable than cloud providers.
- **Document quality:** OCR and table extraction quality depend on the PDF conversion mode and the source document quality.
- **Currency:** The system does not automatically update documents. Users must re-ingest documents to reflect new versions.

## Biases and Known Issues

- **Model bias:** Responses may reflect biases in the underlying pre-trained LLM or in the uploaded documents.
- **Domain bias:** The system is optimized for VCM terminology and registry patterns. Performance on unrelated domains depends on reconfiguring the collection description and registry patterns.
- **Language:** Default models are strongest in English. Multilingual performance depends on the chosen provider and model.
- **Methodology code extraction:** The grounding metric uses a regex tuned for VCM methodology codes (VM, VMD, ACM, AMS, CDM, AR, GS). It may not generalize to other code systems.

## Environmental Impact

Cora does not train models. Energy use is limited to inference, document parsing, and embedding generation. The carbon footprint depends on the selected provider and hardware:

- Local CPU inference with Docling and Ollama has negligible cloud footprint.
- Cloud API providers (Gemini, Voyage, OpenAI, etc.) incur emissions at the provider's data centers.

## Licensing and Redistribution

Cora is released under the Apache 2.0 License. Third-party models and APIs are used under their respective provider terms. See `NOTICE` and `LICENSE` for details.
