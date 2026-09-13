"""Tests for the document store indexer and chunk header logic."""
from __future__ import annotations


def test_row_canonical_id_uses_only_known_identifier_columns(make_record):
    from src.document_store.indexer import _row_canonical_id

    record = make_record(id="doc_1")
    assert _row_canonical_id(record, 4, {"Grid": "grid-1"}) == "doc_1:4"
    assert _row_canonical_id(record, 4, {"Project ID": "VCS1"}) == "doc_1:VCS1"


def test_build_chunk_header_prefers_title(make_record):
    from src.document_store.indexer import _build_chunk_header

    record = make_record(title="VM0048: Monitoring", document_id="VM0048")
    assert _build_chunk_header(record) == "VM0048: Monitoring"


def test_build_chunk_header_uses_title_as_is_without_duplicating_document_id(make_record):
    """If the title already contains the document ID, _build_chunk_header uses
    it as-is and does not synthesize a duplicate "doc_id: title" string."""
    from src.document_store.indexer import _build_chunk_header

    record = make_record(title="VM0048: Monitoring", document_id="VM0048")
    header = _build_chunk_header(record)
    assert header == "VM0048: Monitoring"
    assert "VM0048: VM0048" not in header


def test_build_chunk_header_falls_back_to_original_filename(make_record):
    from src.document_store.indexer import _build_chunk_header

    record = make_record(title=None, original_filename="VM0048.pdf", document_id="VM0048")
    assert _build_chunk_header(record) == "VM0048.pdf"


def test_build_chunk_header_returns_empty_when_no_source(make_record):
    from src.document_store.indexer import _build_chunk_header

    record = make_record(title=None, original_filename=None)
    assert _build_chunk_header(record) == ""


def test_chunk_markdown_prepends_header_to_markdown_chunks(document_store_env, monkeypatch, make_record):
    from src.config import reset_settings_singleton
    from src.document_store.indexer import chunk_markdown

    monkeypatch.setenv("CHUNK_SIZE", "60")
    monkeypatch.setenv("CHUNK_OVERLAP", "10")
    reset_settings_singleton()

    record = make_record(
        title="VM0048: Monitoring",
        document_id="VM0048",
        original_filename="VM0048.pdf",
        converted_path="/tmp/VM0048.md",
    )
    text = (
        "Section one has enough words to make a whole chunk of its own. " * 3
        + "\n\n"
        + "Section two has enough words to make a second chunk. " * 4
    )

    monkeypatch.setattr("src.document_store.indexer.read_markdown", lambda r: text)
    monkeypatch.setattr("src.document_store.indexer.read_row_data_file", lambda r: ([], False))

    chunks = chunk_markdown(record)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.page_content.startswith("VM0048: Monitoring\n\n"), chunk.page_content[:80]
        assert chunk.metadata["title"] == "VM0048: Monitoring"
        assert chunk.metadata["doc_store_id"] == "doc_test"


def test_chunk_markdown_prepends_header_to_dataset_rows(monkeypatch, make_record):
    from src.document_store.indexer import chunk_markdown

    record = make_record(
        title="VM0048: Monitoring",
        document_id="VM0048",
        original_filename="VM0048.json",
        extension=".json",
        converted_path="/tmp/VM0048.md",
    )
    rows = [
        {"Project ID": "P1", "Name": "one"},
        {"Project ID": "P2", "Name": "two"},
    ]

    monkeypatch.setattr("src.document_store.indexer.read_markdown", lambda r: "")
    monkeypatch.setattr("src.document_store.indexer.read_row_data_file", lambda r: (rows, False))

    chunks = chunk_markdown(record)
    assert len(chunks) == 2
    for chunk in chunks:
        assert chunk.page_content.startswith("VM0048: Monitoring\n\n")
        assert chunk.metadata["title"] == "VM0048: Monitoring"


def test_chunk_markdown_marks_truncated_dataset_rows(monkeypatch, make_record):
    """When the row sidecar says the source file was cut at the ingestion row
    limit, every dataset chunk carries dataset_truncated so the structured
    retrieval path reports counts as lower bounds."""
    from src.document_store.indexer import chunk_markdown

    record = make_record(
        title="VM0048: Monitoring",
        document_id="VM0048",
        original_filename="VM0048.csv",
        extension=".csv",
        converted_path="/tmp/VM0048.md",
    )
    rows = [{"Project ID": "P1", "Name": "one"}]

    monkeypatch.setattr("src.document_store.indexer.read_markdown", lambda r: "")
    monkeypatch.setattr("src.document_store.indexer.read_row_data_file", lambda r: (rows, True))

    chunks = chunk_markdown(record)
    assert len(chunks) == 1
    assert chunks[0].metadata["dataset_truncated"] is True


def test_row_data_file_round_trip_preserves_truncated_flag(document_store_env, make_record):
    """The row sidecar persists the truncation flag alongside the records, and
    legacy plain-list sidecars read back as untruncated."""
    import json

    from src.document_store.files import (
        read_row_data_file,
        row_data_path,
        write_row_data_file,
    )

    record = make_record()
    rows = [{"Project ID": "P1"}]

    write_row_data_file(record, rows, truncated=True)
    assert read_row_data_file(record) == (rows, True)

    write_row_data_file(record, rows, truncated=False)
    assert read_row_data_file(record) == (rows, False)

    # Legacy sidecar format: a bare list with no truncation metadata.
    row_data_path(record).write_text(json.dumps(rows), encoding="utf-8")
    assert read_row_data_file(record) == (rows, False)


def test_chunk_markdown_first_chunk_keeps_existing_heading(document_store_env, monkeypatch, make_record):
    from src.config import reset_settings_singleton
    from src.document_store.indexer import chunk_markdown

    monkeypatch.setenv("CHUNK_SIZE", "100")
    monkeypatch.setenv("CHUNK_OVERLAP", "10")
    reset_settings_singleton()

    record = make_record(
        title="VM0048: Monitoring",
        document_id="VM0048",
        original_filename="VM0048.pdf",
        converted_path="/tmp/VM0048.md",
    )
    text = "# VM0048: Monitoring\n\nSome body text that is long enough to survive chunking. " * 5

    monkeypatch.setattr("src.document_store.indexer.read_markdown", lambda r: text)
    monkeypatch.setattr("src.document_store.indexer.read_row_data_file", lambda r: ([], False))

    chunks = chunk_markdown(record)
    assert chunks
    first = chunks[0].page_content
    assert first.startswith("VM0048: Monitoring\n\n")
    assert "# VM0048: Monitoring" in first


def test_chunk_markdown_skips_header_when_no_source(document_store_env, monkeypatch, make_record):
    """When both title and original_filename are empty, _prepend_header is a
    no-op and chunks keep their original page_content (no empty-line prefix)."""
    from src.config import reset_settings_singleton
    from src.document_store.indexer import chunk_markdown

    monkeypatch.setenv("CHUNK_SIZE", "100")
    monkeypatch.setenv("CHUNK_OVERLAP", "10")
    reset_settings_singleton()

    record = make_record(
        title=None,
        original_filename="",
        document_id=None,
        converted_path="/tmp/none.md",
    )
    text = "Body text that is long enough to survive chunking. " * 5

    monkeypatch.setattr("src.document_store.indexer.read_markdown", lambda r: text)
    monkeypatch.setattr("src.document_store.indexer.read_row_data_file", lambda r: ([], False))

    chunks = chunk_markdown(record)
    assert chunks
    for chunk in chunks:
        assert not chunk.page_content.startswith("\n\n")
        assert "Body text" in chunk.page_content
