# Product

## Register

product

## Users

Sustainability analysts, carbon-market researchers, registry staff, and technical operators working with the Voluntary Carbon Market (VCM). They use Cora to answer complex questions grounded in authoritative documents (registries, standards, methodologies, project docs) and to explore project-level data. They are often domain-knowledgeable but time-constrained, so they value clarity, speed, and trust over novelty.

## Product Purpose

Cora is a local-first, self-hostable multi-agent RAG backend and React SPA that answers VCM queries grounded in a local Qdrant vector store of documents. It makes institutional knowledge searchable and verifiable, with citations, conversation memory, and optional web augmentation. Success means a user can drop a set of documents in, build a knowledge base once, and get accurate, cited answers without wrestling with configuration.

## Brand Personality

Expert, trustworthy, calm, precise. Cora should feel like a capable colleague who has already read the documents and knows where to look. The interface favors clarity over persuasion, and restraint over decoration.

## Anti-references

- Generic AI chat interfaces that look like a blank conversation bubble with a glowing send button.
- Dark-mode dashboards with neon accents and glassmorphism.
- Marketing landing pages with hero metrics, gradient text, and dense feature grids.
- Complex admin panels with nested sidebars, tabs, and buried actions.
- Generic SaaS card grids that all look like the same AI-generated template.

## Design Principles

- **Show the source, not just the answer.** Citations, document previews, and status visibility are first-class because trust depends on provenance.
- **One task per screen, one clear action per step.** Avoid configuration noise; progressive disclosure for advanced options.
- **Local-first confidence.** The UI should feel solid and fast even though the backend is running locally; avoid patterns that imply a fragile cloud dependency.
- **Consistency with the existing data surfaces.** Projects, Pricing, and the Document Store should share the same visual language, spacing, and interaction patterns so the product feels like one tool.
- **Respect the user's time.** No welcome paragraphs, no repeated explanations, no marketing copy in product screens.

## Accessibility & Inclusion

- Target WCAG 2.1 AA.
- Respect `prefers-reduced-motion`.
- Maintain keyboard navigability and visible focus states throughout the upload, list, and preview flows.
