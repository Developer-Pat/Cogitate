"""
The RUN EVENT STREAM — the live record, read as it is written.

WHY TAIL A FILE, rather than pushing from an in-process queue:

- **It cannot lie.** Nothing is sent that was not written, and the file being
  tailed is the same record the run leaves behind. A queue could emit an event
  the run never wrote; a file cannot.
- **Replay is free.** A page that reloads mid-run catches up by reading from the
  start — no gap to reconstruct, no ring buffer to size, no missed-events bug.
- **No new machinery.** The spawn path needs no channel, no job runner and no
  shared state: the only state is a byte OFFSET.
- **It follows a run this process did not start** — a terminal run, the sweep —
  which is the case the "a run is in progress" answer depends on.

THE CLOSE RULES, because a stream that never ends is a hang:

- `run_end` in the file → the run is over; replay the rest and close.
- the run is not in progress (`no lock`, or a lock whose process is gone) and
  the file has stopped growing → close, saying WHICH it was: a run that finished
  and a run that was killed look identical from here, and reporting the second
  as the first (or the first as the second) is the kind of lie this page exists
  to avoid.
- while a run IS in progress, silence is normal (a slow test writes nothing) —
  so the stream stays open and only heartbeats, which also keep a proxy from
  timing the connection out.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Iterator
from pathlib import Path

from app.domain.testing.run_lock import read_lock

#: How often to look for new bytes. Fast enough to feel live; slow enough that a
#: 30-minute run is ~5,000 cheap stat calls rather than a busy loop.
POLL_S = 0.4

#: Silence after which a client is told the stream is still alive.
HEARTBEAT_S = 15.0

#: Silence after which a run that is NOT in progress is declared over. The lock
#: is the strong signal — it says no run is coming — so this only needs to be
#: long enough to cover the gap between a run's last event and its release.
ORPHAN_CLOSE_S = 5.0


def read_new_frames(path: Path, offset: int) -> tuple[list[tuple[int, str]], int]:
    """The COMPLETE lines written since `offset`, each with the offset it ENDS at.

    Two rules, and both matter:

    - A partial final line is NOT consumed. Half a JSON object is not an event,
      and emitting it would hand the client a parse error it cannot recover
      from. The remainder is re-read on the next poll, once its newline lands.
    - Splitting happens on BYTES, not on decoded text: a multi-byte character
      can straddle a read boundary, and decoding the chunk first would corrupt
      exactly the character at the seam.
    - **Each line carries its OWN offset.** A batch that shared one offset would
      make the stream's `id:` claim the client had received lines it had not —
      so a browser reconnecting mid-batch would resume PAST them and never see
      them. The id has to mean "everything up to here", line by line.
    """
    try:
        size = path.stat().st_size
        if size <= offset:
            return [], offset
        with open(path, "rb") as f:
            f.seek(offset)
            chunk = f.read(size - offset)
    except OSError:
        return [], offset

    frames: list[tuple[int, str]] = []
    consumed = 0
    rest = chunk
    while True:
        index = rest.find(b"\n")
        if index < 0:
            break
        consumed += index + 1
        frames.append((offset + consumed, rest[:index].decode("utf-8", errors="replace")))
        rest = rest[index + 1:]
    return frames, offset + consumed


def sse(event: str, *, event_id: int | None = None) -> str:
    """One SSE frame. The `id:` is the byte offset, so a browser that
    reconnects (EventSource sends `Last-Event-ID` by itself) resumes exactly
    where it stopped instead of replaying a 30-minute run."""
    head = f"id: {event_id}\n" if event_id is not None else ""
    return f"{head}data: {event}\n\n"


def _resolve(runs_dir: Path, run_id: str) -> Path | None:
    """Containment, exactly as the reader does it — a name arrives from a URL."""
    candidate = (runs_dir / run_id).resolve()
    if candidate.parent != runs_dir.resolve() or not candidate.is_dir():
        return None
    return candidate


async def run_event_stream(runs_dir: Path, run_id: str, offset: int = 0,
                           tail: bool = False) -> AsyncGenerator[str, None]:
    """The run's events as an SSE stream: replay, then follow, then close."""
    runs_dir = Path(runs_dir)
    run_dir = _resolve(runs_dir, run_id)
    if run_dir is None:
        yield sse(json.dumps({"t": "error", "message": "no such run"}))
        return

    events_path = run_dir / "events.jsonl"
    if tail:
        try:
            offset = events_path.stat().st_size
        except OSError:
            offset = 0
    if not events_path.exists():
        yield sse(json.dumps({
            "t": "error",
            "message": "this run has no events file — it was made before the "
                       "live record existed, or it never started",
        }))
        return

    idle = 0.0
    while True:
        frames, offset = read_new_frames(events_path, offset)
        for line_offset, line in frames:
            if not line.strip():
                continue
            yield sse(line, event_id=line_offset)
            if _is_end(line):
                return
        if frames:
            idle = 0.0
        else:
            idle += POLL_S

        if _finished(runs_dir) and idle >= ORPHAN_CLOSE_S:
            # The stream has nothing more to give and no run behind it. WHY it
            # stopped matters: a run that finished and a run that was killed look
            # the same from here, and telling a client its run "was killed" when
            # it simply ended is the kind of lie this page exists to avoid.
            if _has_end_event(events_path):
                yield sse(json.dumps({
                    "t": "stream_end",
                    "message": "the run has finished — nothing more will be written",
                }))
            else:
                yield sse(json.dumps({
                    "t": "stream_end",
                    "message": "the run is no longer in progress and its stream "
                               "stopped without an end event (it was killed)",
                }))
            return
        if idle >= HEARTBEAT_S and not frames:
            idle = 0.0
            yield ": keep-alive\n\n"
        await asyncio.sleep(POLL_S)


def _is_end(line: str) -> bool:
    try:
        event = json.loads(line)
    except ValueError:
        return False
    # `isinstance` before the comparison, and `bool()` around it: a JSON object
    # is `Any` to the type checker, and a bare `Any == str` would leak `Any` out
    # of a function that promises a bool (mypy is what noticed).
    return isinstance(event, dict) and bool(event.get("t") == "run_end")


def _has_end_event(path: Path, tail_bytes: int = 65536) -> bool:
    """Whether the file ALREADY holds a `run_end` — read at close time only."""
    try:
        size = path.stat().st_size
        with open(path, "rb") as f:
            f.seek(max(0, size - tail_bytes))
            chunk = f.read().decode("utf-8", errors="replace")
    except OSError:
        return False
    for line in chunk.splitlines():
        try:
            if json.loads(line).get("t") == "run_end":
                return True
        except ValueError:
            continue
    return False


def _finished(runs_dir: Path) -> bool:
    """Whether ANY run is still in progress — read from the lock, not guessed."""
    lock = read_lock(runs_dir)
    return lock is None or not lock.alive()


def iter_event_lines(path: Path, offset: int = 0) -> Iterator[tuple[int, str]]:
    """Every complete line, synchronously — the replay part, for tests and for
    a caller that only wants the record rather than a live stream."""
    while True:
        frames, offset = read_new_frames(path, offset)
        if not frames:
            return
        yield from frames
