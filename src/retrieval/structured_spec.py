"""Specification data model for structured dataset queries."""

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

StructuredMode = Literal["enumerate", "aggregate", "supplement"]


@dataclass
class StructuredListSpec:
    """Describe a metadata-filtered dataset requested by a user.

    Attributes:
        source: Source identifier for logging / traceability.
        status: Status filter value (e.g. ``"CCP-Eligible"``), or ``""``.
        record_type: Entity type — ``"program"``, ``"methodology"``,
            ``"project"``, ``"standard"``, or ``"registry"``.
        display_name: Human-readable label used in prompt context.
        qdrant_filter: Key-value pairs for the Qdrant payload scroll filter.
            Keys are metadata field names (without the ``metadata.`` prefix).
        mode: What the user asked for, which determines what the context
            contains and what the model is told to do with it:

            ``"enumerate"``
                The user asked for the list itself ("list all CCP approved
                programs"). Every record is emitted and the model is told to
                list them all. Only used for small entity inventories.
            ``"aggregate"``
                The user asked a question *about* the rows ("how many VM0047
                projects are registered"). Every matching row is scrolled so
                the counts are exact, but only the computed facts plus a
                bounded sample reach the prompt. The model leads with the
                totals and asks which subset the user wants next.
            ``"supplement"``
                The question needs normal retrieval; the dataset only grounds
                a premise. An aggregates-only facts block is prepended to
                vector results and web supplementation stays available.
    """

    source: str
    status: str
    record_type: str
    display_name: str
    qdrant_filter: Dict[str, Any]
    mode: StructuredMode = "enumerate"
    record_label: Optional[str] = None
