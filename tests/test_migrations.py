"""Tests for SQL migration scripts."""
from __future__ import annotations

from pathlib import Path


def test_category_backfill_migration_moves_non_registry_names(document_store_env):
    """006 migration moves pre-split non-registry names from registry to category."""
    from src.db.database import get_connection
    from src.document_store.schema import ensure_document_store_tables

    ensure_document_store_tables()

    conn = get_connection()
    try:
        # Simulate rows written before the registry/category split.
        conn.executemany(
            """
            INSERT INTO document_store_documents (
                id, original_filename, stored_filename, mime_type, extension,
                size_bytes, sha256, status, conversion_mode, original_path,
                converted_path, title, registry, category
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "doc_old_policy", "old1.md", "old1.md", "text/plain", ".md",
                    1, "sha1", "indexed", "standard", "/tmp/old1.md",
                    None, "Old Policy", "VCM Policy", None,
                ),
                (
                    "doc_old_governance", "old2.md", "old2.md", "text/plain", ".md",
                    1, "sha2", "indexed", "standard", "/tmp/old2.md",
                    None, "Old Governance", "ICVCM", None,
                ),
                (
                    "doc_real_registry", "real.md", "real.md", "text/plain", ".md",
                    1, "sha3", "indexed", "standard", "/tmp/real.md",
                    None, "Real Registry", "Verra", None,
                ),
                (
                    "doc_already_normalized", "already.md", "already.md", "text/plain", ".md",
                    1, "sha4", "indexed", "standard", "/tmp/already.md",
                    None, "Already Normalized", None, "Market Intelligence",
                ),
            ],
        )
        conn.commit()

        migration_path = (
            Path(__file__).parent.parent / "migrations" / "006_document_category_backfill.sql"
        )
        backfill_sql = migration_path.read_text(encoding="utf-8")
        conn.executescript(backfill_sql)
        conn.commit()

        rows = {
            row["id"]: dict(row)
            for row in conn.execute(
                "SELECT id, registry, category FROM document_store_documents"
            ).fetchall()
        }
    finally:
        conn.close()

    # Topic classifiers and governance bodies move to category.
    assert rows["doc_old_policy"]["registry"] is None
    assert rows["doc_old_policy"]["category"] == "VCM Policy"
    assert rows["doc_old_governance"]["registry"] is None
    assert rows["doc_old_governance"]["category"] == "ICVCM"

    # Real registries stay in registry.
    assert rows["doc_real_registry"]["registry"] == "Verra"
    assert rows["doc_real_registry"]["category"] is None

    # Already-normalized rows are untouched.
    assert rows["doc_already_normalized"]["registry"] is None
    assert rows["doc_already_normalized"]["category"] == "Market Intelligence"


def test_migrations_recorded_when_table_created_outside_migrations(document_store_env):
    """If ensure_document_store_tables creates the schema before run_migrations,
    later migrations that add existing columns must be recorded instead of crashing."""
    from src.db.database import get_connection, run_migrations
    from src.document_store.schema import ensure_document_store_tables

    ensure_document_store_tables()

    # This should not raise despite the table already containing columns added by 004/005.
    run_migrations()

    conn = get_connection()
    try:
        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
    finally:
        conn.close()

    assert "004_document_metadata.sql" in applied
    assert "005_document_category.sql" in applied
