"""The testing API's run endpoints.

Two things here are worth more than the average route test:

- **`/runs/current` must be matched as a LITERAL path.** Declared after
  `/{run_id}` it would be read as a run id, and the answer would be a 404 for a
  route that exists — the exact bug the sessions routes were fixed for.
- **"A run is in progress" is the RUNNER's answer, read from its lock.** A
  page-side notion of "running" is the fabricated progress bar this page
  replaced, so the endpoint is asserted to report the lock verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.requests import Request

from app.api.v1.testing.router import (
    get_current_run,
    get_run,
    get_run_events,
    get_runs,
)
from app.core.config import Paths
from app.domain.testing.reports import list_reports
from app.domain.testing.run_lock import acquire, read_lock, release


def a_run(runs_dir: Path, run_id: str = "20260101-000000", with_end: bool = True,
          selection: list[str] | None = None) -> Path:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    start: dict[str, object] = {
        "t": "run_start", "id": run_id, "kind": "pytest", "group": "unit",
        "files": 3, "parallel": True, "backend": "healthy",
    }
    # A real run records WHAT it selected, which is how a self-test run is
    # identifiable at all (`reports._is_self_test`).
    if selection is not None:
        start["selection"] = selection
    lines = [
        json.dumps(start),
        json.dumps({"t": "test", "nodeid": "tests/unit/x.py::test_y",
                    "outcome": "skipped", "reason": "needs Ollama"}),
        json.dumps({"t": "summary", "counts": {"passed": 2, "skipped": 1},
                    "duration_s": 1.5}),
    ]
    if with_end:
        lines.append(json.dumps({"t": "run_end", "exit": 0, "elapsed_s": 2.0}))
    (run_dir / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (run_dir / "report.xml").write_text(
        '<testsuites><testsuite name="pytest" tests="3" failures="0" errors="0"'
        ' skipped="1" time="1.5">'
        '<testcase classname="tests.unit.x" name="test_y" time="0.1">'
        '<skipped message="needs Ollama"/></testcase>'
        '<testcase classname="tests.unit.x" name="test_z" time="0.1"/>'
        "</testsuite></testsuites>",
        encoding="utf-8",
    )
    return run_dir


@pytest.fixture
def runs_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the locator at a temp runs dir — the endpoints resolve it per call,
    so the whole router follows without a single path argument."""
    target = tmp_path / "test-runs"
    target.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Paths, "test_runs_dir", target)
    return target


@pytest.fixture
def trash_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The same for the trash — a delete test must never touch the REAL one.

    `root` moves with it: the answer names where the run went as a path RELATIVE
    to the project root, so the assertion has to be about that shape, not about
    a temp dir that merely happens to be absolute.
    """
    target = tmp_path / "trash"
    monkeypatch.setattr(Paths, "trash_dir", target)
    monkeypatch.setattr(Paths, "root", tmp_path)
    return target


def request_with(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({
        "type": "http", "method": "GET", "path": "/", "headers": headers or [],
    })


async def test_current_run_is_the_LITERAL_path_not_a_run_id(runs_dir: Path) -> None:
    a_run(runs_dir, "20260101-000000")
    # A path parameter would try to open a run called "current" and 404.
    answer = await get_current_run()
    assert answer == {"running": False, "stale": False, "lock": None}


async def test_current_run_reports_the_LOCK_verbatim(runs_dir: Path) -> None:
    acquire(runs_dir, "20260101-000000", origin="terminal")
    try:
        answer = await get_current_run()
        assert answer["running"] is True
        assert answer["stale"] is False
        assert answer["lock"] is not None
        assert answer["lock"]["id"] == "20260101-000000"
        assert answer["lock"]["origin"] == "terminal"
    finally:
        release(runs_dir, "20260101-000000")


async def test_runs_are_listed_newest_first(runs_dir: Path) -> None:
    a_run(runs_dir, "20260101-000000")
    a_run(runs_dir, "20260102-000000")
    answer = await get_runs()
    assert answer["available"] is True
    assert answer["count"] == 2
    names = [r["name"] for r in answer["reports"]]
    assert names[0] == "20260102-000000"


async def test_an_empty_runs_dir_says_so_rather_than_failing(runs_dir: Path) -> None:
    answer = await get_runs()
    assert answer == {"available": False, "count": 0, "reports": []}


async def test_a_run_detail_carries_the_SKIP_REASON(runs_dir: Path) -> None:
    a_run(runs_dir, "20260101-000000")
    detail = await get_run("20260101-000000")
    assert detail["counts"] == {"passed": 2, "skipped": 1}
    assert [s["where"] for s in detail["skips"]] == ["tests.unit.x::test_y"]
    assert "Ollama" in detail["skips"][0]["reason"]


async def test_an_unknown_run_is_a_404(runs_dir: Path) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as caught:
        await get_run("19990101-000000")
    assert caught.value.status_code == 404


async def test_the_events_endpoint_replays_and_closes(runs_dir: Path) -> None:
    a_run(runs_dir, "20260101-000000")
    response = await get_run_events("20260101-000000", request_with())
    chunks = [c async for c in response.body_iterator]
    payloads = [json.loads(c.split("data: ", 1)[1]) for c in chunks if "data: " in c]
    assert [p["t"] for p in payloads] == ["run_start", "test", "summary", "run_end"]
    assert response.media_type == "text/event-stream"


async def test_the_events_endpoint_resumes_from_LAST_EVENT_ID(runs_dir: Path) -> None:
    """A browser reconnecting sends this header by itself; the stream must
    continue rather than replay a whole run."""
    run_dir = a_run(runs_dir, "20260101-000000")
    from app.domain.testing.stream import read_new_frames

    frames, _ = read_new_frames(run_dir / "events.jsonl", 0)
    offset = frames[0][0]
    response = await get_run_events(
        "20260101-000000",
        request_with([(b"last-event-id", str(offset).encode())]),
    )
    chunks = [c async for c in response.body_iterator]
    payloads = [json.loads(c.split("data: ", 1)[1]) for c in chunks if "data: " in c]
    assert [p["t"] for p in payloads] == ["test", "summary", "run_end"]


async def test_tail_true_skips_what_already_happened(runs_dir: Path) -> None:
    a_run(runs_dir, "20260101-000000")
    response = await get_run_events("20260101-000000", request_with(), tail=True)
    chunks = [c async for c in response.body_iterator]
    # Nothing new to read; the stream still closes honestly (never hangs).
    assert all("run_start" not in c for c in chunks)
    assert any("stream_end" in c for c in chunks)


async def test_STARTING_a_run_is_refused_while_one_is_in_progress(runs_dir: Path) -> None:
    """409, naming the run — the lock is the gate for the page exactly as it is
    for a terminal."""
    from fastapi import HTTPException

    from app.api.v1.testing.router import RunRequest, start_run

    acquire(runs_dir, "20260101-000000", origin="terminal")
    try:
        with pytest.raises(HTTPException) as caught:
            await start_run(RunRequest(group="unit"))
        assert caught.value.status_code == 409
        assert "20260101-000000" in str(caught.value.detail)
    finally:
        release(runs_dir, "20260101-000000")


async def test_CANCEL_refuses_a_run_started_outside_the_page(runs_dir: Path) -> None:
    """A terminal run is watched, not stopped: killing someone else's run is a
    deliberate act, not the side effect of a button."""
    from app.api.v1.testing.router import cancel_run

    acquire(runs_dir, "20260101-000000", origin="sweep")
    try:
        result = await cancel_run("20260101-000000")
        assert result["cancelled"] is False
        assert "outside the page" in result["reason"]
        assert read_lock(runs_dir) is not None   # untouched
    finally:
        release(runs_dir, "20260101-000000")


async def test_DELETING_a_run_MOVES_it_to_the_trash_and_says_where(
    runs_dir: Path, trash_dir: Path,
) -> None:
    """Delete is RECOVERABLE: the folder keeps its artifacts, in one piece.

    A person deleting a run gets one folder moved, and the answer names where it
    went — an action that cannot be undone silently is not a user-space action.
    """
    from app.api.v1.testing.router import delete_run

    run_dir = a_run(runs_dir, "20260101-000000")
    before = sorted(p.name for p in run_dir.iterdir())

    answer = await delete_run("20260101-000000")

    assert answer["deleted"] is True
    assert answer["name"] == "20260101-000000"
    assert answer["moved_to"] == "trash/test-runs/20260101-000000"
    assert sorted(answer["contents"]) == before
    assert not run_dir.exists()                                   # gone from the runs
    landed = trash_dir / "test-runs" / "20260101-000000"
    assert sorted(p.name for p in landed.iterdir()) == before      # intact in the trash
    assert list_reports() == []                                    # and the page agrees


async def test_deleting_an_unknown_run_is_a_404(runs_dir: Path, trash_dir: Path) -> None:
    from fastapi import HTTPException

    from app.api.v1.testing.router import delete_run

    with pytest.raises(HTTPException) as caught:
        await delete_run("19990101-000000")
    assert caught.value.status_code == 404


async def test_deleting_the_RUNNING_run_is_refused_with_the_locks_sentence(
    runs_dir: Path, trash_dir: Path,
) -> None:
    """409, not 404: the run exists — STATE is what stops it.

    Deleting the folder under a live run would break its stream and strand the
    artifacts it is still writing.
    """
    from fastapi import HTTPException

    from app.api.v1.testing.router import delete_run

    run_dir = a_run(runs_dir, "20260101-000000")
    acquire(runs_dir, "20260101-000000", origin="page")
    try:
        with pytest.raises(HTTPException) as caught:
            await delete_run("20260101-000000")
        assert caught.value.status_code == 409
        assert "20260101-000000" in str(caught.value.detail)
        assert run_dir.exists()                                   # untouched
    finally:
        release(runs_dir, "20260101-000000")


async def test_a_STALE_lock_does_not_protect_a_dead_run(runs_dir: Path,
                                                       trash_dir: Path) -> None:
    """A crashed run is debris, not a run in progress — its folder can go."""
    from app.api.v1.testing.router import delete_run

    run_dir = a_run(runs_dir, "20260101-000000")
    payload = json.dumps({"id": "20260101-000000", "pid": 999999, "pgid": 999999,
                          "started": "2026-01-01T00:00:00", "origin": "terminal"})
    (runs_dir / ".run.lock").write_text(payload, encoding="utf-8")
    try:
        answer = await delete_run("20260101-000000")
        assert answer["deleted"] is True
        assert not run_dir.exists()
    finally:
        (runs_dir / ".run.lock").unlink(missing_ok=True)


async def test_the_trash_never_overwrites_an_earlier_copy(runs_dir: Path,
                                                         trash_dir: Path) -> None:
    """A restored run deleted a second time lands BESIDE the first, not on top.

    Silently replacing the copy already in the trash would destroy the very
    thing the trash exists to keep.
    """
    from app.api.v1.testing.router import delete_run

    a_run(runs_dir, "20260101-000000")
    one = await delete_run("20260101-000000")
    assert one["moved_to"] == "trash/test-runs/20260101-000000"

    a_run(runs_dir, "20260101-000000")           # restored, same name
    two = await delete_run("20260101-000000")
    assert two["moved_to"] == "trash/test-runs/20260101-000000-2"
    names = sorted(p.name for p in (trash_dir / "test-runs").iterdir())
    assert names == ["20260101-000000", "20260101-000000-2"]


async def test_the_run_name_cannot_WALK_OUT_of_the_runs_dir(runs_dir: Path,
                                                            trash_dir: Path) -> None:
    """The name arrives from a URL: containment is checked on the RESOLVED path."""
    from fastapi import HTTPException

    from app.api.v1.testing.router import delete_run

    outside = runs_dir.parent / "outside"
    outside.mkdir()
    (outside / "report.md").write_text("not a run of ours", encoding="utf-8")
    for name in ("../outside", "..%2Foutside", "../outside/", "."):
        with pytest.raises(HTTPException) as caught:
            await delete_run(name)
        assert caught.value.status_code == 404
    assert outside.exists()


# ── a self-test run is MARKED, so history cannot be misread ──────────────────


async def test_a_self_test_run_is_MARKED_by_what_it_RAN(runs_dir: Path) -> None:
    """A deliberately red run must not read as the suite failing.

    The flag comes from the run's own recorded SELECTION — the fixture's files and
    nothing else. A run that mixed the fixture with the suite is a different thing
    and is NOT marked: a convenient label is what this page exists to avoid.
    """
    a_run(runs_dir, "20260101-000000", selection=["selftest/test_page_exercise.py"])
    a_run(runs_dir, "20260101-000001", selection=["tests/unit/x.py"])
    a_run(runs_dir, "20260101-000002", selection=["selftest/test_page_exercise.py",
                                                  "tests/unit/x.py"])   # a mixture
    a_run(runs_dir, "20260101-000003")                                   # no selection

    flags = {r["name"]: r["self_test"] for r in (await get_runs())["reports"]}
    assert flags["20260101-000000"] is True
    assert flags["20260101-000001"] is False
    assert flags["20260101-000002"] is False      # a mixture is not a self-test
    assert flags["20260101-000003"] is False      # not knowing is not a guess


# ── retiring several runs at once ────────────────────────────────────────────


async def test_RETIRING_several_runs_moves_each_and_answers_per_run(
    runs_dir: Path, trash_dir: Path,
) -> None:
    """A batch is answered for one run at a time — never with a bare success."""
    from app.api.v1.testing.router import RetireRequest, retire_runs

    a_run(runs_dir, "20260101-000000")
    a_run(runs_dir, "20260101-000001")

    answer = await retire_runs(RetireRequest(runs=["20260101-000000", "20260101-000001"]))

    assert sorted(r["name"] for r in answer["retired"]) == \
        ["20260101-000000", "20260101-000001"]
    assert answer["refused"] == []
    assert answer["missing"] == []
    assert sorted(p.name for p in (trash_dir / "test-runs").iterdir()) == \
        ["20260101-000000", "20260101-000001"]
    assert list_reports() == []


async def test_a_retire_batch_REFUSES_the_running_run_and_still_moves_the_rest(
    runs_dir: Path, trash_dir: Path,
) -> None:
    """The refusal is BY NAME while the others go.

    Aborting the whole batch at the first refusal would leave a person guessing
    which of their nine runs were moved.
    """
    from app.api.v1.testing.router import RetireRequest, retire_runs

    live = a_run(runs_dir, "20260101-000000")
    other = a_run(runs_dir, "20260101-000001")
    acquire(runs_dir, "20260101-000000", origin="page")
    try:
        answer = await retire_runs(
            RetireRequest(runs=["20260101-000000", "20260101-000001"])
        )
        assert [r["name"] for r in answer["refused"]] == ["20260101-000000"]
        assert "20260101-000000" in answer["refused"][0]["reason"]
        assert [r["name"] for r in answer["retired"]] == ["20260101-000001"]
        assert live.exists()          # the running run is untouched
        assert not other.exists()     # and the other one went
    finally:
        release(runs_dir, "20260101-000000")


async def test_a_name_that_is_not_a_run_is_MISSING_not_fatal(
    runs_dir: Path, trash_dir: Path,
) -> None:
    """One stale name in a batch does not lose the rest of the selection."""
    from app.api.v1.testing.router import RetireRequest, retire_runs

    a_run(runs_dir, "20260101-000000")
    answer = await retire_runs(RetireRequest(runs=["20260101-000000", "19990101-000000"]))
    assert [r["name"] for r in answer["retired"]] == ["20260101-000000"]
    assert answer["missing"] == ["19990101-000000"]


async def test_retiring_NOTHING_is_refused(runs_dir: Path, trash_dir: Path) -> None:
    """An empty list is a request that names no run — 400, not a silent no-op."""
    from fastapi import HTTPException

    from app.api.v1.testing.router import RetireRequest, retire_runs

    with pytest.raises(HTTPException) as caught:
        await retire_runs(RetireRequest(runs=[]))
    assert caught.value.status_code == 400


# ── the trash: visible, with a way back, and one shelf at a time ────────────
#
# THE RUNS SHELF IS READ AND ACTED ON AT /api/v1/trash NOW. The three delegates
# that stood under /testing were a second address for one implementation, and
# they went with the last caller of them. What is still THIS page's own is the
# MOVE into the trash (`delete_run` / `retire`, asserted above); everything below
# asks the shelf at its own address, the way the page and Exa do.


async def test_the_trash_LISTS_what_was_retired_and_what_each_folder_holds(
    runs_dir: Path, trash_dir: Path, test_session,
) -> None:
    """The shelf can be read: what was retired, and what each folder holds."""
    from app.api.v1.testing.router import delete_run
    from app.api.v1.trash.router import get_shelf

    assert (await get_shelf("test-runs", test_session))["count"] == 0   # honest empty

    a_run(runs_dir, "20260101-000000")
    await delete_run("20260101-000000")

    answer = await get_shelf("test-runs", test_session)
    assert answer["count"] == 1
    assert answer["entries"][0]["name"] == "20260101-000000"
    # What the folder actually holds — this fixture writes two of the three
    # artifacts, and the listing reports the folder rather than a fixed list.
    assert sorted(answer["entries"][0]["files"]) == ["events.jsonl", "report.xml"]
    assert answer["entries"][0]["size_bytes"] > 0
    # A retired run has a record to restore to, so the way back is offered.
    assert answer["entries"][0]["restorable"] is True


async def test_RESTORE_puts_a_run_BACK(
    runs_dir: Path, trash_dir: Path, test_session,
) -> None:
    """The way out of the trash — which is what makes the delete a MOVE."""
    from app.api.v1.testing.router import delete_run
    from app.api.v1.trash.router import restore_entry

    a_run(runs_dir, "20260101-000000")
    await delete_run("20260101-000000")
    assert list_reports() == []

    answer = await restore_entry("test-runs", "20260101-000000", test_session)

    assert answer["restored"] is True
    assert answer["renamed"] is False
    # Relative to the project root — which the fixture points at a temp dir, so
    # the assertion is about the SHAPE the caller can print, not a real path.
    assert answer["restored_to"] == "test-runs/20260101-000000"
    assert [r["name"] for r in list_reports()] == ["20260101-000000"]
    assert trash_holds_no_runs(trash_dir)


def trash_holds_no_runs(trash_dir: Path) -> bool:
    """The trash holds no run FOLDERS — read directly, since an empty dir may
    simply not exist."""
    root = trash_dir / "test-runs"
    return not root.is_dir() or not any(p.is_dir() for p in root.iterdir())


async def test_restore_RENAMES_when_the_name_is_taken_again(
    runs_dir: Path, trash_dir: Path, test_session,
) -> None:
    """A run made again since comes back BESIDE it, and the answer says so.

    Silently returning a run under a name nobody asked for is the failure this
    flag exists to prevent.
    """
    from app.api.v1.testing.router import delete_run
    from app.api.v1.trash.router import restore_entry

    a_run(runs_dir, "20260101-000000")
    await delete_run("20260101-000000")
    a_run(runs_dir, "20260101-000000")           # the same name, made again

    answer = await restore_entry("test-runs", "20260101-000000", test_session)

    assert answer["renamed"] is True
    assert answer["restored_to"] == "test-runs/20260101-000000-2"
    assert sorted(r["name"] for r in list_reports()) == \
        ["20260101-000000", "20260101-000000-2"]


async def test_restoring_something_the_trash_does_not_hold_is_a_404(
    runs_dir: Path, trash_dir: Path, test_session,
) -> None:
    from fastapi import HTTPException

    from app.api.v1.trash.router import restore_entry

    with pytest.raises(HTTPException) as caught:
        await restore_entry("test-runs", "19990101-000000", test_session)
    assert caught.value.status_code == 404


async def test_EMPTYING_the_trash_DELETES_what_it_holds(
    runs_dir: Path, trash_dir: Path, test_session,
) -> None:
    """The irreversible act, and the COUNT is the answer rather than a claim.

    No phrase any more: the caller has already decided, and asking them to retype
    a sentence the server holds adds nothing to the decision. One shelf at a time
    is the containment that remains — the sibling-shelf case is asserted on the
    trash surface's own suite, where a second shelf exists to be asserted against.
    """
    from app.api.v1.testing.router import delete_run
    from app.api.v1.trash.router import DestructiveRequest, empty_shelf, get_shelf

    for name in ("20260101-000000", "20260101-000001"):
        a_run(runs_dir, name)
        await delete_run(name)

    answer = await empty_shelf("test-runs", test_session, body=DestructiveRequest(confirm=True))

    assert answer == {"emptied": True, "domain": "test-runs", "deleted": 2}
    assert (await get_shelf("test-runs", test_session))["count"] == 0
    assert not any((trash_dir / "test-runs").iterdir())
