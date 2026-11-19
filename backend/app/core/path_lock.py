"""Per-path write locks (2026-09-11).

WHY THIS EXISTS: the agent stores used to create their lock in
``__init__`` — and the tool handlers build a FRESH store per call, so
every concurrent write held a DIFFERENT lock and nothing was serialized.
The lock was decorative: the code looked guarded and was not.

A lock keyed by the file's path is shared by every instance touching the
same file, so "a fresh store per call" no longer means "a fresh lock".

HONEST SCOPE — read this before trusting it:

- It serializes THREADS WITHIN ONE PROCESS.
- It does NOT coordinate separate processes: a multi-worker deployment,
  or a script writing beside the running app, is NOT covered. A file
  lock (``fcntl``) would be needed for that, and is deliberately not
  used yet — the app is single-process, and a stale lockfile is a worse
  failure than the one it prevents.
- Today the agent stores are called synchronously from inside the async
  tool path, so the read-modify-write cannot interleave on the event
  loop at all. This is insurance against a future threadpool, workflow,
  or worker caller — not a fix for a live race.

One more thing it does NOT do: prevent a LOST UPDATE. Two callers can
still read the same base and the second write wins. That needs a
revision/compare-and-swap at the store level, which is a separate
decision (see the known-issues entry).
"""

from __future__ import annotations

import threading
from pathlib import Path

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def path_lock(path: str | Path) -> threading.Lock:
    """The shared lock for one file path (one lock per absolute path)."""
    key = str(Path(path).absolute())
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def write_atomic(path: str | Path, text: str, suffix: str = ".tmp") -> None:
    """Write text to a file atomically, with a UNIQUE temp per writer.

    THE SHARED-TEMP FIX (2026-09-11): the stores used a FIXED temp name
    (``state.json.tmp``), so two writers collided on it — one's replace
    consumed the other's temp and it died with FileNotFoundError. The
    temp is unique per writer and removed on failure, and it lives in
    the SAME directory as the target so the replace stays atomic (same
    filesystem).
    """
    import os
    import tempfile

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=target.name + ".", suffix=suffix
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_name, target)  # atomic on POSIX
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
