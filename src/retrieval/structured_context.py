"""Context building and deterministic aggregation for structured datasets.

Formats records into compact prompt context lines and computes deterministic
dataset facts (counts, status breakdown, issuance/retirement totals) over all
scrolled records.
"""

from dataclasses import dataclass
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .structured_spec import StructuredListSpec


@dataclass
class _RecordTypeSchema:
    name_fields: list[str]
    name_label: str
    detail_fields: list[tuple[str, str]]


_RECORD_SCHEMAS: dict[str, _RecordTypeSchema] = {
    "program": _RecordTypeSchema(
        name_fields=["program_name"],
        name_label="Program",
        detail_fields=[("category", "Category"), ("status", "Status")],
    ),
    "methodology": _RecordTypeSchema(
        name_fields=["methodology_name", "title"],
        name_label="Methodology",
        detail_fields=[("program_name", "Program"), ("category", "Category"), ("status", "Status")],
    ),
    "registry": _RecordTypeSchema(
        name_fields=["title", "registry", "name"],
        name_label="Registry",
        detail_fields=[("category", "Category"), ("status", "Status")],
    ),
    "standard": _RecordTypeSchema(
        name_fields=["title", "standard", "name"],
        name_label="Standard",
        detail_fields=[("category", "Category"), ("status", "Status")],
    ),
}

# Fallback for self-host datasets whose record type is not in the VCM taxonomy.
_GENERIC_RECORD_SCHEMA = _RecordTypeSchema(
    name_fields=["title", "name", "source"],
    name_label="Record",
    detail_fields=[],
)

# Column-name aliases for dataset row fields. The row parser uses these to
# identify conceptual columns no matter what the uploaded CSV/JSON calls them.
# VCM labels are the primary aliases; the rest cover carbon markets, compliance,
# and general ESG datasets that self-host users may ingest.
_FIELD_ROLE_ALIASES: dict[str, list[str]] = {
    "id": [
        "project id", "project_id", "projectid",
        "record id", "record_id", "recordid",
        "issuance id", "issuance_id", "issuanceid",
        "reference id", "reference_id", "referenceid",
        "document id", "document_id", "documentid",
        "project number", "project_number",
    ],
    "name": [
        "project name", "project_name", "projectname",
        "name", "title", "project title", "project_title",
    ],
    "status": [
        "voluntary status", "status", "state", "project status",
        "assessment status", "assessment_status",
        "compliance status", "compliance_status",
    ],
    "country": [
        "country", "nation", "jurisdiction",
    ],
}

# Exact-only column names that are too short/substring-prone to use as aliases.
_EXACT_ROLE_NAMES: dict[str, set[str]] = {
    "id": {"id", "identifier"},
}

# Numeric column aliases and the canonical label used in fact strings.
# Most specific matches are listed first so "Total Credits Issued" maps to
# ``issued`` rather than the looser ``credits``.
_NUMERIC_CANONICALS: list[tuple[str, list[str]]] = [
    ("issued", ["total credits issued", "credits issued", "issued", "total issued"]),
    ("retired", ["total credits retired", "credits retired", "retired", "total retired"]),
    ("remaining", ["total credits remaining", "credits remaining", "remaining", "total remaining"]),
    ("allowances", ["allowances issued", "allowances", "allowance"]),
    ("volume", ["volume", "volumes"]),
    ("credits", ["credits", "credit"]),
    ("units", ["units", "unit"]),
    ("tonnes", ["tonnes", "tco2", "t co2"]),
    ("amount", ["amount", "quantity"]),
]

# Columns that contain a numeric keyword but are not summable.
_DATE_NUMERIC_EXCLUDES = {"date", "year", "registered", "effective", "start", "end", "created", "updated"}

# Rows shown as concrete examples in aggregate mode. Enough to establish that
# the numbers come from real records without paying for the full dump.
SAMPLE_ROW_COUNT = 10

_SCROLL_CAP_NOTE = (
    "Note: this dataset has more matching rows than the scroll cap, so "
    "the counts below are lower bounds. Say so: report them as \"at least N\"."
)

_LIST_TRUNCATION_NOTE = (
    "Note: the row list below was cut off at a size cap and is partial; "
    "do not claim it is complete. The record count above is still computed "
    "over all matching rows, not just the rows shown."
)

_SOURCE_TRUNCATION_NOTE = (
    "Note: the source file exceeded the ingestion row limit, so only a prefix "
    "of its rows was indexed. The counts below are lower bounds over the "
    "indexed rows, not the full dataset. Report them as \"at least N\"."
)


def _is_source_truncated(records: Iterable[Dict[str, Any]]) -> bool:
    """True when any scrolled row is marked as coming from a truncated source."""
    return any(
        bool((record.get("metadata") or {}).get("dataset_truncated"))
        for record in records
    )


def _get_nonempty_str(metadata: Dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = metadata.get(key)
        if value:
            text = str(value).strip()
            if text:
                return text
    return ""


def _normalize_field(field: str) -> str:
    """Lowercase a column name and collapse punctuation to spaces."""
    return re.sub(r"[^\w]+", " ", field).strip().lower()


def _field_role(field: str) -> Optional[str]:
    """Return the conceptual role (id/name/status/country) for a column, if any."""
    normalized = _normalize_field(field)
    for role, exact_names in _EXACT_ROLE_NAMES.items():
        if normalized in exact_names:
            return role
    for role, aliases in _FIELD_ROLE_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                return role
    return None


def _numeric_canonical(field: str) -> Optional[str]:
    """Return the canonical numeric label for a column, or None if not summable."""
    normalized = _normalize_field(field)
    if any(ex in normalized for ex in _DATE_NUMERIC_EXCLUDES):
        return None
    for canonical, aliases in _NUMERIC_CANONICALS:
        for alias in aliases:
            if alias in normalized:
                return canonical
    return None


def _parse_count(value: Optional[str]) -> Optional[float]:
    """Parse a signed decimal dataset field, tolerating thousands separators."""
    if not value:
        return None
    try:
        number = float(value.strip().replace(",", ""))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _format_total(value: float) -> str:
    """Format a summed total: trim float noise and a bare ``.0``."""
    rounded = round(value, 2)
    return str(int(rounded)) if rounded.is_integer() else str(rounded)


def _dataset_facts(
    rows: List[Dict[str, str]],
    total: int,
    record_label: str = "Records",
) -> List[str]:
    """Compute aggregates over every parsed dataset row.

    Counting and summing are deterministic operations — they are computed
    here, over every scrolled row, rather than delegated to the model over
    whatever rows happened to fit the context budget.
    """
    status_counts: Dict[str, int] = {}
    totals: Dict[str, float] = {}
    counts: Dict[str, int] = {}
    numeric_fields: set[str] = set()

    for fields in rows:
        for label, value in fields.items():
            role = _field_role(label)
            if role == "status" and value:
                status_counts[value] = status_counts.get(value, 0) + 1
            canonical = _numeric_canonical(label)
            if canonical is None:
                continue
            numeric_fields.add(canonical)
            amount = _parse_count(value)
            if amount is None:
                continue
            totals[canonical] = totals.get(canonical, 0.0) + amount
            if amount > 0:
                counts[canonical] = counts.get(canonical, 0) + 1

    facts = [f"Rows: {total}"]
    if status_counts:
        by_status = ", ".join(
            f"{status}={count}"
            for status, count in sorted(status_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        )
        facts.append(f"By status: {by_status}")

    if numeric_fields:
        # Totals line for the canonical credit/allowance/offset fields, appending
        # any additional carbon-market numeric columns (volume, units, etc.).
        if "issued" in numeric_fields:
            main_parts = [f"total issued={_format_total(totals.get('issued', 0.0))}"]
            for canon in ("retired", "remaining"):
                if canon in numeric_fields:
                    main_parts.append(f"{canon}={_format_total(totals.get(canon, 0.0))}")

            extra: List[str] = []
            for canon in sorted(numeric_fields):
                if canon not in ("issued", "retired", "remaining"):
                    extra.append(f"total {canon}={_format_total(totals.get(canon, 0.0))}")
            # "Projects" keeps the VCM phrasing for backward compatibility.
            issued_phrase = "credits issued" if record_label == "Projects" else "issued totals"
            line = f"{record_label} with {issued_phrase}: {counts.get('issued', 0)}; "
            line += ", ".join(main_parts)
            if extra:
                line += ", " + ", ".join(extra)
            facts.append(line)
        else:
            # No credit-style fields; emit a generic numeric totals line.
            generic_parts = [
                f"total {canon}={_format_total(totals.get(canon, 0.0))}"
                for canon in sorted(numeric_fields)
            ]
            facts.append("Numeric totals: " + ", ".join(generic_parts))

    return facts


def _format_row_line(fields: Dict[str, str]) -> Optional[str]:
    """Build a single human-readable line from parsed row fields."""
    if not fields:
        return None

    roles: Dict[str, Optional[str]] = {}
    for label in fields:
        roles[label] = _field_role(label)

    id_label = next(
        (label for label, role in roles.items() if role == "id"),
        None,
    )
    if not id_label:
        return None

    name_label = next(
        (label for label, role in roles.items() if role == "name"),
        None,
    )

    ordered = [id_label]
    if name_label:
        ordered.append(name_label)
    ordered += [
        label for label in fields
        if label not in ordered and (_field_role(label) or _numeric_canonical(label))
    ]

    details = [f"{label}: {fields[label]}" for label in ordered if fields.get(label)]
    return ". ".join(details) + "." if details else None


def _row_from_metadata(record: Dict[str, Any]) -> Tuple[Any, Optional[Dict[str, str]], Optional[str]]:
    """Return ``(dedup_key, fields, line)`` from typed row_data metadata."""
    metadata = record.get("metadata") or {}
    row_data = metadata.get("row_data")
    if not row_data:
        return None, None, None
    fields = {str(k): str(v).strip() if v is not None else "" for k, v in row_data.items()}
    line = _format_row_line(fields)
    return metadata.get("row_id") or record.get("json_index", 0), fields, line


def _schema_line(
    record: Dict[str, Any],
    schema: _RecordTypeSchema,
) -> Tuple[Any, Optional[str]]:
    """Format a metadata-driven record. Returns ``(dedup_key, line or None)``."""
    metadata = record.get("metadata") or {}
    name = _get_nonempty_str(metadata, schema.name_fields)
    source = metadata.get("source", "")
    key = (name, source)
    if not name:
        return key, None
    details = [f"{schema.name_label}: {name}"]
    for field, field_label in schema.detail_fields:
        value = _get_nonempty_str(metadata, [field])
        if value:
            details.append(f"{field_label}: {value}")
    return key, ". ".join(details) + "."


def build_structured_context(
    records: Iterable[Dict[str, Any]],
    spec: StructuredListSpec,
    *,
    hit_scroll_cap: bool = False,
    max_chars: Optional[int] = None,
) -> Tuple[str, int]:
    """Build compact context from filtered Qdrant records, shaped by ``spec.mode``.

    Dataset rows are read from typed ``row_data`` in the Qdrant payload
    metadata. This function formats them into human-readable lines and
    computes deterministic aggregates (counts, status breakdowns, totals)
    over the full scrolled result.

    The three modes produce different context:

    ``aggregate``
        Facts header plus at most :data:`SAMPLE_ROW_COUNT` example rows. The
        user asked a question about the rows, not for the rows, so shipping
        the full dump would cost thousands of tokens the answer cannot use.
    ``supplement``
        Facts header only, for prepending to normal vector results.
    ``enumerate``
        Every record, subject to ``max_chars``. Used for small entity
        inventories where the list *is* the answer.

    Args:
        records: Iterable of dicts, each with ``"json_index"`` (int) and
            ``"metadata"`` (dict). The metadata dict should contain the
            fields named in the schema for ``spec.record_type``. Dataset
            rows additionally need ``"row_data"`` and ``"row_id"``.
        spec: The ``StructuredListSpec`` that produced these records.
        hit_scroll_cap: Whether more rows matched than were scrolled. Counts
            then become lower bounds and the model is told to say so.
        max_chars: Size budget for ``enumerate`` mode. When a record line
            would exceed it, remaining records are dropped at a whole-line
            boundary and a note is added — never cut mid-line or silently.

    Returns:
        ``(context_text, unique_count)`` — the formatted context string and
        the number of unique records parsed.
    """
    schema = _RECORD_SCHEMAS.get(spec.record_type) or _GENERIC_RECORD_SCHEMA

    # Dataset rows are now stored as typed row_data in metadata. The qdrant_filter
    # is the most reliable signal for which formatter to use: doc_type=dataset.
    is_dataset_row = spec.qdrant_filter.get("doc_type") == "dataset"
    record_label = (spec.record_label or ("Projects" if is_dataset_row else "Records")).capitalize()

    normalized = sorted(
        list(records),
        key=lambda r: (r.get("json_index") or 0),
    )

    seen: set = set()
    row_lines: List[str] = []
    fact_rows: List[Dict[str, str]] = []
    for record in normalized:
        if is_dataset_row:
            key, fields, line = _row_from_metadata(record)
        else:
            fields = None
            key, line = _schema_line(record, schema)
        if line is None or key in seen:
            continue
        seen.add(key)
        row_lines.append(line)
        if fields is not None:
            fact_rows.append(fields)

    total = len(seen)
    source_truncated = _is_source_truncated(normalized)
    scope = "at least" if (hit_scroll_cap or source_truncated) else "all"
    facts_header = (
        f"Dataset facts for {spec.display_name} "
        f"(computed over {scope} {total} matching rows):"
    )

    if spec.mode in ("aggregate", "supplement"):
        lines = [facts_header, *(f"- {fact}" for fact in _dataset_facts(fact_rows, total, record_label))]
        if hit_scroll_cap:
            lines.append(_SCROLL_CAP_NOTE)
        if source_truncated:
            lines.append(_SOURCE_TRUNCATION_NOTE)
        if spec.mode == "aggregate" and row_lines:
            shown = row_lines[:SAMPLE_ROW_COUNT]
            lines.append(
                f"Example records ({len(shown)} of {total}, for illustration only — "
                "the counts above are the answer, these rows are not):"
            )
            lines.extend(shown)
        return "\n".join(lines), total

    lines = [
        f"{'Partial' if source_truncated else 'Complete'} dataset: "
        f"{spec.display_name} ({total} records)."
    ]
    if hit_scroll_cap:
        lines.append(_SCROLL_CAP_NOTE)
    if source_truncated:
        lines.append(_SOURCE_TRUNCATION_NOTE)
    if is_dataset_row:
        lines.append(facts_header)
        lines.extend("- " + fact for fact in _dataset_facts(fact_rows, total, record_label))

    # Reserve room for the truncation note in case a later line forces it.
    budget = max_chars - len(_LIST_TRUNCATION_NOTE) - 1 if max_chars is not None else None
    truncated = False
    current_len = sum(len(line) + 1 for line in lines)
    for line in row_lines:
        if budget is not None and current_len + len(line) + 1 > budget:
            truncated = True
            break
        lines.append(line)
        current_len += len(line) + 1

    if truncated:
        lines.insert(1, _LIST_TRUNCATION_NOTE)

    return "\n".join(lines), total
