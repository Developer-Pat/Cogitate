"""Cancel stops the process, and the record follows — the half that used to be missing.

`POST /rag/ingest` refused for ever after a job died mid-run, because "is it running?" was a word in a
JSON file. Liveness made the word credible; cancel is what makes stopping possible at all.
"""
import os
import subprocess
import sys
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.api.v1.rag import router as rag_router
from app.domain.rag import service as rag_service
from app.domain.rag.schemas import IngestStatusFile


def _write_record(tmp_path, monkeypatch, **overrides) -> IngestStatusFile:
    monkeypatch.setattr(rag_service, "STATUS_FILE", str(tmp_path / "status.json"))
    now = datetime.now(timezone.utc)
    record = IngestStatusFile(
        job_id=overrides.get("job_id", "rag-ingest-test"),
        status=overrides.get("status", "running"),
        mode="incremental",
        started_at=now,
        pid=overrides.get("pid", None),
        heartbeat_at=overrides.get("heartbeat_at", now),
    )
    rag_service._write_status_file(record)
    return record


def _sleep_child() -> subprocess.Popen:
    """A process in its own session, like the ingest child — killable as a group."""
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)


async def test_cancel_kills_the_group_and_settles_the_record(tmp_path, monkeypatch):
    child = _sleep_child()
    try:
        _write_record(tmp_path, monkeypatch, pid=child.pid)

        result = await rag_router.cancel_ingest()

        assert result["cancelled"] is True
        assert result["status"] == "cancelled"
        assert child.wait(timeout=10) is not None  # it really stopped
        assert rag_service.RagIngestService.is_running() is False
    finally:
        if child.poll() is None:
            child.kill()


async def test_cancel_on_a_dead_job_says_so_without_killing_anything(tmp_path, monkeypatch):
    """A record left by a job whose process is gone is not live — cancel does nothing and says it."""
    _write_record(tmp_path, monkeypatch, pid=4_000_000)

    result = await rag_router.cancel_ingest()

    assert result["cancelled"] is False
    assert "owner is gone" in result["message"]


async def test_cancel_refuses_to_sign_the_api_process_itself(tmp_path, monkeypatch):
    """An in-process job has no group of its own; killing it would take the app down."""
    _write_record(tmp_path, monkeypatch, pid=os.getpid())

    with pytest.raises(HTTPException) as raised:
        await rag_router.cancel_ingest()

    assert raised.value.status_code == 409


async def test_cancel_with_no_record_is_404(tmp_path, monkeypatch):
    monkeypatch.setattr(rag_service, "STATUS_FILE", str(tmp_path / "nothing.json"))
    with pytest.raises(HTTPException) as raised:
        await rag_router.cancel_ingest()
    assert raised.value.status_code == 404
