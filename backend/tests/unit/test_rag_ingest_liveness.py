"""The job record is the contract: who owns a run, whether they are alive, and how far they have got.

Two failures came out of the record being one word in a file:

- **`is_running()` was `status == "running"`.** A cancelled task, a crash, or uvicorn's `--reload`
  (measured twice in one session) left the word set, so `POST /rag/ingest` answered 409 for ever and
  the only way out was editing the JSON by hand.
- **progress was written per FILE**, so a six-minute document showed `0 / 0` while embeddings visibly
  flowed.

Liveness is now the pid plus a heartbeat, and the heartbeat is written per chunk.
"""
import os
from datetime import datetime, timedelta, timezone

from app.domain.rag import service as rag_service
from app.domain.rag.schemas import IngestProgress, IngestStatusFile


def _record(
    *,
    status: str = "running",
    pid: int | None = os.getpid(),
    heartbeat_at: datetime | None = None,
    dirs: list[str] | None = None,
) -> IngestStatusFile:
    now = datetime.now(timezone.utc)
    return IngestStatusFile(
        job_id="rag-ingest-1",
        status=status,
        mode="incremental",
        started_at=now,
        pid=pid,
        heartbeat_at=heartbeat_at if heartbeat_at is not None else now,
        dirs=dirs if dirs is not None else [],
    )


def test_a_live_pid_with_a_fresh_heartbeat_is_running():
    assert rag_service._job_is_live(_record()) is True


def test_a_dead_pid_is_not_running_even_with_a_fresh_heartbeat():
    """The reload trap: the record still says `running`, and the process that wrote it is gone."""
    assert rag_service._job_is_live(_record(pid=4_000_000)) is False


def test_a_stale_heartbeat_is_not_running():
    old = datetime.now(timezone.utc) - timedelta(seconds=rag_service.HEARTBEAT_STALE_S + 5)
    assert rag_service._job_is_live(_record(heartbeat_at=old)) is False


def test_a_finished_job_is_not_running_whatever_its_pid_says():
    for finished in ("completed", "failed", "cancelled"):
        assert rag_service._job_is_live(_record(status=finished)) is False


def test_a_record_with_no_pid_is_not_running():
    """A record written before the child started names nobody — it cannot be a live job."""
    assert rag_service._job_is_live(_record(pid=None)) is False


def test_the_record_keeps_what_was_asked_for():
    """`dirs` is the run config's own record of itself — an empty list must survive, not default."""
    assert _record(dirs=[]).dirs == []
    assert _record(dirs=["wiki/help"]).dirs == ["wiki/help"]


def test_progress_carries_a_live_chunk_counter_apart_from_the_indexed_total():
    """`chunks_done` moves per chunk; `total_chunks` only when a document commits."""
    progress = IngestProgress.model_validate(
        {"chunks_done": 7, "total_chunks": 2, "current_file": "wiki/help/a.md"}
    )
    assert progress.chunks_done == 7
    assert progress.total_chunks == 2
    assert progress.current_file.endswith("a.md")
