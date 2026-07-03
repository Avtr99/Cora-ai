"""
Score normalization utilities for retrieval results.

Different vector stores and distance metrics produce scores on different
scales.  This module provides consistent normalization so that threshold
comparisons (e.g. min_relevance_score) are predictable regardless of the
underlying distance function.

Supported distance metrics:
  - Cosine distance (Qdrant default): 0 = identical, 2 = opposite
  - Euclidean / L2 distance: 0 = identical, unbounded upper
  - Dot product / inner product: higher = better (can be negative)
  - Cosine similarity: [-1, 1], higher = better

Adapted from GuidelineCopilot's distance_to_score with additional
normalization strategies for different distance metrics.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Optional


class DistanceMetric(str, Enum):
    """Known distance metric types for score normalization."""

    COSINE_DISTANCE = "cosine_distance"       # Qdrant default: 0..2, lower=better
    EUCLIDEAN = "euclidean"                    # L2: 0..∞, lower=better
    DOT_PRODUCT = "dot_product"                # inner product: -∞..∞, higher=better
    COSINE_SIMILARITY = "cosine_similarity"    # -1..1, higher=better
    UNKNOWN = "unknown"                         # fallback


def normalize_score(
    raw_score: float,
    metric: DistanceMetric = DistanceMetric.COSINE_DISTANCE,
) -> float:
    """
    Normalize a raw retrieval score to a [0.0, 1.0] similarity score
    where 1.0 = best match and 0.0 = no match.

    Args:
        raw_score: The raw score/distance from the vector store.
        metric: The distance metric used by the store.

    Returns:
        Float in [0.0, 1.0].  Higher = more similar.
    """
    if math.isnan(raw_score) or math.isinf(raw_score):
        return 0.0

    if metric == DistanceMetric.COSINE_DISTANCE:
        # Cosine distance: 0 = identical, 2 = opposite
        # Convert: score = 1 - (d / 2), clamped to [0, 1]
        return max(0.0, min(1.0, 1.0 - raw_score / 2.0))

    if metric == DistanceMetric.EUCLIDEAN:
        # Euclidean: 0 = identical, unbounded
        # Use inverse: score = 1 / (1 + d)
        # This is the GuidelineCopilot formula, works well in practice
        d = max(0.0, raw_score)
        return max(0.0, min(1.0, 1.0 / (1.0 + d)))

    if metric == DistanceMetric.DOT_PRODUCT:
        # Dot product: higher = better, range depends on vectors
        # Normalize via sigmoid-like mapping: score = 1 / (1 + exp(-x))
        # Centered at 0 so dot=0 → 0.5
        try:
            return max(0.0, min(1.0, 1.0 / (1.0 + math.exp(-raw_score))))
        except OverflowError:
            return 1.0 if raw_score > 0 else 0.0

    if metric == DistanceMetric.COSINE_SIMILARITY:
        # Cosine similarity: -1..1, higher=better
        # Map: score = (sim + 1) / 2 → [0, 1]
        return max(0.0, min(1.0, (raw_score + 1.0) / 2.0))

    # UNKNOWN: assume cosine-distance-like (Qdrant default)
    return max(0.0, min(1.0, 1.0 - raw_score / 2.0))


def distance_to_score(distance: float) -> float:
    """
    Convenience function: convert a generic distance value to [0,1] similarity.

    Uses the inverse formula 1/(1+d) which works well for both cosine
    and euclidean distances.  This is the GuidelineCopilot formula.

    Args:
        distance: Non-negative distance value (lower = more similar).

    Returns:
        Float in [0.0, 1.0].
    """
    d = float(distance)
    if not math.isfinite(d):
        return 0.0
    d = max(0.0, d)
    return max(0.0, min(1.0, 1.0 / (1.0 + d)))


def infer_metric_from_collection(
    _collection_name: Optional[str] = None,
) -> DistanceMetric:
    """
    Infer the likely distance metric from collection configuration.

    Qdrant's default for cosine vectors is COSINE_DISTANCE.
    This can be overridden if the collection uses a different metric.

    Args:
        collection_name: Optional collection name (for future config lookup).

    Returns:
        Best-guess DistanceMetric enum value.
    """
    # Qdrant default with Voyage embeddings is cosine
    return DistanceMetric.COSINE_DISTANCE
