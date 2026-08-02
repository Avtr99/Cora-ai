"""Docling model-warmup heuristic and first-run download notice.

Tracks whether Docling standard-conversion model weights have been loaded in
this process. The first standard PDF conversion may download ~670MB of
models; we emit a job status update so the user sees a download is happening
instead of a frozen converter.

The ``_docling_models_warmed`` flag is a **process-level singleton**: once any
standard conversion completes, subsequent conversions skip the notice. It
lives here (not in ``handlers.py``) so the read-side helpers
(``_docling_models_cached``, ``_maybe_emit_docling_download_notice``) can use
``global`` on it. The write side (handlers, after a successful conversion)
mutates it via ``docling_warmup._docling_models_warmed = True`` so the change
is visible to all importers of this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import get_settings
from .models import DocumentRecord
from .storage import update_job

# Process-level flag: once a Docling standard conversion has completed in this
# process, model weights are cached in memory and (usually) on disk, so we stop
# emitting the "downloading models" notice for subsequent conversions.
_docling_models_warmed = False


def _docling_models_cached() -> Optional[bool]:
    """Heuristic: are Docling model artifacts already on disk?

    Returns True if ``DOCLING_ARTIFACTS_PATH`` is set and non-empty, False if it is
    set but missing/empty, and None when the path is unset (unknown -- rely on the
    process-level warmed flag instead).
    """
    artifacts = get_settings().DOCLING_ARTIFACTS_PATH
    if not artifacts:
        return None
    p = Path(artifacts)
    return p.exists() and any(p.iterdir())


def _maybe_emit_docling_download_notice(job_id: str, record: DocumentRecord) -> None:
    """Emit a 'downloading models' job status update before the first standard PDF
    conversion when models aren't yet cached, so the user sees a download is
    happening instead of a frozen converter."""
    global _docling_models_warmed
    if record.conversion_mode != "standard" or record.extension.lower() != ".pdf":
        return
    if _docling_models_warmed:
        return
    cached = _docling_models_cached()
    if cached is True:
        _docling_models_warmed = True
        return
    update_job(
        job_id,
        "processing",
        "Downloading Docling models (first run only, ~670MB). This may take several minutes.",
    )
