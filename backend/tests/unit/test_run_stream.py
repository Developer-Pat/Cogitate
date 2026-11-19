"""The run's event stream — the frames, the offsets, and the honest close.

Two invariants carry the whole live feed, and both were got wrong once before
being pinned here:

1. **A partial line is never emitted.** Half a JSON object is a parse error the
   client cannot recover from, so the trailing fragment waits for its newline.
2. **Every frame carries its OWN offset.** If a batch shared one offset, the
   stream's `id:` would claim the client had received lines it had not — and a
   browser reconnecting mid-batch (EventSource sends `Last-Event-ID` by itself)
   would resume PAST them and never see them again.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.testing.run_lock import acquire, release
from app.domain.testing.stream import (
    _has_end_event,
    read_new_frames,
    run_event_stream,
    sse,
)


def write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_only_complete_lines_are_emitted(tmp_path: Path) -> None:
    events = write(tmp_path / "events.jsonl", '{"t":"a"}\n{"t":"b"}\n{"t":"hal')
    frames, offset = read_new_frames(events, 0)
    assert [line for _, line in frames] == ['{"t":"a"}', '{"t":"b"}']
    assert offset == len('{"t":"a"}\n{"t":"b"}\n')

    # and the fragment is delivered once its newline lands — nothing is lost
    with open(events, "a", encoding="utf-8") as f:
        f.write('f"}\n')
    more, offset = read_new_frames(events, offset)
    assert [line for _, line in more] == ['{"t":"half"}']


def test_each_frame_carries_its_own_offset(tmp_path: Path) -> None:
    events = write(tmp_path / "events.jsonl", '{"t":"a"}\n{"t":"b"}\n{"t":"c"}\n')
    frames, offset = read_new_frames(events, 0)
    ids = [frame_id for frame_id, _ in frames]
    assert ids == sorted(ids) and len(set(ids)) == 3, ids
    # the last frame's id IS the file's length: "everything up to here"
    assert ids[-1] == offset == events.stat().st_size
    # resuming from the FIRST id yields exactly the lines after it
    resumed, _ = read_new_frames(events, ids[0])
    assert [line for _, line in resumed] == ['{"t":"b"}', '{"t":"c"}']


def test_reading_from_an_offset_returns_only_what_is_new(tmp_path: Path) -> None:
    events = write(tmp_path / "events.jsonl", '{"t":"a"}\n')
    _, offset = read_new_frames(events, 0)
    assert read_new_frames(events, offset) == ([], offset)

    with open(events, "a", encoding="utf-8") as f:
        f.write('{"t":"b"}\n')
    frames, _ = read_new_frames(events, offset)
    assert [line for _, line in frames] == ['{"t":"b"}']


def test_multibyte_text_survives_a_read_boundary(tmp_path: Path) -> None:
    """Offsets land on LINE boundaries, so a character is never split — the
    reason the split happens on BYTES rather than on decoded text."""
    events = write(tmp_path / "events.jsonl", '{"t":"é"}\n{"t":"π — ok"}\n')
    frames, offset = read_new_frames(events, 0)
    assert [line for _, line in frames] == ['{"t":"é"}', '{"t":"π — ok"}']
    assert offset == events.stat().st_size
    # the offset after the FIRST line is a real boundary: reading from it yields
    # the second line intact, never a repair-character fragment
    resumed, _ = read_new_frames(events, frames[0][0])
    assert [line for _, line in resumed] == ['{"t":"π — ok"}']


def test_a_missing_file_is_not_an_error(tmp_path: Path) -> None:
    assert read_new_frames(tmp_path / "nope.jsonl", 0) == ([], 0)


def test_has_end_event_tells_finished_from_killed(tmp_path: Path) -> None:
    killed = write(tmp_path / "killed.jsonl", '{"t":"run_start"}\n{"t":"test"}\n')
    finished = write(tmp_path / "finished.jsonl",
                     '{"t":"run_start"}\n{"t":"run_end","exit":0}\n')
    assert _has_end_event(killed) is False
    assert _has_end_event(finished) is True


def test_the_sse_frame_format_carries_the_id(tmp_path: Path) -> None:
    frame = sse('{"t":"test"}', event_id=42)
    assert frame == 'id: 42\ndata: {"t":"test"}\n\n'


async def test_the_stream_replays_then_closes_on_run_end(tmp_path: Path) -> None:
    run_dir = tmp_path / "20260101-000000"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text(
        '{"t":"run_start","id":"20260101-000000"}\n'
        '{"t":"test","outcome":"passed"}\n'
        '{"t":"run_end","exit":0}\n',
        encoding="utf-8",
    )
    chunks = [c async for c in run_event_stream(tmp_path, "20260101-000000")]
    payloads = [json.loads(c.split("data: ", 1)[1]) for c in chunks if "data: " in c]
    assert [p["t"] for p in payloads] == ["run_start", "test", "run_end"]


async def test_the_stream_says_no_such_run(tmp_path: Path) -> None:
    chunks = [c async for c in run_event_stream(tmp_path, "19990101-000000")]
    assert "no such run" in chunks[0]


async def test_the_stream_says_so_when_a_run_has_NO_events_file(tmp_path: Path) -> None:
    (tmp_path / "20260101-000000").mkdir()
    chunks = [c async for c in run_event_stream(tmp_path, "20260101-000000")]
    assert "no events file" in chunks[0]


async def test_a_killed_run_closes_WITHOUT_claiming_it_finished(tmp_path: Path) -> None:
    """The lie to avoid: telling a client its run "finished" when the process
    was killed. The close says which it was — and it must not hang forever."""
    run_dir = tmp_path / "20260101-000000"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text('{"t":"run_start"}\n', encoding="utf-8")
    chunks = []
    async for chunk in run_event_stream(tmp_path, "20260101-000000"):
        chunks.append(chunk)
        if "stream_end" in chunk:
            break
    tail = json.loads([c for c in chunks if "stream_end" in c][0].split("data: ", 1)[1])
    assert "killed" in tail["message"]


async def test_a_finished_run_replays_from_an_offset(tmp_path: Path) -> None:
    """A reload mid-run asks for what it missed rather than starting over."""
    run_dir = tmp_path / "20260101-000000"
    run_dir.mkdir()
    events = run_dir / "events.jsonl"
    events.write_text('{"t":"run_start"}\n{"t":"test"}\n{"t":"run_end"}\n',
                      encoding="utf-8")
    frames, _ = read_new_frames(events, 0)
    offset = frames[0][0]
    chunks = [c async for c in run_event_stream(tmp_path, "20260101-000000", offset=offset)]
    payloads = [json.loads(c.split("data: ", 1)[1]) for c in chunks if "data: " in c]
    assert [p["t"] for p in payloads] == ["test", "run_end"]


async def test_a_stream_STAYS_OPEN_while_the_run_is_in_progress(tmp_path: Path) -> None:
    """Silence during a run is normal — a slow test writes nothing. Closes only
    once nothing is in progress, so the lock is what decides."""
    run_dir = tmp_path / "20260101-000000"
    run_dir.mkdir()
    (run_dir / "events.jsonl").write_text('{"t":"run_start"}\n', encoding="utf-8")
    acquire(tmp_path, "20260101-000000", origin="page")
    try:
        stream = run_event_stream(tmp_path, "20260101-000000")
        first = await stream.__anext__()
        assert "run_start" in first
        # The run is in progress: the next frame must NOT be a close. It is a
        # keep-alive or a poll — either way, no `stream_end`.
        second = await stream.__anext__()
        assert "stream_end" not in second
        await stream.aclose()
    finally:
        release(tmp_path, "20260101-000000")


@pytest.mark.parametrize("name", ["../escape", "20260101-000000/../..", "no-such-run"])
async def test_the_stream_is_CONTAINED(tmp_path: Path, name: str) -> None:
    """The name arrives from a URL — it must not walk out of the runs dir."""
    chunks = [c async for c in run_event_stream(tmp_path, name)]
    assert "no such run" in chunks[0]
