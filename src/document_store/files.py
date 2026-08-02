"""Filesystem I/O for converted markdown and metadata sidecars.

Thin helpers around the on-disk artifacts produced during ingestion: reading
the converted markdown back for indexing, writing the JSON metadata sidecar
used for debugging, and removing both when a document is deleted.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import DocumentRecord
from .schema import document_root


def read_markdown(record: DocumentRecord) -> str:
    if not record.converted_path:
        raise FileNotFoundError("Converted text is not ready")
    path = Path(record.converted_path)
    if not path.exists():
        raise FileNotFoundError("Converted text is not available")
    return path.read_text(encoding="utf-8")


def _atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically using a temp file + os.replace.

    A crash or power loss during the write leaves the original file (if any)
    untouched and the temp file can be cleaned up on the next operation.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temp_path, path)
    except Exception:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
        raise


def write_metadata_file(record: DocumentRecord) -> None:
    root = document_root()
    metadata_path = root / "metadata" / f"{record.id}.json"
    _atomic_write_text(metadata_path, json.dumps(record.to_api(), indent=2))


def remove_document_files(record: DocumentRecord) -> None:
    for value in (record.original_path, record.converted_path):
        if value:
            Path(value).unlink(missing_ok=True)
    root = document_root()
    (root / "metadata" / f"{record.id}.json").unlink(missing_ok=True)
