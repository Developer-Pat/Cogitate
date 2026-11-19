"""
Spawning a run, and stopping one.

**One runner, driven — not a second one.** The page starts the same
`scripts/testing/run_tests.py` a person starts from a terminal, with the same
flags. A second runner for the UI would duplicate what this project already
fights: two copies, one fixed, the symptom surviving.

WHAT THIS DOES NOT DO, stated plainly: it keeps no job queue, no scheduler and no
run state of its own. The LOCK FILE is the state — it says which run is going,
whose it is, and how to reach it — so a run survives a backend restart, and a
cancel works on a run this process never spawned.

CANCEL IS A GROUP KILL, and that is not a detail. The runner launches pytest,
which launches xdist workers; killing the runner's pid alone leaves the workers
alive and holding the database, which presents as FLAKY TESTS — the worst
possible presentation, because the report blames the code. So the kill mirrors
`stop_process_group` in `cogitate.sh`: read the GROUP id (never assume it),
TERM the group, wait, KILL the group, then VERIFY — and name any survivor rather
than claiming success.

WHOSE RUN MAY THIS CANCEL: the page's own. A run started in a terminal, or by
the sweep, is watched and not stopped — killing a process this page did not start
is a different decision, and it is filed as one.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from app.core import activity
from app.core.config import Paths
from app.domain.testing.run_lock import (
    RunInProgress,
    clear_stale,
    lock_path,
    read_lock,
)

logger = logging.getLogger(__name__)

#: The runner, and the project root it is documented to be started from (it
#: resolves its own paths from `__file__`, but its pytest call and its relative
#: `--file` handling assume the root).
RUNNER = Path(Paths.root) / "scripts" / "testing" / "run_tests.py"

#: How long a spawned run gets to take the lock before we call it a failed start.
#: The runner takes it within milliseconds; this covers a cold interpreter.
START_GRACE_S = 20.0

#: How long a cancelled group gets to die on SIGTERM before it is SIGKILLed.
TERM_GRACE_S = 10.0

#: The most recent console lines per live run — enough to explain a failed start
#: or a stubborn cancel, and not a second log to own.
_LOG_LINES = 40
_logs: dict[str, deque[str]] = {}
_procs: dict[str, subprocess.Popen] = {}
_state_lock = threading.Lock()


@dataclass(frozen=True)
class RunSpec:
    """What to run — the same choices the terminal runner takes."""

    group: str | None = None
    files: list[str] = field(default_factory=list)
    parallel: bool | None = None

    def to_args(self) -> list[str]:
        if self.files:
            args: list[str] = []
            for f in self.files:
                args += ["--file", f]
        elif self.group:
            args = ["--group", self.group]
        else:
            raise ValueError("a run needs a --group or at least one --file")
        if self.parallel is True:
            args.append("--parallel")
        elif self.parallel is False:
            args.append("--sequential")
        return args


def build_command(spec: RunSpec, runs_dir: Path, run_id: str) -> list[str]:
    """The exact command a person would type, plus the two flags that make it
    addressable: the id the page will watch, and the dir it lands in."""
    return [
        sys.executable, str(RUNNER),
        "--runs-dir", str(runs_dir),
        "--run-id", run_id,
        # The page reads the run's artifacts; a console stream would be a second
        # copy of the same information, and the page does not render consoles.
        "--no-live",
        *spec.to_args(),
    ]


def _drain(run_id: str, proc: subprocess.Popen) -> None:
    """Keep the run's console lines, bounded, in memory (never a second log)."""
    assert proc.stdout is not None
    buf = _logs.setdefault(run_id, deque(maxlen=_LOG_LINES))
    try:
        for line in proc.stdout:
            buf.append(line.rstrip())
    except Exception:  # noqa: BLE001 — a reader thread must never take the app down
        pass


def console(run_id: str) -> list[str]:
    """The last lines the run printed — for explaining a failed start or cancel."""
    return list(_logs.get(run_id, ()))


def is_running(run_id: str) -> bool:
    with _state_lock:
        proc = _procs.get(run_id)
    return proc is not None and proc.poll() is None


def spawn(spec: RunSpec, run_id: str) -> dict:
    """Start a run. Returns its id once the lock confirms it is really going.

    THE CONFIRMATION IS THE POINT. `Popen` succeeding only means a process was
    created — not that a test run began. A run that died at import would leave
    the page showing "running" over nothing, so this waits for the runner's own
    lock and reports the console if the process exits first.
    """
    runs_dir = Path(Paths.test_runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)

    held = read_lock(runs_dir)
    if held is not None and held.alive():
        raise RunInProgress(held, stale=False)

    cmd = build_command(spec, runs_dir, run_id)
    env = os.environ.copy()
    # WHO started it is the lock's data — the page can then say "started outside
    # this page" about someone else's run instead of guessing.
    env["COGITATE_RUN_ORIGIN"] = "page"

    logger.info("spawning a test run: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=str(Paths.root),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=env,
        # ITS OWN PROCESS GROUP. This is what makes the cancel a group kill
        # rather than a wish: pytest and its xdist workers all land in this
        # group, and the group is what gets signalled.
        start_new_session=True,
    )
    with _state_lock:
        _procs[run_id] = proc
        _logs[run_id] = deque(maxlen=_LOG_LINES)
    threading.Thread(target=_drain, args=(run_id, proc), daemon=True).start()

    key = activity.note_start(f"test run {run_id}")
    deadline = time.monotonic() + START_GRACE_S
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            activity.note_done(key)
            raise RuntimeError(
                f"the run exited immediately (code {proc.returncode}) — "
                + " / ".join(console(run_id)[-3:] or ["no output"])
            )
        held = read_lock(runs_dir)
        if held is not None and held.id == run_id:
            return {"run_id": run_id, "pid": proc.pid, "pgid": held.pgid,
                    "started": held.started, "origin": held.origin}
        time.sleep(0.05)

    activity.note_done(key)
    raise TimeoutError(
        f"the run did not take the lock within {START_GRACE_S:.0f}s — "
        + " / ".join(console(run_id)[-3:] or ["no output"])
    )


def _group_alive(pgid: int) -> bool:
    """Whether any process in a group is still there."""
    if pgid <= 0:
        return False
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True
    return True


def _group_pids(pgid: int) -> list[int]:
    """The LIVE members of a process group — so a survivor can be NAMED.

    Zombies are excluded deliberately: a killed-but-unreaped process has already
    released everything it held (file descriptors, the database), and counting it
    as a survivor turns a clean kill into a scary report nobody should believe.
    """
    try:
        out = subprocess.run(["ps", "-o", "pid=,stat=", "-g", str(pgid)],
                             capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return []
    pids: list[int] = []
    for line in out.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0].isdigit() and not parts[1].startswith("Z"):
            pids.append(int(parts[0]))
    return pids


def cancel(run_id: str) -> dict:
    """Kill a run the PAGE started: the whole group, then verify.

    Reads the GROUP from the lock rather than from this process's memory, so it
    works for a run spawned before a backend restart — and refuses anything this
    page did not start (see the module docstring).
    """
    runs_dir = Path(Paths.test_runs_dir)
    held = read_lock(runs_dir)
    if held is None:
        return {"cancelled": False, "reason": "no run is in progress"}
    if held.id != run_id:
        return {"cancelled": False,
                "reason": f"a different run is in progress: {held.describe()}"}
    if held.origin != "page":
        return {"cancelled": False,
                "reason": f"this run was started outside the page ({held.origin}) — "
                          "stopping someone else's run is a deliberate act, not a "
                          "side effect of a button"}
    if not held.alive():
        clear_stale(runs_dir)
        return {"cancelled": False, "reason": "the run was already gone; its stale "
                                              "lock has been cleared"}

    pgid = held.pgid or held.pid
    logger.warning("cancelling run %s — TERM to process group %s", run_id, pgid)
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    deadline = time.monotonic() + TERM_GRACE_S
    while time.monotonic() < deadline and _group_alive(pgid):
        time.sleep(0.2)
    forced = False
    if _group_alive(pgid):
        logger.warning("run %s ignored SIGTERM — killing group %s", run_id, pgid)
        forced = True
        try:
            os.killpg(pgid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        time.sleep(0.5)

    # The dead can hold the door open: a lock left by a killed run refused every
    # future run, and this caller has just VERIFIED the run is gone — which is
    # the condition that makes clearing it honest rather than automatic.
    with _state_lock:
        proc = _procs.pop(run_id, None)
    if proc is not None:
        # Reap OUR child. Until it is waited on it lingers as a zombie, which is
        # not a survivor but does wear a pid — and the pid is what gets reported.
        try:
            proc.wait(timeout=5)
        except Exception:  # noqa: BLE001
            pass
    survivors = _group_pids(pgid)
    released = clear_stale(runs_dir) is not None or read_lock(runs_dir) is None

    return {
        "cancelled": True,
        "forced": forced,
        "released_lock": released,
        "survivors": survivors,
        "console": console(run_id)[-5:],
    }


def forget(run_id: str) -> None:
    """Drop the in-memory handle once a run is over (the record is on disk)."""
    with _state_lock:
        _procs.pop(run_id, None)
        _logs.pop(run_id, None)


def lock_path_for(runs_dir: Path | None = None) -> Path:
    """Where the lock lives — exposed so callers do not rebuild the path."""
    return lock_path(runs_dir or Path(Paths.test_runs_dir))
