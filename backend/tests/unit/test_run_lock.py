"""The run lock — one run at a time, and a sentence when it is not.

The lock exists because two overlapping runs do not present as "two runs":
pytest needs exclusive database access, so they present as FLAKY TESTS — the
suite looks unreliable and the real cause is invisible. These pin the three
behaviours that make the lock worth having: it is TAKEN, a second attempt is
REFUSED with the holder named, and a lock whose run is GONE is cleared only by
an explicit act — never automatically, because a lock that clears itself when it
feels stale can clear itself while another run is starting.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from app.domain.testing.run_lock import (
    LOCK_NAME,
    RunInProgress,
    acquire,
    clear_stale,
    lock_path,
    process_alive,
    read_lock,
    release,
)


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    return tmp_path / "test-runs"


def dead_pid() -> int:
    """A pid that certainly belonged to a process and certainly no longer does."""
    proc = subprocess.Popen(["true"])
    pid = proc.pid
    proc.wait()
    return pid


def test_acquire_records_the_holder_and_release_removes_it(runs_dir: Path) -> None:
    lock = acquire(runs_dir, "20260101-000000", origin="terminal")
    on_disk = read_lock(runs_dir)
    assert on_disk == lock
    assert on_disk is not None
    assert on_disk.pid == os.getpid()
    assert on_disk.pgid == os.getpgid(0)
    assert on_disk.origin == "terminal"

    assert release(runs_dir, "20260101-000000") is True
    assert read_lock(runs_dir) is None
    assert not lock_path(runs_dir).exists()


def test_a_second_acquire_refuses_and_names_the_holder(runs_dir: Path) -> None:
    acquire(runs_dir, "20260101-000000", origin="terminal")
    with pytest.raises(RunInProgress) as caught:
        acquire(runs_dir, "20260101-000001", origin="page")
    assert caught.value.stale is False
    assert caught.value.lock is not None
    assert caught.value.lock.id == "20260101-000000"
    assert "in progress" in str(caught.value)
    # The refusal names WHO, because "something is running" is not actionable.
    assert "terminal" in str(caught.value)
    release(runs_dir, "20260101-000000")


def test_release_does_not_remove_ANOTHER_runs_lock(runs_dir: Path) -> None:
    """A `finally` firing late must not delete the lock of the run that took
    over after it — that would let a third run start on top of the second."""
    acquire(runs_dir, "20260101-000000")
    assert release(runs_dir, "20260101-999999") is False
    assert read_lock(runs_dir) is not None
    release(runs_dir, "20260101-000000")


def test_a_dead_pid_is_reported_STALE_not_in_progress(runs_dir: Path) -> None:
    runs_dir.mkdir(parents=True)
    lock_path(runs_dir).write_text(json.dumps({
        "id": "20260101-000000", "pid": dead_pid(), "pgid": 0,
        "started": "2026-01-01T00:00:00", "origin": "terminal",
    }))
    with pytest.raises(RunInProgress) as caught:
        acquire(runs_dir, "20260101-000001")
    assert caught.value.stale is True
    assert "NOT in progress" in str(caught.value)


def test_clear_stale_refuses_a_LIVE_lock(runs_dir: Path) -> None:
    """Clearing a live lock is how two runs end up on one database."""
    acquire(runs_dir, "20260101-000000")
    with pytest.raises(RunInProgress) as caught:
        clear_stale(runs_dir)
    assert caught.value.stale is False
    assert read_lock(runs_dir) is not None
    release(runs_dir, "20260101-000000")


def test_clear_stale_removes_debris_and_says_which(runs_dir: Path) -> None:
    runs_dir.mkdir(parents=True)
    lock_path(runs_dir).write_text(json.dumps({
        "id": "20260101-000000", "pid": dead_pid(), "pgid": 0,
        "started": "2026-01-01T00:00:00", "origin": "sweep",
    }))
    cleared = clear_stale(runs_dir)
    assert cleared is not None and cleared.id == "20260101-000000"
    assert not lock_path(runs_dir).exists()
    assert clear_stale(runs_dir) is None  # nothing left to clear


def test_a_fresh_unreadable_lock_is_NOT_taken_over(runs_dir: Path) -> None:
    """A run writes its lock microseconds after creating it. A file that is
    unreadable RIGHT NOW may be mid-write, so it must not be read as debris."""
    runs_dir.mkdir(parents=True)
    lock_path(runs_dir).write_text("")
    with pytest.raises(RunInProgress) as caught:
        acquire(runs_dir, "20260101-000001")
    assert caught.value.unreadable is True
    assert caught.value.stale is False


def test_an_old_unreadable_lock_is_clearable(runs_dir: Path) -> None:
    runs_dir.mkdir(parents=True)
    path = lock_path(runs_dir)
    path.write_text("{ this never finished")
    old = 10_000
    os.utime(path, (path.stat().st_atime - old, path.stat().st_mtime - old))
    assert clear_stale(runs_dir) is None      # cleared, but there was no holder to name
    assert not path.exists()


def test_the_lock_file_lives_BESIDE_the_runs(runs_dir: Path) -> None:
    """Moving or copying a runs dir has to carry its own state."""
    assert lock_path(runs_dir).parent == runs_dir
    assert LOCK_NAME.startswith(".")


def test_process_alive_is_honest_about_the_edge(runs_dir: Path) -> None:
    assert process_alive(os.getpid()) is True
    assert process_alive(dead_pid()) is False
    assert process_alive(0) is False
    assert process_alive(-1) is False
