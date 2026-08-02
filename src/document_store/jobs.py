"""Backwards-compatible re-export facade for the document store job layer.

The implementation has been split into cohesive submodules:

- :mod:`.dispatch`        -- job dispatch (in_process BackgroundTasks vs worker queue)
- :mod:`.errors`          -- conversion error classification
- :mod:`.handlers`        -- process/reindex/delete job handlers + shared helpers
- :mod:`.docling_warmup`  -- Docling model-warmup heuristic and first-run notice

This module re-exports every public name that previously lived here so all
existing ``from src.document_store.jobs import X`` import sites (worker,
routes, tests) keep working unchanged. Tests that patch by module path must
target ``src.document_store.handlers.<name>`` (not ``src.document_store.jobs``)
for the imported converter/indexer/storage names the handlers look up at call
time -- see the plan file for the full list of patch-site updates.
"""

from __future__ import annotations

from .dispatch import (
    JobHandler,
    raise_if_conversion_unavailable,
    schedule_ingestion_job,
)
from .errors import _classify_conversion_error  # noqa: F401
from .handlers import (
    _process_document_job_inner,  # noqa: F401 -- patched by tests via handlers module
    delete_document_job,
    process_document_job,
    reindex_document_job,
)

__all__ = [
    "JobHandler",
    "raise_if_conversion_unavailable",
    "schedule_ingestion_job",
    "_classify_conversion_error",
    "process_document_job",
    "reindex_document_job",
    "delete_document_job",
    "_process_document_job_inner",
]
