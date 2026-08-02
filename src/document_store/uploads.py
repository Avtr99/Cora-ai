"""Upload saving, MIME validation, and tag/filename helpers.

The entry point is ``save_upload``: streams an ``UploadFile`` to disk under
the document store root, validates magic bytes against the declared
extension, dedups by SHA-256, and inserts the document record. The tag and
filename helpers normalize user-supplied metadata before it reaches the DB.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Iterable, Optional

from fastapi import UploadFile

from ..config import get_settings
from .files import write_metadata_file
from .models import ConversionMode, DocumentRecord
from .repository import find_by_sha256, insert_document
from .schema import (
    _EXPECTED_MIME_PREFIXES,
    _SAFE_FILENAME_CHARS,
    allowed_extensions,
    document_root,
    ensure_document_store_tables,
)


def normalize_tags(raw_tags: Optional[Iterable[str]]) -> list[str]:
    if raw_tags is None:
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for value in raw_tags:
        tag = str(value).strip().lower()
        if not tag or len(tag) > 64 or tag in seen:
            continue
        tags.append(tag)
        seen.add(tag)
    return tags[:20]


def parse_tags(raw: Optional[str]) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return normalize_tags(str(item) for item in parsed)
    except json.JSONDecodeError:
        pass
    return normalize_tags(part for part in raw.split(","))


def safe_original_filename(filename: Optional[str]) -> str:
    fallback = "document"
    cleaned = _SAFE_FILENAME_CHARS.sub("_", (filename or fallback).strip()).strip("._")
    return cleaned or fallback


def _validate_upload_mime(extension: str, first_chunk: bytes, declared_mime: Optional[str]) -> None:
    """Check that the uploaded file's magic bytes match its declared extension.

    ponytail: Uses python-magic if available; on import failure, skips validation
    so a missing libmagic DLL doesn't block uploads. Declared MIME is ignored --
    it is client-controlled and trivially spoofed.
    """
    try:
        import magic
    except Exception:
        return

    detected = magic.from_buffer(first_chunk, mime=True)
    expected = _EXPECTED_MIME_PREFIXES.get(extension)
    if expected and not detected.startswith(expected):
        raise ValueError(
            f"File content ({detected}) does not match extension {extension}"
        )


async def save_upload(file: UploadFile, conversion_mode: ConversionMode, tags: list[str]) -> DocumentRecord:
    ensure_document_store_tables()
    root = document_root()
    filename = safe_original_filename(file.filename)
    extension = Path(filename).suffix.lower()
    if extension not in allowed_extensions():
        raise ValueError(f"Unsupported file type: {extension or 'unknown'}")

    settings = get_settings()
    max_bytes = int(settings.DOCUMENT_UPLOAD_MAX_BYTES)
    max_mb = max_bytes // (1024 * 1024)
    too_large = f"File is too large (limit: {max_mb} MB). Reduce the file size or increase DOCUMENT_UPLOAD_MAX_BYTES in your .env file."

    # Up-front size check when the client provides Content-Length.
    content_length = None
    if file.headers and "content-length" in file.headers:
        try:
            content_length = int(file.headers["content-length"])
        except ValueError:
            content_length = None
    if content_length is not None and content_length > max_bytes:
        raise ValueError(too_large)

    doc_id = f"doc_{uuid.uuid4().hex[:16]}"
    stored_filename = f"{doc_id}{extension}"
    original_path = root / "originals" / stored_filename
    temp_path = root / "originals" / f"{doc_id}.tmp"
    converted_path = root / "converted" / f"{doc_id}.md"

    digest = hashlib.sha256()
    size = 0
    first_chunk: Optional[bytes] = None
    try:
        with temp_path.open("wb") as handle:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                if first_chunk is None:
                    first_chunk = chunk
                    _validate_upload_mime(extension, first_chunk, file.content_type)
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError(too_large)
                digest.update(chunk)
                handle.write(chunk)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    sha256_hex = digest.hexdigest()
    existing = find_by_sha256(sha256_hex)
    if existing is not None:
        temp_path.unlink(missing_ok=True)
        raise FileExistsError(
            f"A document with the same content already exists: {existing.original_filename}"
        )

    original_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp_path, original_path)

    record = DocumentRecord(
        id=doc_id,
        original_filename=filename,
        stored_filename=stored_filename,
        mime_type=file.content_type or "application/octet-stream",
        extension=extension,
        size_bytes=size,
        sha256=sha256_hex,
        status="queued",
        conversion_mode=conversion_mode,
        original_path=str(original_path),
        converted_path=str(converted_path),
        tags=tags,
    )
    insert_document(record)
    write_metadata_file(record)
    return record
