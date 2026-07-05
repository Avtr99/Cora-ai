# =============================================================================
# Stage 1: Build the Vite React Frontend
# =============================================================================
# Pinned by digest (multi-arch manifest list) for supply-chain integrity.
# Update via Dependabot (docker ecosystem) — it will bump the tag + digest together.
FROM node:22-alpine@sha256:16e22a550f3863206a3f701448c45f7912c6896a62de43add43bb9c86130c3e2 AS frontend-builder

WORKDIR /app/frontend

# Copy dependency manifests first for better layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source and build
COPY frontend/ ./
RUN npm run build

# =============================================================================
# Stage 2: Python Backend (serves API + built SPA)
# =============================================================================
# Pinned by digest (multi-arch manifest list) for supply-chain integrity.
# Update via Dependabot (docker ecosystem) — it will bump the tag + digest together.
FROM python:3.14-slim@sha256:b877e50bd90de10af8d82c57a022fc2e0dc731c5320d762a27986facfc3355c1 AS backend

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOME=/app/data \
    HF_HOME=/app/data/.cache/huggingface \
    HF_DATASETS_CACHE=/app/data/.cache/datasets \
    DOCLING_ARTIFACTS_PATH=/app/models/docling

WORKDIR /app

# System dependencies (curl for healthcheck; native libs for document conversion)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libglib2.0-0 \
    libgl1 \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (better layer caching)
# Core runtime is installed separately so it can be cached independently of
# the heavy ingestion stack.
# Lockfiles are generated with `uv pip compile --generate-hashes` and installed
# with --require-hashes for supply-chain integrity (Scorecard Pinned-Dependencies).
# To regenerate: uv pip compile --generate-hashes --python-platform x86_64-unknown-linux-gnu \
#   --python-version 3.11 requirements-core.txt -o requirements-core.lock
COPY requirements-core.lock .
RUN pip install --no-cache-dir --require-hashes -r requirements-core.lock

# The heavy ingestion stack: Docling (standard/classical PDF pipeline: layout +
# RapidOCR + TableFormer).
# PyMuPDF is also installed here for llm_api page rendering. When INSTALL_INGESTION
# is false, standard PDF mode is unavailable (llm_api still works if configured) —
# use this on hosts with <4GB RAM or where the ~1-2GB Docling footprint is too large.
# Torch/torchvision are forced to CPU-only wheels to keep the image small.
# Docling 2.107+ imports torch/torchvision unconditionally (even with VLM
# features off), so they must be installed. CPU-only torch is ~123MB vs ~451MB
# for the CUDA build.
# To regenerate: uv pip compile --generate-hashes --python-platform x86_64-unknown-linux-gnu \
#   --python-version 3.11 --index-strategy unsafe-best-match \
#   --extra-index-url https://download.pytorch.org/whl/cpu \
#   requirements-ingestion.txt -o requirements-ingestion.lock
ARG INSTALL_INGESTION=true
COPY requirements-ingestion.lock .
RUN if [ "$INSTALL_INGESTION" != "false" ]; then \
        pip install --no-cache-dir --require-hashes -r requirements-ingestion.lock \
            --extra-index-url https://download.pytorch.org/whl/cpu; \
    fi

# Create non-root user and writable data/model directories.
# Register uid 1000 in /etc/passwd so torch's getpass.getuser() doesn't crash
# at runtime (torch is imported unconditionally by docling's import chain).
# We intentionally chown /app/models while it is EMPTY; models are downloaded
# as the non-root user below, so a later chown does not duplicate the model
# files in a new Docker layer.
RUN mkdir -p /app/data/documents/originals /app/data/documents/converted /app/data/documents/metadata \
    /app/data/.cache/huggingface /app/data/.cache/datasets \
    /app/models \
    && echo "cora:x:1000:1000:Cora:/app/data:/sbin/nologin" >> /etc/passwd \
    && chown -R 1000:1000 /app/data /app/models

# Switch to non-root user before downloading models so they are owned by cora
# from the start and a later chown does not duplicate them.
USER 1000:1000

# Prebake Docling models into the image so the first PDF upload is fast and
# works offline. Downloads layout + TableFormer + RapidOCR models (~700MB total)
# that the standard route needs — skips the ~610MB CodeFormulaV2 and picture
# classifier models that download_models() would pull by default but that are
# never used (do_formula_enrichment=False, do_picture_description=False).
# Gated by INSTALL_INGESTION so query-only images stay small.
COPY --chown=1000:1000 scripts/docker/download_docling_models.py ./scripts/docker/
RUN if [ "$INSTALL_INGESTION" != "false" ]; then \
        mkdir -p /app/models/docling && \
        python scripts/docker/download_docling_models.py /app/models/docling; \
    fi

# Copy backend source (readable by default 755/644 permissions)
COPY src/ ./src/
COPY migrations/ ./migrations/

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "src.api.main"]
