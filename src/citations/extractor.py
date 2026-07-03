"""Citation extraction from retrieval provider payloads."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .config import CitationConfig
from .models import Citation, VectorResults, WebResults
from .source_name import clean_source_name
from .source_type import SourceTypeResolver
from ..retrieval.score_utils import normalize_score, DistanceMetric


class CitationExtractor:
    """Extracts citations from vector and web provider results."""

    def __init__(
        self,
        config: CitationConfig,
        safe_metadata_fields: Set[str],
        source_type_resolver: Optional[SourceTypeResolver] = None,
    ) -> None:
        self.config = config
        self.safe_metadata_fields = safe_metadata_fields
        self.source_type_resolver = source_type_resolver or SourceTypeResolver(config)

    def extract_from_vector_results(
        self,
        vector_results: Dict[str, Any],
        max_citations: Optional[int] = None,
    ) -> List[Citation]:
        citations: List[Citation] = []
        typed = VectorResults.from_dict(vector_results)
        limit = max_citations if max_citations is not None else self.config.max_kb_citations

        # Resolve distance metric from retrieval results, fallback to cosine distance.
        try:
            metric = DistanceMetric(typed.distance_metric) if typed.distance_metric else DistanceMetric.COSINE_DISTANCE
        except ValueError:
            metric = DistanceMetric.COSINE_DISTANCE

        for index, document in enumerate(typed.documents):
            if index >= limit:
                break

            metadata = typed.metadatas[index]
            # Prefer the explicit similarity score from the retriever when it is
            # available (e.g., from a reranker). Fall back to normalizing raw
            # distances, which may be cosine distance or 1 - similarity.
            if typed.scores and index < len(typed.scores):
                relevance_score = max(0.0, min(1.0, float(typed.scores[index])))
            else:
                distance = typed.distances[index]
                relevance_score = normalize_score(distance, metric)
            if relevance_score < self.config.min_relevance_score:
                continue

            raw_source_name = (
                metadata.get("file_name")
                or metadata.get("parent_doc")
                or metadata.get("source")
                or f"Document {index + 1}"
            )
            source_name = clean_source_name(raw_source_name) or raw_source_name

            snippet = (
                document[: self.config.snippet_max_length] + "..."
                if len(document) > self.config.snippet_max_length
                else document
            )

            safe_metadata = {k: v for k, v in metadata.items() if k in self.safe_metadata_fields}
            citations.append(
                Citation(
                    source_id=metadata.get("id", f"doc_{index}"),
                    source_name=source_name,
                    source_type="knowledge_base",
                    content_snippet=snippet,
                    relevance_score=round(relevance_score, 3),
                    page_number=metadata.get("page_number"),
                    section=metadata.get("section"),
                    url=metadata.get("url"),
                    metadata=safe_metadata,
                )
            )

        return citations

    def extract_from_web_results(
        self,
        web_results: Dict[str, Any],
        max_citations: Optional[int] = None,
    ) -> List[Citation]:
        citations: List[Citation] = []
        typed = WebResults.from_dict(web_results)
        limit = max_citations if max_citations is not None else self.config.max_web_citations

        for index, source in enumerate(typed.sources):
            if index >= limit:
                break

            raw_score = source.relevance_score
            if raw_score is None:
                raw_score = source.score
            if raw_score is None:
                raw_score = max(0.0, 1.0 - (index * self.config.rank_decay_factor))

            raw_score = max(0.0, min(1.0, raw_score))
            if raw_score < self.config.min_relevance_score:
                continue

            metadata = source.metadata if isinstance(source.metadata, dict) else {}
            safe_metadata = {k: v for k, v in metadata.items() if k in self.safe_metadata_fields}

            source_type = self.source_type_resolver.resolve(metadata, source.title, source.url)
            citation_url = source.url if source_type == "web" else None

            raw_snippet = source.snippet or ""
            content_snippet = raw_snippet[: self.config.snippet_max_length]

            # Sanitize source name consistently with vector results path
            source_name = clean_source_name(source.title) or source.title

            citations.append(
                Citation(
                    source_id=f"web_{index}",
                    source_name=source_name,
                    source_type=source_type,
                    content_snippet=content_snippet,
                    relevance_score=round(raw_score, 3),
                    url=citation_url,
                    metadata=safe_metadata,
                )
            )

        return citations
