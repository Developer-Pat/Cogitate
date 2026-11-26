"""The child's own guards: which roots it will accept, whose record it will settle, and what a clear removes."""
from datetime import datetime, timezone

import pytest

from app.domain.providers.embeddings import EmbeddingService
from app.domain.rag import ingest_cli, service as rag_service
from app.domain.rag.schemas import IngestStatusFile
from app.domain.tools.builtin.doc_vector_store import DocVectorStore


def _resolved() -> EmbeddingService:
    return EmbeddingService(address="http://127.0.0.1:9", model="nomic-embed-text", dims=768)


# ── the child's argument surface ────────────────────────────────────────────────────────────────

def test_the_child_accepts_the_roots_the_app_knows():
    args = ingest_cli._parse(["--job-id", "j1", "--dirs", "wiki/help,wiki/entities"])
    assert args.dirs == ["wiki/help", "wiki/entities"]


def test_an_empty_dirs_flag_means_the_apps_own_six():
    args = ingest_cli._parse(["--job-id", "j1"])
    assert args.dirs == []


def test_the_child_refuses_a_root_the_app_does_not_know():
    """A typo must fail loudly here — silently indexing nothing is how a run 'succeeds' empty."""
    with pytest.raises(SystemExit):
        ingest_cli._parse(["--job-id", "j1", "--dirs", "wiki/help,wiki/nowhere"])


# ── whose record the child settles ──────────────────────────────────────────────────────────────

def test_finishing_never_touches_a_newer_jobs_record(tmp_path, monkeypatch):
    monkeypatch.setattr(rag_service, "STATUS_FILE", str(tmp_path / "status.json"))
    now = datetime.now(timezone.utc)
    rag_service._write_status_file(
        IngestStatusFile(
            job_id="the-newer-job",
            status="running",
            mode="incremental",
            started_at=now,
            pid=1,
            heartbeat_at=now,
        )
    )

    ingest_cli._finish_record("an-older-job", "cancelled", "stopped")

    record = rag_service._read_status_file()
    assert record is not None and record.job_id == "the-newer-job" and record.status == "running"


def test_finishing_leaves_a_record_that_already_finished_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(rag_service, "STATUS_FILE", str(tmp_path / "status.json"))
    now = datetime.now(timezone.utc)
    rag_service._write_status_file(
        IngestStatusFile(
            job_id="j1", status="completed", mode="incremental", started_at=now, pid=1, heartbeat_at=now
        )
    )

    ingest_cli._finish_record("j1", "failed", "too late")

    record = rag_service._read_status_file()
    assert record is not None and record.status == "completed"


# ── clear ───────────────────────────────────────────────────────────────────────────────────────

def test_clear_empties_the_index_and_reports_what_it_removed(tmp_path):
    store = DocVectorStore(db_path=str(tmp_path / "idx.db"), embedding=_resolved())
    store.init_db()
    db = store._get_connection()
    db.execute(
        "INSERT INTO doc_chunks (source_path, chunk_text, checksum) VALUES (?, ?, ?)",
        ("wiki/help/a.md", "some text", "abc123"),
    )
    db.commit()

    removed = store.clear()

    assert removed["chunks"] == 1
    assert removed["documents"] == 1
    assert store.list_indexed_paths() == []


def test_clear_on_a_store_that_was_never_built_reports_nothing_rather_than_creating_one(tmp_path):
    store = DocVectorStore(db_path=str(tmp_path / "never.db"), embedding=_resolved())

    assert store.clear() == {"documents": 0, "chunks": 0}
