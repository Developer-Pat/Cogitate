"""
The RUN LOCK — one run at a time, and the second attempt says so.

WHY A LOCK AT ALL. pytest needs exclusive access to the database, and two
overlapping runs do not present as "two runs" — they present as **flaky tests**.
That is the worst possible presentation: the suite looks unreliable, and the real
cause (a collision) is invisible in the output. The lock turns a collision into
a sentence someone can act on.

WHY THE RUNNER OWNS IT. If the runner takes the lock, then a run started from a
terminal, from the page and from the system sweep all collide through ONE
mechanism. A lock only the page respected would leave the page blind to the
terminal run it was about to collide with.

WHY A FILE, AND NOT A PROCESS-LOCAL FLAG. The contenders are different processes
and different programs — a shell script and a web server. Shared state has to be
shared.

THE STALENESS RULE, which is the whole difficulty. A lock whose process is gone
is not a lock: it is debris from a crash, and refusing forever because of it
would make the suite unrunnable until somebody found a hidden dotfile. So a
stale lock is **detected and NAMED**, and clearing it is an **explicit action**
(`clear_stale`). It is never taken over silently — a lock that clears itself
when it *thinks* it is stale is a lock that can clear itself while another run
is starting, which is the collision it exists to prevent.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

#: The lock's filename, inside the runs dir — beside the runs it protects, so a
#: moved or copied runs dir carries its own state.
LOCK_NAME = ".run.lock"

#: How long an UNREADABLE lock file must sit before it counts as debris from a
#: crash during acquisition. A run writes its lock in the microseconds after
#: creating it, so anything older than this is not mid-write.
UNREADABLE_GRACE_S = 5.0


@dataclass(frozen=True)
class RunLock:
    """Who holds the lock, and since when."""

    id: str
    pid: int
    pgid: int
    started: str
    origin: str  # "page" | "terminal" | "sweep" — who started the run

    def as_dict(self) -> dict:
        return asdict(self)

    def alive(self) -> bool:
        """Is the holder's process still there?

        Err toward ALIVE. An unknown failure (a permission error, an odd OSError)
        must not be read as "the holder is gone" — a false stale read is what
        lets a second run start on top of a live one.
        """
        return process_alive(self.pid)

    def describe(self) -> str:
        return (f"run {self.id} (pid {self.pid}, started {self.started}, "
                f"origin {self.origin})")


class RunInProgress(RuntimeError):
    """Raised when the lock is held. Carries the holder, so a caller can SAY so.

    `stale` distinguishes the two very different situations: a live run (wait for
    it, or go find it) versus debris from a crash (clear it, deliberately).
    """

    def __init__(self, lock: RunLock | None, stale: bool, unreadable: bool = False):
        self.lock = lock
        self.stale = stale
        self.unreadable = unreadable
        if unreadable:
            message = ("a run lock exists but cannot be read — a run may have "
                       "crashed while starting one")
        elif lock is not None and stale:
            message = f"a run is NOT in progress, but its lock is stale: {lock.describe()}"
        elif lock is not None:
            message = f"a run is in progress: {lock.describe()}"
        else:
            message = "a run lock is held by an unknown run"
        super().__init__(message)


def process_alive(pid: int) -> bool:
    """Whether a pid belongs to a live process (used for staleness)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except OSError:
        return True  # unknown — assume alive (see `alive`)
    return True


def lock_path(runs_dir: Path) -> Path:
    return Path(runs_dir) / LOCK_NAME


def read_lock(runs_dir: Path) -> RunLock | None:
    """The lock as written, or None when there is none (or it is unreadable)."""
    path = lock_path(runs_dir)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    try:
        return RunLock(
            id=str(payload["id"]),
            pid=int(payload["pid"]),
            pgid=int(payload.get("pgid") or 0),
            started=str(payload.get("started") or ""),
            origin=str(payload.get("origin") or "unknown"),
        )
    except (KeyError, TypeError, ValueError):
        return None


def unreadable_is_debris(runs_dir: Path) -> bool:
    """An unreadable lock, old enough not to be mid-write (see the grace note)."""
    path = lock_path(runs_dir)
    try:
        return (time.time() - path.stat().st_mtime) > UNREADABLE_GRACE_S
    except OSError:
        return False


def acquire(runs_dir: Path, run_id: str, origin: str = "terminal") -> RunLock:
    """Take the lock for `run_id`, or raise RunInProgress naming the holder.

    O_EXCL is the whole mechanism: the create IS the test, so two processes
    cannot both believe they won.
    """
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    lock = RunLock(
        id=run_id,
        pid=os.getpid(),
        pgid=os.getpgid(0),
        started=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        origin=origin,
    )
    path = lock_path(runs_dir)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        held = read_lock(runs_dir)
        if held is None:
            raise RunInProgress(None, stale=unreadable_is_debris(runs_dir),
                                unreadable=True) from None
        raise RunInProgress(held, stale=not held.alive()) from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(lock.as_dict(), f)
    except OSError:
        # No lock content means no lock: an empty file would refuse every future
        # run for no stated reason.
        path.unlink(missing_ok=True)
        raise
    return lock


def release(runs_dir: Path, run_id: str) -> bool:
    """Release the lock — but ONLY if it is still ours.

    The id check is not politeness: a run whose `finally` fires after someone
    cleared a stale lock and started a NEW run would otherwise delete the new
    run's lock and let a third run start on top of it.
    """
    held = read_lock(runs_dir)
    if held is None or held.id != run_id:
        return False
    try:
        lock_path(runs_dir).unlink()
        return True
    except OSError:
        return False


def clear_stale(runs_dir: Path) -> RunLock | None:
    """The EXPLICIT action: remove a lock whose run is gone (never a live one).

    Returns the lock that was cleared, or None when there was nothing to clear.
    Raises RunInProgress when the lock is genuinely held — clearing a live lock
    is how two runs end up on one database.
    """
    held = read_lock(runs_dir)
    if held is None:
        path = lock_path(runs_dir)
        if path.exists():
            if not unreadable_is_debris(runs_dir):
                raise RunInProgress(None, stale=False, unreadable=True)
            path.unlink(missing_ok=True)
        return None
    if held.alive():
        raise RunInProgress(held, stale=False)
    lock_path(runs_dir).unlink(missing_ok=True)
    return held
