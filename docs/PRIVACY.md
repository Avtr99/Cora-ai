# Privacy Policy

**Last updated:** July 2026

## 1. Introduction

This Privacy Policy is an operator-completed template. It describes how Cora AI (the "Service") handles information when you use this self-hosted Voluntary Carbon Market (VCM) research assistant. The default-behaviour description of the software is preserved below; operators must fill in the bracketed placeholders with their deployment-specific details before publishing this policy.

Cora AI is designed as a local-first application: by default, all data processing and storage occurs on the machine where the application is deployed. We are committed to protecting your privacy and supporting compliance with the General Data Protection Regulation (GDPR) and other applicable data protection laws.

Because Cora AI is open-source and self-hosted, the operator (the person or organization running the instance) is the data controller. Operators are responsible for ensuring compliance with their local laws and may need to adapt this policy to their specific deployment.

### Controller Information

- **Controller name:** [CONTROLLER_NAME]
- **Controller address:** [CONTROLLER_ADDRESS]
- **Controller email:** [CONTROLLER_EMAIL]
- **Controller phone (optional):** [CONTROLLER_PHONE]

## 2. Information Collected and Stored

### Local-First Data Storage

Cora AI does not require user accounts or logins. All data is stored locally on the machine where the instance is deployed, using SQLite (for caches and metadata) and Qdrant (for vector embeddings and conversation memory). No data leaves the machine unless an external API provider is explicitly configured.

### Conversation History

- **Chat messages:** Your conversations are stored in the local Qdrant instance under the `cora_memories` collection. User identifiers are HMAC-hashed before storage, pseudonymizing them and reducing the direct linkability of conversation history.
- **Session data:** Chat sessions are stored locally in your browser via local storage. You can clear this at any time from your browser settings.

### Query and Cache Data

- **Query cache:** Previous queries and answers are cached in a local SQLite database (`backend_cache` table) with a 24-hour TTL to improve response times. Cached data is not sent anywhere.
- **Embedding cache:** Embedding vectors for processed documents are stored in a local SQLite table (`embedding_cache`) to avoid redundant API calls.

### Uploaded Documents

- **Document content:** Files you upload are processed locally, chunked, and stored as vector embeddings in the local Qdrant instance. The original files and extracted text are stored on the local filesystem.
- **Document metadata:** Metadata such as filename, file type, registry, and document ID is extracted and stored in SQLite and Qdrant payloads.

### PII Redaction

Personally identifiable information (PII) is automatically detected and redacted before being stored in conversation memory. This feature is enabled by default (`PII_REDACTION_ENABLED=true`) and covers names, emails, phone numbers, credit card numbers, and other common PII patterns. Redacted content is replaced with type-tagged placeholders (e.g. `[NAME]`, `[EMAIL]`).

**Note:** Cora AI does not collect IP addresses, browser fingerprints, or location data. No analytics or tracking are included in the default deployment.

## 3. External API Providers (Optional)

By default, Cora AI operates entirely locally. However, the operator may configure external API providers for AI inference, embeddings, web search, and PDF conversion. When enabled, the following data is sent to the configured provider:

- **LLM provider (e.g. Gemini, OpenAI, OpenRouter):** User queries and retrieved document chunks are sent to generate answers.
- **Embedding provider (e.g. Voyage, Cohere, OpenAI):** Text chunks from uploaded documents and user queries are sent to generate vector embeddings.
- **Web search provider (e.g. Tavily):** Reformulated queries are sent to fetch web search results for time-sensitive or non-KB questions.
- **PDF conversion API (llm_api mode):** PDF page images are sent to the configured vision-language model for OCR and layout extraction.

All external providers are configurable via environment variables. The operator can switch to fully local alternatives (e.g. Ollama for LLM and embeddings, Docling for PDF conversion) to keep all data on-machine. See the `.env.example` file and project documentation for configuration details.

**Important:** When external API providers are enabled, the operator is responsible for reviewing the privacy policy and data handling practices of those providers and ensuring compliance with applicable laws.

Other recipients or external providers the operator may use: [RECIPIENTS_OR_EXTERNAL_PROVIDERS]

## 4. How Data Is Used

Data is processed solely for the following purposes:

- **Answer generation:** Retrieve relevant document chunks and generate responses to user queries.
- **Conversation context:** Maintain chat history to provide contextual follow-up answers within a session.
- **Performance optimization:** Cache previous results to reduce response times and avoid redundant API calls.
- **Document retrieval:** Index uploaded documents for semantic search.

No data is used for advertising, profiling, or sold to third parties. No telemetry or usage analytics are collected by the application itself.

The operator may add additional processing purposes and legal bases:

- **Processing purposes:** [PROCESSING_PURPOSES]
- **Legal bases:** [LEGAL_BASES]

## 5. Data Security

Cora AI implements the following security measures:

- **Local storage:** All data remains on the operator's machine by default. No external databases or cloud services are required.
- **PII redaction:** Automatic detection and redaction of personal identifiers before storage in conversation memory.
- **HMAC-hashed user IDs:** User identifiers are hashed before being stored in the memory collection, pseudonymizing them and reducing direct linkability to individuals.
- **API key isolation:** API keys are stored either in the gitignored local `.env` file or in the SQLite database used by the setup wizard. In both cases, operators should protect the file and any backups, and keys are never committed to version control.
- **Optional API authentication:** The operator can enable API key authentication to restrict access to the service.
- **Input sanitization:** HTML content in responses is sanitized via `nh3`. This does not protect against SQL, command, prompt, or other input-injection types.

**Note:** Because Cora AI is self-hosted, physical and network security of the deployment machine is the operator's responsibility. We recommend running the application behind a reverse proxy with TLS encryption if exposed to a network.

## 6. Your GDPR Rights

Under GDPR and similar regulations, you have the following rights regarding data stored in a Cora AI instance:

- **Right to Access:** Request information about data stored in the local databases. The operator can query SQLite and Qdrant directly.
- **Right to Rectification:** Request correction of inaccurate data stored in the system.
- **Right to Erasure (Right to be Forgotten):** You can clear your chat history from your browser at any time. The operator can delete conversation memories via the `DELETE /v1/memory/delete` API endpoint or by clearing the Qdrant `cora_memories` collection.
- **Right to Data Portability:** Data can be exported from SQLite (standard SQL dumps) and Qdrant (via the Qdrant API) in machine-readable formats.
- **Right to Object:** Object to processing by disabling the relevant features (e.g. disable conversation memory via configuration).

To exercise these rights, contact the operator of the Cora AI instance you are using.

## 7. Data Retention

Data retention is controlled by the operator. The default behaviour is:

- **Chat history:** Stored in the browser's local storage until cleared by the user. Conversation memory in Qdrant persists until explicitly deleted.
- **Query cache:** Automatically expires after 24 hours.
- **Embedding cache:** Persists until the corresponding documents are deleted or the database is cleared.
- **Uploaded documents:** Persist until explicitly deleted by the operator via the document store UI or API.

The operator can configure retention policies and schedule periodic cleanup as needed for their compliance requirements.

## 8. Children's Privacy

Cora AI is not intended for use by children under the age of 16. The service does not knowingly collect personal data from children. If you believe a child has provided personal information to a Cora AI instance, contact the operator to have it removed.

## 9. Changes to This Policy

This Privacy Policy may be updated as the project evolves. Changes will be posted in the project repository and the "Last Updated" date will be revised. Operators are encouraged to review the policy periodically.

## 10. Contact

If you have questions about this Privacy Policy or how data is handled, please contact the operator of the Cora AI instance you are using:

- **Controller name:** [CONTROLLER_NAME]
- **Controller address:** [CONTROLLER_ADDRESS]
- **Controller email:** [CONTROLLER_EMAIL]
- **Controller phone (optional):** [CONTROLLER_PHONE]

For questions about the project itself, refer to the project repository or contact `hello@cora-ai.org`.
