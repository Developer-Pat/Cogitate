"""The agent-store write defects and their fixes.

THREE DEFECTS, each of which looked fine alone:

1. The lock was created in ``__init__`` — and the tool handlers build a
   FRESH store per call, so every concurrent write held a different lock
   and nothing was serialized. Decorative.
2. The "atomic" write used a FIXED temp name (``state.json.tmp``), so two
   writers collided on it: one's ``replace`` consumed the other's temp and
   it died with FileNotFoundError.
3. An unreadable file returned an EMPTY store with a reassuring log line
   ("the next write repairs it"). It did not repair it — the empty read
   ARMED the next write, which stored only its own key and thereby ERASED
   every other fact.

Defects 1 and 2 are latent (single process, sync inline call). Defect 3 is
live regardless of concurrency: a corrupt file's contents are destroyed by
the next write, with no concurrency needed at all.

The race test below FAILED before the fix — writer A's key was destroyed
outright and the other thread crashed.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from app.core.path_lock import path_lock, write_atomic
from app.domain.agents.agent_state import AgentStateStore, AgentStateUnreadable


# ---- defect 1: the lock must be per PATH, not per instance -------------


def test_the_lock_is_shared_across_instances(tmp_path):
    """A fresh store per call must not mean a fresh lock."""
    a = AgentStateStore(base_dir=str(tmp_path))
    b = AgentStateStore(base_dir=str(tmp_path))

    assert a._lock is b._lock, "a fresh store per call left the write unserialized"


def test_different_paths_get_different_locks(tmp_path):
    x = AgentStateStore(base_dir=str(tmp_path / "x"))
    y = AgentStateStore(base_dir=str(tmp_path / "y"))

    assert x._lock is not y._lock, "unrelated workspaces must not block each other"


def test_path_lock_is_stable_for_a_path(tmp_path):
    assert path_lock(tmp_path / "f") is path_lock(tmp_path / "f")


# ---- the race itself (the regression that failed before) ---------------


def test_concurrent_writers_do_not_destroy_each_other(tmp_path):
    """Emulate two turns for one agent writing DIFFERENT keys at once.

    Before the fix this failed two ways: a writer's key vanished, and a
    writer crashed on the shared temp file. It is the exact harness that
    reproduced the bug, kept as the guard.
    """
    d = str(tmp_path)
    lost = {"a": 0, "b": 0}
    crashes: list[str] = []

    def writer(tag: str, key: str) -> None:
        for i in range(40):
            try:
                AgentStateStore(base_dir=d).set_fact(key, f"{tag}{i}")
                back = AgentStateStore(base_dir=d).read()["facts"]
                if key not in back:
                    lost[tag] += 1
            except Exception as e:  # noqa: BLE001 - the test asserts on this
                crashes.append(f"{tag}: {type(e).__name__}: {e}")

    threads = [
        threading.Thread(target=writer, args=("a", "alpha")),
        threading.Thread(target=writer, args=("b", "beta")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    final = AgentStateStore(base_dir=d).read()["facts"]
    assert {"alpha", "beta"} <= set(final), f"a key was destroyed: {sorted(final)}"
    assert lost == {"a": 0, "b": 0}, f"a writer lost its own write: {lost}"
    assert crashes == [], f"concurrent writers crashed: {crashes[:3]}"


def test_no_temp_litter_is_left_behind(tmp_path):
    d = str(tmp_path)
    AgentStateStore(base_dir=d).set_fact("k", "v")

    leftovers = [p.name for p in Path(d).iterdir() if ".tmp" in p.name]
    assert leftovers == [], f"temp litter: {leftovers}"


# ---- defect 3: an unreadable file must REFUSE, not be erased ----------


def test_a_corrupt_store_refuses_instead_of_returning_empty(tmp_path):
    """The dangerous one: the old empty read let the next write erase it."""
    d = str(tmp_path)
    (Path(d) / "state.json").write_text('{"facts": {"keep": "me"}, "sou', encoding="utf-8")

    store = AgentStateStore(base_dir=d)
    with pytest.raises(AgentStateUnreadable):
        store.read()


def test_a_corrupt_store_is_not_erased_by_a_write(tmp_path):
    """The regression that matters: a write must not silently wipe it."""
    d = str(tmp_path)
    corrupt = '{"facts": {"keep": "me"}, "sou'
    (Path(d) / "state.json").write_text(corrupt, encoding="utf-8")

    with pytest.raises(AgentStateUnreadable):
        AgentStateStore(base_dir=d).set_fact("new", "value")

    # the file's bytes are untouched — nothing was written over the top
    assert (Path(d) / "state.json").read_text(encoding="utf-8") == corrupt


def test_a_MISSING_store_is_still_empty_and_writable(tmp_path):
    """A missing file is not a corrupt one — that path must still work."""
    store = AgentStateStore(base_dir=str(tmp_path / "fresh"))

    assert store.read() == {"facts": {}, "sources": []}
    store.set_fact("location", "Omaha")
    assert store.read()["facts"]["location"]["value"] == "Omaha"


# ---- write_atomic, the shared helper ----------------------------------


def test_write_atomic_replaces_content(tmp_path):
    target = tmp_path / "f.txt"
    write_atomic(target, "one")
    write_atomic(target, "two")

    assert target.read_text() == "two"
    assert [p.name for p in tmp_path.iterdir() if ".tmp" in p.name] == []


def test_write_atomic_cleans_up_when_the_write_fails(tmp_path, monkeypatch):
    """A failed write must not leave a temp file behind."""
    import os

    target = tmp_path / "f.txt"
    real_replace = os.replace

    def boom(*a, **k):
        raise OSError("disk on fire")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        write_atomic(target, "content")

    monkeypatch.setattr(os, "replace", real_replace)
    assert [p.name for p in tmp_path.iterdir() if ".tmp" in p.name] == []


def test_the_beat_store_shares_the_same_lock_fix(tmp_path):
    """The defects were one class in two stores — both must be fixed."""
    from app.domain.agents.agent_beats import AgentBeatStore

    a = AgentBeatStore(base_dir=str(tmp_path))
    b = AgentBeatStore(base_dir=str(tmp_path))

    assert a._lock is b._lock
