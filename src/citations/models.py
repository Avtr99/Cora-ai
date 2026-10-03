"""Typed data models for citation processing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass
class Citation:
    """Represents a single citation with source information.

    ``index`` is the prompt position (``N`` in ``<source index="N">`` /
    ``[cite_kb: N]`` / ``[Web, cite: N]`` markers). ``None`` for citations
    that exist without a marker (e.g. a structured dataset).

    ``marker_type`` is the marker namespace the index belongs to —
    ``"knowledge_base"`` or ``"web"``. A web result can carry
    ``source_type="knowledge_base"`` (file-like display classification) while
    still being numbered among web results, so the namespace is recorded
    explicitly; it falls back to ``source_type`` when unset.

    ``document_key`` is the identity of the underlying document — the doc
    store ID for KB chunks, the URL for web results — used only to group
    chunks of the same document for display.
    """

    source_id: str
    source_name: str
    source_type: str
    content_snippet: str
    relevance_score: float
    page_number: Optional[int] = None
    section: Optional[str] = None
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    index: Optional[int] = None
    marker_type: Optional[str] = None
    document_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Citation":
        """Rebuild a Citation from a ``to_dict()`` payload, tolerating missing keys."""
        return cls(
            source_id=str(data.get("source_id", "")),
            source_name=str(data.get("source_name", "")),
            source_type=str(data.get("source_type", "knowledge_base")),
            content_snippet=str(data.get("content_snippet", "")),
            relevance_score=float(data.get("relevance_score") or 0.0),
            page_number=data.get("page_number"),
            section=data.get("section"),
            url=data.get("url"),
            metadata=data.get("metadata"),
            index=data.get("index"),
            marker_type=data.get("marker_type"),
            document_key=data.get("document_key"),
        )

    def to_display_format(self) -> str:
        parts = [self.source_name]
        if self.page_number is not None:
            parts.append(f"p. {self.page_number}")
        if self.section is not None:
            parts.append(f"§ {self.section}")
        if self.url:
            parts.append(f"({self.url})")
        return ", ".join(parts)


@dataclass
class VectorResults:
    """Typed shape for vector retrieval payloads."""

    documents: List[str]
    metadatas: List[Dict[str, Any]]
    distances: List[float]
    distance_metric: Optional[str] = None
    scores: List[float] = None

    def __post_init__(self) -> None:
        if not (len(self.documents) == len(self.metadatas) == len(self.distances)):
            raise ValueError("documents, metadatas, and distances must have equal length")
        if self.scores is None:
            self.scores = []

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "VectorResults":
        data = payload or {}
        documents_raw = data.get("documents") or []
        metadatas_raw = data.get("metadatas") or []
        distances_raw = data.get("distances") or []
        scores_raw = data.get("scores")

        documents = [str(doc) if doc is not None else "" for doc in documents_raw]
        metadatas = [m if isinstance(m, dict) else {} for m in metadatas_raw]

        distances: List[float] = []
        for value in distances_raw:
            try:
                distances.append(float(value))
            except (TypeError, ValueError):
                distances.append(1.0)

        scores: List[float] = []
        if scores_raw is not None:
            for value in scores_raw:
                try:
                    scores.append(float(value))
                except (TypeError, ValueError):
                    scores.append(0.0)

        max_len = max(len(documents), len(metadatas), len(distances), 0)
        if len(documents) < max_len:
            documents.extend([""] * (max_len - len(documents)))
        if len(metadatas) < max_len:
            metadatas.extend([{} for _ in range(max_len - len(metadatas))])
        if len(distances) < max_len:
            distances.extend([1.0] * (max_len - len(distances)))
        if scores and len(scores) < max_len:
            scores.extend([0.0] * (max_len - len(scores)))

        distance_val = data.get("distance_metric")
        distance_metric = distance_val if isinstance(distance_val, str) else None

        return cls(documents=documents, metadatas=metadatas, distances=distances, distance_metric=distance_metric, scores=scores)


@dataclass
class WebSource:
    """Typed web source item from search providers."""

    title: str
    url: str = ""
    snippet: str = ""
    relevance_score: Optional[float] = None
    score: Optional[float] = None
    explicit_type: str = ""
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_any(cls, value: Any, index: int) -> "WebSource":
        if isinstance(value, str):
            return cls(title=value)

        if not isinstance(value, dict):
            return cls(title=f"Web Source {index + 1}")

        relevance_score = _to_optional_float(value.get("relevance_score"))
        score = _to_optional_float(value.get("score"))
        return cls(
            title=str(value.get("title", f"Web Source {index + 1}")),
            url=str(value.get("url", "")),
            snippet=str(value.get("snippet", "")),
            relevance_score=relevance_score,
            score=score,
            explicit_type=str(value.get("type", "")).strip().lower(),
            metadata=dict(value) if isinstance(value, dict) else {},
        )


@dataclass
class WebResults:
    """Typed web search payload."""

    sources: List[WebSource]

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> "WebResults":
        data = payload or {}
        raw_sources = data.get("sources") or []
        sources = [WebSource.from_any(source, idx) for idx, source in enumerate(raw_sources)]
        return cls(sources=sources)


def _to_optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
