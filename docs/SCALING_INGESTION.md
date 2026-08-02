# Scaling Ingestion Throughput

> PDF ingestion is CPU- and memory-bound. The default Docker limits are
> conservative so Cora runs on modest hardware. If your host has more
> resources, you can convert more PDFs in parallel and cut batch time
> significantly.

---

## What controls ingestion speed

Three settings work together. **Change all three together** — raising only one
either does nothing or makes things worse.

| Setting | Where | Default | What it does |
|---|---|---|---|
| `cpus` | `docker-compose.yml` (`ingest-worker`) | `2.0` | CPU cores for Docling layout model + OCR + table parsing |
| `mem_limit` | `docker-compose.yml` (`ingest-worker`) | `4g` | RAM for the model stack + concurrent documents |
| `DOCUMENT_INGESTION_CONCURRENCY` | `.env` or compose `environment` | `2` | PDFs converted in parallel |

**Rule of thumb:** keep `concurrency` ≤ `cpus`, and budget ~1–1.5 GB RAM per
concurrent job on top of the ~3 GB base the models need.

---

## Pick your host size

| Your host | `cpus` | `mem_limit` | `concurrency` |
|---|---|---|---|
| Small (4 cores, 8 GB) | `2.0` | `4g` | `2` *(defaults — leave as-is)* |
| Medium (8 cores, 16 GB) | `4.0` | `8g` | `4` |
| Large (12+ cores, 24+ GB) | `6.0` | `12g` | `5`–`6` |

Leave headroom for the `app` (queries) and `qdrant` containers — they need
~2 cores and ~3 GB combined. Don't give the worker everything.

---

## How to apply (Docker Compose)

Edit the `ingest-worker` service in `docker-compose.yml`:

```yaml
  ingest-worker:
    # ... keep existing build / env_file / volumes ...
    environment:
      - DATABASE_URL=sqlite:////app/db/cora.db
      - QDRANT_URL=http://qdrant:6333
      - INGESTION_DISPATCH=worker
      - SQLITE_JOURNAL_MODE=WAL
      # --- add this line to scale ---
      - DOCUMENT_INGESTION_CONCURRENCY=4
    mem_limit: 8g     # was 4g
    cpus: 4.0         # was 2.0
```

Then rebuild and restart only the worker:

```bash
docker compose up -d --build ingest-worker
```

Verify it picked up the new value:

```bash
docker compose logs ingest-worker --tail=5
# → "Ingestion worker started (concurrency=4, poll interval=2.0s, ...)"
```

---

## How to apply (native / no Docker)

Set the env var in `.env` (or your shell) and restart the worker process:

```env
DOCUMENT_INGESTION_CONCURRENCY=4
```

```bash
python -m src.document_store.worker
```

---

## Running multiple workers (very large hosts)

The job table uses atomic claiming, so multiple worker containers never
double-process a job. Scale horizontally on a big host:

```bash
docker compose up -d --scale ingest-worker=2 --build
```

Each replica still respects `DOCUMENT_INGESTION_CONCURRENCY`, so total
parallelism = `replicas × concurrency`. Make sure
`replicas × cpus` fits your host.

---

## Optional per-document tuning

These don't speed up a single conversion but reduce or redirect work:

| Setting | Default | When to change |
|---|---|---|
| `DOCUMENT_DOCLING_TIMEOUT` | `1800` (30 min) | Raise to `3600` for very large PDFs that time out |
| `DOCUMENT_DOCLING_TABLE_MODE` | `fast` | Set to `accurate` if you see broken merged-cell tables in answers |
| `DOCUMENT_DOCLING_DO_FORMULAS` | `false` | Set to `true` for proper math decoding (loads a VLM — needs more RAM) |
| `EMBEDDING_BATCH_SIZE` | `256` | Raise only if your embedding provider documents a higher limit |

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Worker OOM-killed mid-batch | `mem_limit` too low for the concurrency | Raise `mem_limit` or lower `concurrency` |
| No speedup after raising concurrency | `cpus` still at `2.0` | Raise `cpus` to match `concurrency` |
| `concurrency` in logs didn't change | Compose `environment` overrides `.env` | Set it in one place only; rebuild the worker |
| Queries slow during ingestion | Worker starved the `app` container | Lower worker `cpus` so the app keeps its share |
