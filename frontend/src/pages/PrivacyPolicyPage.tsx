import React from 'react';
import LegalPageLayout from '@/components/layout/LegalPageLayout';
import LegalSection from '@/components/ui/LegalSection';

/**
 * Privacy Policy for Cora AI — a self-hosted, local-first application.
 *
 * This policy reflects the local-first architecture: all data stays on the
 * operator's machine unless they explicitly configure external API providers.
 */
const PrivacyPolicyPage: React.FC = () => {
  return (
    <LegalPageLayout title="Privacy Policy" lastUpdated="July 2026">

      <LegalSection title="Introduction" number={1}>
        <p>
          This Privacy Policy describes how Cora AI (the "Service") handles information when you use
          this self-hosted Voluntary Carbon Market (VCM) research assistant. Cora AI is designed as a
          local-first application: by default, all data processing and storage occurs on the machine
          where the application is deployed. We are committed to protecting your privacy and ensuring
          compliance with the General Data Protection Regulation (GDPR) and other applicable data
          protection laws.
        </p>
        <p>
          Because Cora AI is open-source and self-hosted, the operator (the person or organization
          running the instance) is the data controller. This policy describes the default behaviour
          of the software. Operators are responsible for ensuring compliance with their local laws
          and may need to adapt this policy to their specific deployment.
        </p>
      </LegalSection>

      <LegalSection title="Information Collected and Stored" number={2}>
        <p className="font-semibold text-brand-primary">Local-First Data Storage</p>
        <p>
          Cora AI does not require user accounts or logins. All data is stored locally on the
          machine where the instance is deployed, using SQLite (for caches and metadata) and Qdrant
          (for vector embeddings and conversation memory). No data leaves the machine unless an
          external API provider is explicitly configured.
        </p>

        <p className="font-semibold text-brand-primary pt-2">Conversation History</p>
        <ul>
          <li><strong>Chat messages:</strong> Your conversations are stored in the local Qdrant
            instance under the <code>cora_memories</code> collection. User identifiers are
            HMAC-hashed before storage for GDPR compliance.</li>
          <li><strong>Session data:</strong> Chat sessions are stored locally in your browser via
            local storage. You can clear this at any time from your browser settings.</li>
        </ul>

        <p className="font-semibold text-brand-primary pt-2">Query and Cache Data</p>
        <ul>
          <li><strong>Query cache:</strong> Previous queries and answers are cached in a local
            SQLite database (<code>backend_cache</code> table) with a 24-hour TTL to improve
            response times. Cached data is not sent anywhere.</li>
          <li><strong>Embedding cache:</strong> Embedding vectors for processed documents are stored
            in a local SQLite table (<code>embedding_cache</code>) to avoid redundant API calls.</li>
        </ul>

        <p className="font-semibold text-brand-primary pt-2">Uploaded Documents</p>
        <ul>
          <li><strong>Document content:</strong> Files you upload are processed locally, chunked,
            and stored as vector embeddings in the local Qdrant instance. The original files and
            extracted text are stored on the local filesystem.</li>
          <li><strong>Document metadata:</strong> Metadata such as filename, file type, registry,
            and document ID is extracted and stored in SQLite and Qdrant payloads.</li>
        </ul>

        <p className="font-semibold text-brand-primary pt-2">PII Redaction</p>
        <p>
          Personally identifiable information (PII) is automatically detected and redacted before
          being stored in conversation memory. This feature is enabled by default
          (<code>PII_REDACTION_ENABLED=true</code>) and covers names, emails, phone numbers, credit
          card numbers, and other common PII patterns. Redacted content is replaced with
          type-tagged placeholders (e.g. <code>[NAME]</code>, <code>[EMAIL]</code>).
        </p>

        <p className="text-xs text-text-muted pt-1">
          <strong>Note:</strong> Cora AI does not collect IP addresses, browser fingerprints, or
          location data. No analytics or tracking are included in the default deployment.
        </p>
      </LegalSection>

      <LegalSection title="External API Providers (Optional)" number={3}>
        <p>
          By default, Cora AI operates entirely locally. However, the operator may configure
          external API providers for AI inference, embeddings, web search, and PDF conversion.
          When enabled, the following data is sent to the configured provider:
        </p>
        <ul>
          <li><strong>LLM provider (e.g. Gemini, OpenAI, OpenRouter):</strong> User queries and
            retrieved document chunks are sent to generate answers.</li>
          <li><strong>Embedding provider (e.g. Voyage, Cohere, OpenAI):</strong> Text chunks from
            uploaded documents and user queries are sent to generate vector embeddings.</li>
          <li><strong>Web search provider (e.g. Tavily):</strong> Reformulated queries are sent to
            fetch web search results for time-sensitive or non-KB questions.</li>
          <li><strong>PDF conversion API (llm_api mode):</strong> PDF page images are sent to the
            configured vision-language model for OCR and layout extraction.</li>
        </ul>
        <p>
          All external providers are configurable via environment variables. The operator can switch
          to fully local alternatives (e.g. Ollama for LLM and embeddings, Docling for PDF
          conversion) to keep all data on-machine. See the <code>.env.example</code> file and
          project documentation for configuration details.
        </p>
        <p className="text-xs text-text-muted pt-1">
          <strong>Important:</strong> When external API providers are enabled, the operator is
          responsible for reviewing the privacy policy and data handling practices of those
          providers and ensuring compliance with applicable laws.
        </p>
      </LegalSection>

      <LegalSection title="How Data Is Used" number={4}>
        <p>Data is processed solely for the following purposes:</p>
        <ul>
          <li><strong>Answer generation:</strong> Retrieve relevant document chunks and generate
            responses to user queries.</li>
          <li><strong>Conversation context:</strong> Maintain chat history to provide contextual
            follow-up answers within a session.</li>
          <li><strong>Performance optimization:</strong> Cache previous results to reduce response
            times and avoid redundant API calls.</li>
          <li><strong>Document retrieval:</strong> Index uploaded documents for semantic search.</li>
        </ul>
        <p>
          No data is used for advertising, profiling, or sold to third parties. No telemetry or
          usage analytics are collected by the application itself.
        </p>
      </LegalSection>

      <LegalSection title="Data Security" number={5}>
        <p>Cora AI implements the following security measures:</p>
        <ul>
          <li><strong>Local storage:</strong> All data remains on the operator's machine by default.
            No external databases or cloud services are required.</li>
          <li><strong>PII redaction:</strong> Automatic detection and redaction of personal
            identifiers before storage in conversation memory.</li>
          <li><strong>HMAC-hashed user IDs:</strong> User identifiers are hashed before being stored
            in the memory collection, preventing direct association with individuals.</li>
          <li><strong>API key isolation:</strong> All API keys are stored in a local
            <code>.env</code> file that is gitignored and never committed to version control.</li>
          <li><strong>Optional API authentication:</strong> The operator can enable API key
            authentication to restrict access to the service.</li>
          <li><strong>Input sanitization:</strong> All user inputs are sanitized to prevent
            injection attacks. HTML content in responses is sanitized via nh3.</li>
        </ul>
        <p className="text-xs text-text-muted pt-1">
          <strong>Note:</strong> Because Cora AI is self-hosted, physical and network security of
          the deployment machine is the operator's responsibility. We recommend running the
          application behind a reverse proxy with TLS encryption if exposed to a network.
        </p>
      </LegalSection>

      <LegalSection title="Your GDPR Rights" number={6}>
        <p>
          Under GDPR and similar regulations, you have the following rights regarding data stored in
          a Cora AI instance:
        </p>
        <ul>
          <li><strong>Right to Access:</strong> Request information about data stored in the local
            databases. The operator can query SQLite and Qdrant directly.</li>
          <li><strong>Right to Rectification:</strong> Request correction of inaccurate data stored
            in the system.</li>
          <li><strong>Right to Erasure (Right to be Forgotten):</strong> You can clear your chat
            history from your browser at any time. The operator can delete conversation memories via
            the <code>DELETE /v1/memory/delete</code> API endpoint or by clearing the Qdrant
            <code>cora_memories</code> collection.</li>
          <li><strong>Right to Data Portability:</strong> Data can be exported from SQLite (standard
            SQL dumps) and Qdrant (via the Qdrant API) in machine-readable formats.</li>
          <li><strong>Right to Object:</strong> Object to processing by disabling the relevant
            features (e.g. disable conversation memory via configuration).</li>
        </ul>
        <p>
          To exercise these rights, contact the operator of the Cora AI instance you are using.
        </p>
      </LegalSection>

      <LegalSection title="Data Retention" number={7}>
        <p>
          Data retention is controlled by the operator. The default behaviour is:
        </p>
        <ul>
          <li><strong>Chat history:</strong> Stored in the browser's local storage until cleared by
            the user. Conversation memory in Qdrant persists until explicitly deleted.</li>
          <li><strong>Query cache:</strong> Automatically expires after 24 hours.</li>
          <li><strong>Embedding cache:</strong> Persists until the corresponding documents are
            deleted or the database is cleared.</li>
          <li><strong>Uploaded documents:</strong> Persist until explicitly deleted by the operator
            via the document store UI or API.</li>
        </ul>
        <p>
          The operator can configure retention policies and schedule periodic cleanup as needed for
          their compliance requirements.
        </p>
      </LegalSection>

      <LegalSection title="Children's Privacy" number={8}>
        <p>
          Cora AI is not intended for use by children under the age of 16. The service does not
          knowingly collect personal data from children. If you believe a child has provided
          personal information to a Cora AI instance, contact the operator to have it removed.
        </p>
      </LegalSection>

      <LegalSection title="Changes to This Policy" number={9}>
        <p>
          This Privacy Policy may be updated as the project evolves. Changes will be posted in the
          project repository and the "Last Updated" date will be revised. Operators are encouraged
          to review the policy periodically.
        </p>
      </LegalSection>

      <LegalSection title="Contact" number={10}>
        <p>
          If you have questions about this Privacy Policy or how data is handled, please contact the
          operator of the Cora AI instance you are using. For questions about the project itself,
          refer to the project repository or the contact information provided in the README.
        </p>
      </LegalSection>

    </LegalPageLayout>
  );
};

export default PrivacyPolicyPage;
