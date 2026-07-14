from __future__ import annotations

from typing import Optional

import asyncio
import threading

from ..config import get_settings

# Process-level ingestion concurrency guard. Docling standard parsing is CPU/RAM
# intensive and embeddings are network-bound; processing all uploaded documents at
# once thrashes the host and can hit embedding API rate limits. The cap keeps the
# rest of the app responsive while still saturating hardware.
_ingestion_sem: Optional[asyncio.Semaphore] = None
_ingestion_sem_lock = threading.Lock()


def _get_ingestion_sem() -> asyncio.Semaphore:
    global _ingestion_sem
    if _ingestion_sem is not None:
        return _ingestion_sem
    with _ingestion_sem_lock:
        if _ingestion_sem is not None:
            return _ingestion_sem
        _ingestion_sem = asyncio.Semaphore(
            max(1, get_settings().DOCUMENT_INGESTION_CONCURRENCY)
        )
        return _ingestion_sem
