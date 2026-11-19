"""The phase's exit criterion, exercised for real.

**"A run can be started, watched, cancelled and re-started without leaving a
process behind — proven by checking for orphans AFTER a cancel."**

That is a phase boundary, not a unit test: it starts a real process group, kills
it, and looks for survivors. Marked `integration` so the fast loop stays fast —
an integration test that runs on every edit is a test people start ignoring.

WHAT IT WOULD CATCH, and why it is worth the seconds:

- a cancel that kills the runner's pid and leaves pytest's xdist workers alive,
  holding the database — the failure that presents LATER as flaky tests, when
  nobody remembers there was a cancel;
- a lock left behind by a killed run, which would refuse every run afterwards
  until somebody found a hidden dotfile;
- a "cancel" that reports success without checking.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import pytest

from app.core.config import Paths
from app.domain.testing import runner
from app.domain.testing.run_lock import read_lock

pytestmark = pytest.mark.integration


def _run_processes(run_id: str) -> list[str]:
    """The processes OF ONE RUN — the orphan net, asked of the OS by run id.

    THIS USED TO MATCH THE WHOLE MACHINE (`pgrep -af "pytest|run_tests.py"`), which
    cannot be right when the suite runs in parallel: other workers launch and reap
    their own pytest subprocesses between the two snapshots, so the net reported
    THEIR processes as this run's orphans. Measured in `--group all`: it failed on
    another test's subprocess AND on the shared-db guard's probe fixture — a net
    wide enough to catch strangers catches the suite itself.

    The runner puts `--run-id <id>` into the argv it spawns (see `build_command`),
    so the run's own id is the precise token for "a process belonging to this run".
    """
    try:
        out = subprocess.run(["pgrep", "-af", run_id],
                             capture_output=True, text=True, timeout=10).stdout
    except Exception:  # noqa: BLE001
        return []
    return [line for line in out.splitlines() if line.strip()]


def test_start_cancel_and_start_again_leaves_nothing_behind(tmp_path: Path,
                                                           monkeypatch: pytest.MonkeyPatch) -> None:
    runs_dir = tmp_path / "test-runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Paths, "test_runs_dir", runs_dir)

    run_id = "itest-cancel-1"
    before = _run_processes(run_id)  # nothing carries this id until it is spawned

    # 1. START a real group run — long enough to be cancelled mid-flight.
    handle = runner.spawn(runner.RunSpec(group="unit"), run_id)
    assert handle["run_id"] == run_id
    assert handle["origin"] == "page"
    held = read_lock(runs_dir)
    assert held is not None and held.id == run_id and held.alive()

    # 2. WATCH it: the run's own event file is producing frames.
    deadline = time.monotonic() + 30
    events = runs_dir / run_id / "events.jsonl"
    while time.monotonic() < deadline and not events.exists():
        time.sleep(0.2)
    assert events.exists(), "the run never wrote its event stream"

    # 3. CANCEL — the whole group.
    time.sleep(2)  # let pytest get going, so there are workers to kill
    result = runner.cancel(run_id)
    assert result["cancelled"] is True
    assert result["survivors"] == [], (
        f"the cancel left processes behind: {result['survivors']}"
    )
    assert result["released_lock"] is True

    # 4. VERIFY: no test-family process is left, and the lock is gone.
    time.sleep(1)
    after = _run_processes(run_id)
    leaked = [line for line in after if line not in before]
    assert leaked == [], f"orphaned processes from run {run_id}: {leaked}"
    assert read_lock(runs_dir) is None, "the lock outlived the run it protected"

    # 5. RE-START — the cancel must not have wedged the lock or the runner.
    second = "itest-cancel-2"
    handle = runner.spawn(runner.RunSpec(files=["tests/unit/test_macro_meta_topics.py"]),
                          second)
    assert handle["run_id"] == second
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        if (runs_dir / second / "events.jsonl").exists():
            text = (runs_dir / second / "events.jsonl").read_text(encoding="utf-8")
            if "run_end" in text:
                break
        time.sleep(0.5)
    text = (runs_dir / second / "events.jsonl").read_text(encoding="utf-8")
    assert '"run_end"' in text or '"t":"run_end"' in text, "the second run never finished"
    assert read_lock(runs_dir) is None
    runner.forget(second)
