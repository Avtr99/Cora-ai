"""Citation extraction from web search provider payloads.

KB citations are built by ``context.build_kb_context`` alongside the prompt so
they share the prompt's own numbering — this module handles web results only.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .config import CitationConfig, SAFE_METADATA_FIELDS
from .models import Citation, WebResults
from .source_name import clean_source_name
from .source_type import SourceTypeResolver


class CitationExtractor:
    """Extracts citations from web provider results."""

    def __init__(
        self,
        config: CitationConfig,
        source_type_resolver: Optional[SourceTypeResolver] = None,
    ) -> None:
        self.config = config
        self.source_type_resolver = source_type_resolver or SourceTypeResolver(config)

    def extract_from_web_results(
        self,
        web_results: Dict[str, Any],
    ) -> List[Citation]:
        """One citation per prompt result.

        ``index = position + 1`` matches the ``source_{i+1}`` numbering the web
        prompt and ``parse_citations`` use. There is no cap and no relevance
        threshold: every result shown to the model is citable.
        """
        citations: List[Citation] = []
        typed = WebResults.from_dict(web_results)

        for index, source in enumerate(typed.sources):
            position = index + 1

            raw_score = source.relevance_score
            if raw_score is None:
                raw_score = source.score
            relevance_score = (
                max(0.0, min(1.0, float(raw_score))) if raw_score is not None else 1.0
            )

            metadata = source.metadata if isinstance(source.metadata, dict) else {}
            safe_metadata = {k: v for k, v in metadata.items() if k in SAFE_METADATA_FIELDS}

            source_type = self.source_type_resolver.resolve(metadata, source.title, source.url)
            citation_url = source.url if source_type == "web" else None

            raw_snippet = source.snippet or ""
            content_snippet = raw_snippet[: self.config.snippet_max_length]

            # Sanitize source name consistently with the KB context path
            source_name = clean_source_name(source.title) or source.title

            citations.append(
                Citation(
                    source_id=f"web_{position}",
                    source_name=source_name,
                    source_type=source_type,
                    content_snippet=content_snippet,
                    relevance_score=round(relevance_score, 3),
                    url=citation_url,
                    metadata=safe_metadata,
                    index=position,
                    marker_type="web",
                    document_key=source.url or None,
                )
            )

        return citations
