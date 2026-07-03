# Content Moderation Policy

**Last updated:** July 2026

This document describes how Cora AI handles inappropriate, misleading, and illegal
content, in accordance with DPG Standard Indicator 9b.

## 1. Overview

Cora AI is a **self-hosted, local-first application**. The software itself does not
autonomously collect, distribute, or moderate content. All content is controlled by
the **operator** — the person or organization running the instance. The operator
uploads documents, configures API providers, and manages user access.

The software *enables* the operator to store and retrieve content locally. It does
not transmit content to any external party unless the operator explicitly configures
external API providers (LLM, embeddings, web search). In the default configuration,
all content remains on the operator's machine.

## 2. Content Stored by the Software

When the operator uses a Cora AI instance, the following content may be stored
locally on the deployment machine:

| Type | How it gets stored | Where it lives | Exposed to external services? |
|------|-------------------|----------------|-------------------------------|
| **Uploaded documents** | Operator uploads via UI or API | Local filesystem + Qdrant (local) | Only if operator configures external LLM/embedding API |
| **AI-generated responses** | Generated at query time | SQLite cache (24h TTL) | Only the query text is sent to external LLM if configured |
| **Conversation memory** | Stored during chat sessions | Qdrant `cora_memories` collection (local) | Never — memory stays in local Qdrant |

**Key point:** No content leaves the machine unless the operator explicitly sets
`GEMINI_API_KEY`, `OPENAI_API_KEY`, `VOYAGE_API_KEY`, `TAVILY_API_KEY`, or similar
environment variables. The fully offline configuration (`EMBEDDING_PROVIDER=ollama`,
`SEARCH_PROVIDER=none`) keeps everything local.

## 3. Mechanisms for Identifying Inappropriate Content

### 3.1 Uploaded Documents

The operator is the content moderator for their instance. The following mechanisms
are available:

- **Operator review:** The document store UI (`/documents`) provides a full list of
  uploaded documents. The operator can review, preview, and delete any document at
  any time via the UI or the `DELETE /v1/documents/{id}` API.
- **Bulk deletion:** The operator can clear all documents via
  `DELETE /v1/documents` to remove all content from the instance.
- **No automatic upload scanning:** Cora AI does not include automated detection of
  illegal content (e.g. CSAM) in uploaded files. The operator is responsible for
  reviewing uploads. If automated scanning is required, the operator should integrate
  a dedicated content safety service.

### 3.2 AI-Generated Responses

- **Prompt-level safeguards:** The system prompts instruct the AI model to refuse
  generating content that is illegal, harmful, or offensive. The prompts use
  XML-structured instructions (`<system_role>`, `<instructions>`) with explicit
  refusal directives.
- **PII redaction:** All conversation memory is filtered through the PII redactor
  (`src/memory/pii_redactor.py`) before storage, preventing personal information from
  being persisted or retrieved in future responses.
- **Input sanitization:** User queries are sanitized
  (`src/api/middleware/input_sanitizer.py`) to prevent prompt injection attacks that
  could manipulate the AI into generating harmful content.
- **HTML sanitization:** All AI-generated HTML in responses is sanitized via nh3
  (`src/citations/sanitizer.py`) to prevent XSS and malicious content injection.

### 3.3 Conversation Memory

- **PII redaction (automatic):** Enabled by default
  (`PII_REDACTION_ENABLED=true`). Detects and redacts names, emails, phone numbers,
  credit card numbers, SSNs, and other common PII patterns before storage.
- **Memory deletion:** Users can request memory deletion via the
  `DELETE /v1/memory/delete` API endpoint (requires authorization token). The
  operator can also clear the entire memory collection from Qdrant.

## 4. Processes for Detecting, Moderating, Reporting, and Removing Content

| Action | Process |
|--------|---------|
| **Detect** | Operator manually reviews uploaded documents via the document store UI. AI responses are safeguarded by prompt-level refusal directives and input sanitization. |
| **Moderate** | Operator can delete any document via the UI or API. AI responses are ephemeral (24h cache TTL) and not persisted long-term. |
| **Report** | Users who encounter inappropriate content should report it to the operator of the instance. The project repository's issue tracker can be used for project-level concerns. |
| **Remove** | Operator deletes the document via `DELETE /v1/documents/{id}`. For bulk removal, `DELETE /v1/documents` clears all documents. Memory entries can be deleted via `DELETE /v1/memory/delete`. |

## 5. Operator Responsibilities

Because Cora AI is self-hosted, the operator is the data controller and content
moderator. The operator is responsible for:

1. **Reviewing uploaded content** periodically and removing any inappropriate or
   illegal material.
2. **Monitoring AI responses** for quality and safety, especially when configuring
   custom system prompts or using different LLM providers.
3. **Complying with local laws** regarding content moderation, data retention, and
   reporting obligations.
4. **Providing a contact method** to their users for content-related complaints. The
   operator should publish their contact information on their deployment (e.g. in the
   Privacy Policy page or a dedicated contact page).

## 6. Limitations

- Cora AI does not include automated CSAM detection, terrorism content detection, or
  copyright infringement detection. Operators who need these capabilities should
  integrate dedicated third-party content safety services.
- The AI model's refusal of harmful content depends on the configured LLM provider.
  Different providers may have different safety characteristics. Operators should
  evaluate their chosen provider's safety features.
- This policy applies to the default Cora AI deployment. Modified deployments may
  require an updated policy.

## 7. Contact

For questions about this content moderation policy as it applies to a specific
deployment, contact the **operator of that instance**. The operator's contact
information should be provided on their deployment.

For questions about the Cora AI project itself (the open-source software), refer to
the project repository or the contact information in the `NOTICE` file.
