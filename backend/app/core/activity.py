"""The in-flight registry (2026-09-12).

WHY IT EXISTS: the shutdown report must NAME what was running, not count it.
"2 items abandoned" is not actionable; "chat session 41, workflow job nightly"
is. So the app keeps a small, honest list of what is currently in flight, and
the shutdown drain reads it.

Deliberately tiny and in-memory. This is not a metrics system — it is the
answer to one question, asked once, at shutdown. Every operation swallows its
own errors: a registry that can break the thing it observes is worse than no
registry at all.

NOT YET WIRED INTO THE CHAT STREAM. That path's registration point is inside a
long-lived generator, and a careless edit there risks the stream itself — the
thing we would be trying to observe. The lifespan's own tasks and the
scheduler's jobs register today; the chat stream is a follow-up.
"""
from __future__ import annotations

import itertools
import logging
import threading
from contextlib import contextmanager
from typing import Dict, Iterator, List

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_next_id = itertools.count(1)
_active: Dict[int, str] = {}


def note_start(label: str) -> int:
    """Register something in flight; returns its key for :func:`note_done`."""
    try:
        with _lock:
            key = next(_next_id)
            _active[key] = label
            return key
    except Exception:  # pragma: no cover - the registry must never raise
        return -1


def note_done(key: int) -> None:
    """Deregister. Safe with an unknown key or a failed ``note_start``."""
    try:
        with _lock:
            _active.pop(key, None)
    except Exception:  # pragma: no cover
        pass


def snapshot() -> List[str]:
    """What is in flight right now, NAMED, in insertion order."""
    try:
        with _lock:
            return list(_active.values())
    except Exception:  # pragma: no cover
        return []


@contextmanager
def activity(label: str) -> Iterator[None]:
    """Mark a block as in flight: ``with activity("inbox drain"): ...``"""
    key = note_start(label)
    try:
        yield
    finally:
        note_done(key)
