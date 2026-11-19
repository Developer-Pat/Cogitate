"""Starting and stopping a run — the parts that must not lie.

Three claims carry this module, and each is pinned here:

1. **A failed start is REPORTED, not hidden.** `Popen` succeeding only means a
   process exists. The spawn waits for the runner's own lock, so "it started" is
   a fact — and a run that died first hands back its console instead of a page
   that shows "running" over nothing.
2. **A cancel is a GROUP kill.** pytest's xdist workers share the group; killing
   the runner's pid alone leaves them holding the database, and that surfaces
   later as flaky tests.
3. **A cancel refuses what it did not start.** Stopping a terminal run or the
   sweep is a deliberate act, not the side effect of a button.

The real spawn-and-cancel round trip lives in
`tests/integration/test_run_spawn_cancel.py`: it takes seconds, kills a process
group, and checks for orphans — which is a phase boundary, not a unit test.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from app.core.config import Paths
from app.domain.testing import runner
from app.domain.testing.run_lock import RunInProgress, acquire, lock_path, read_lock, release


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "test-runs"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Paths, "test_runs_dir", target)
    return target


def dead_pid() -> int:
    proc = subprocess.Popen(["true"])
    pid = proc.pid
    proc.wait()
    return pid


def test_the_command_names_the_run_and_its_dir() -> None:
    spec = runner.RunSpec(group="unit")
    cmd = runner.build_command(spec, Path("/tmp/runs"), "20260101-000000")
    assert cmd[0] == runner.sys.executable
    assert str(runner.RUNNER) in cmd
    assert "--run-id" in cmd and "20260101-000000" in cmd
    assert cmd[cmd.index("--runs-dir") + 1] == "/tmp/runs"
    assert cmd[cmd.index("--group") + 1] == "unit"
    # The page reads artifacts; a console stream would be a second copy.
    assert "--no-live" in cmd


def test_a_named_module_wins_over_a_group() -> None:
    spec = runner.RunSpec(group="unit", files=["tests/unit/x.py"])
    args = spec.to_args()
    assert "--file" in args and "--group" not in args


def test_parallel_is_only_forced_when_asked() -> None:
    assert "--parallel" not in runner.RunSpec(group="unit").to_args()
    assert "--parallel" in runner.RunSpec(group="unit", parallel=True).to_args()
    assert "--sequential" in runner.RunSpec(group="unit", parallel=False).to_args()


def test_a_spec_that_describes_nothing_is_refused() -> None:
    with pytest.raises(ValueError):
        runner.RunSpec().to_args()


def test_spawn_refuses_while_a_LIVE_lock_is_held(runs_dir: Path) -> None:
    acquire(runs_dir, "20260101-000000", origin="terminal")
    try:
        with pytest.raises(RunInProgress) as caught:
            runner.spawn(runner.RunSpec(group="unit"), "20260101-000001")
        assert caught.value.lock is not None
        assert caught.value.lock.id == "20260101-000000"
    finally:
        release(runs_dir, "20260101-000000")


def test_a_failed_start_is_REFUSED_with_its_console(runs_dir: Path) -> None:
    """An invalid group makes the runner exit before it takes the lock. The
    caller must get that, not a run id for a run that never began."""
    with pytest.raises(RuntimeError) as caught:
        runner.spawn(runner.RunSpec(group="not-a-group"), "20260101-000000")
    assert "exited immediately" in str(caught.value)
    assert "not-a-group" in str(caught.value) or "invalid choice" in str(caught.value)
    assert read_lock(runs_dir) is None          # no lock was taken
    runner.forget("20260101-000000")


def test_cancel_with_nothing_running_says_so(runs_dir: Path) -> None:
    assert runner.cancel("20260101-000000") == {
        "cancelled": False, "reason": "no run is in progress",
    }


def test_cancel_refuses_a_run_the_page_did_not_start(runs_dir: Path) -> None:
    acquire(runs_dir, "20260101-000000", origin="terminal")
    try:
        result = runner.cancel("20260101-000000")
        assert result["cancelled"] is False
        assert "outside the page" in result["reason"]
        assert read_lock(runs_dir) is not None   # still theirs, untouched
    finally:
        release(runs_dir, "20260101-000000")


def test_cancel_refuses_a_DIFFERENT_run(runs_dir: Path) -> None:
    acquire(runs_dir, "20260101-000000", origin="page")
    try:
        result = runner.cancel("20260101-999999")
        assert result["cancelled"] is False
        assert "different run" in result["reason"]
    finally:
        release(runs_dir, "20260101-000000")


def test_cancel_of_a_dead_run_clears_its_lock(runs_dir: Path) -> None:
    lock_path(runs_dir).write_text(json.dumps({
        "id": "20260101-000000", "pid": dead_pid(), "pgid": 0,
        "started": "2026-01-01T00:00:00", "origin": "page",
    }))
    result = runner.cancel("20260101-000000")
    assert result["cancelled"] is False
    assert "already gone" in result["reason"]
    assert read_lock(runs_dir) is None


def test_group_pids_excludes_zombies() -> None:
    """A killed-but-unreaped process holds nothing. Reporting it as a survivor
    would turn a clean kill into a scary number."""
    proc = subprocess.Popen(["true"], start_new_session=True)
    proc.wait()  # reaped by us, so no zombie — the group is empty
    assert runner._group_pids(proc.pid) == []
    # a live member IS reported, so the check is not vacuously empty
    alive = subprocess.Popen(["sleep", "5"], start_new_session=True)
    try:
        assert alive.pid in runner._group_pids(alive.pid)
    finally:
        alive.kill()
        alive.wait()
