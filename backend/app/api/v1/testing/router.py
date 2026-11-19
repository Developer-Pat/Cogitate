"""
The testing API — the user-testing page's endpoints.

THE USER-TESTING PAGE. This router is **USER SPACE**: it presents
the test catalog, the runs on disk, and — from C1 — it can START and STOP one.
It does not own a report repository, roll files, or monitor the system's health
— the sweeps do that (design §1).

The runs come from the locator (`Paths.test_runs_dir`, `data/test-runs/`), one
FOLDER per run holding report.md, report.xml and events.jsonl.

READ vs LIVE vs ACT, which is the split these endpoints exist to make:

    GET  /runs                    the runs on disk, newest first (from the record)
    GET  /runs/current            is a run in progress, and WHO started it (from the lock)
    POST /runs                    start one — the runner, under the run lock
    POST /runs/{run_id}/cancel    stop the one this page started (group kill)
    GET  /runs/{run_id}           one run, read from its JUnit XML
    GET  /runs/{run_id}/events    the run's own event file, followed live (SSE)
    DELETE /runs/{run_id}         retire one run — moved to the trash, not unlinked
    POST /runs/retire             retire SEVERAL — the same move, listed per run
    GET  /runs/{run_id}/diff      what CHANGED since the last green run of the same selection
    POST /runs/{run_id}/save      keep a COPY of a run, where the person says

THE TRASH IS NOT HERE. This page retires a run INTO the trash, and that is all it
does with it: the shelf, its entries, the way back and the permanent removal are
read and acted on at `/api/v1/trash`, the shelf registry's own surface. The three
delegates that used to stand here were a second address for one implementation,
and they went with the last caller.

Nothing here invents a state: "in progress" is the lock's answer, the stream is
the runner's own output, and a cancel reports what actually died.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.core.config import Paths
from app.domain.testing import runner
from app.domain.testing.catalog import build_catalog
from app.domain.testing.diffing import diff_against_last_green
from app.domain.testing.reports import list_reports, read_report
from app.domain.testing.run_lock import RunInProgress, read_lock
from app.domain.testing.saving import save_run
from app.domain.testing.stream import run_event_stream
from app.domain.testing.trash import trash_run


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/testing", tags=["testing"])

#: The no-cache headers the SSE stream needs, matching the logs stream.
_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


class RunRequest(BaseModel):
    """What to run — the same choices the terminal runner takes."""

    group: str | None = None
    files: list[str] = Field(default_factory=list)
    parallel: bool | None = None
    #: The caller may NAME the run, so it can watch it immediately instead of
    #: polling for whichever folder appeared.
    run_id: str | None = None


class RetireRequest(BaseModel):
    """Which runs to retire — an explicit LIST, never a rule.

    There is no "older than", no "keep the newest N" and no count: retention is
    out of scope for this page (design §9), so the only thing that can move a run
    is a person naming it.
    """

    runs: list[str] = Field(default_factory=list)


class SaveRequest(BaseModel):
    """Where the copy goes. Null (or absent) means the locator's default, so the
    common case needs no argument at all."""

    destination: str | None = None


@router.get("/catalog")
async def get_catalog() -> dict[str, Any]:
    """The test catalog, DERIVED from the test tree.

    Descriptions come from the module docstrings, clusters from the paths,
    time classes from the dependencies. Nothing is hand-maintained, so nothing
    can drift. When there is no test tree (an installed build) this returns an
    empty catalog WITH a reason, so the page can say why it is empty.
    """
    return build_catalog()


@router.get("/runs")
async def get_runs(limit: int = 50) -> dict[str, Any]:
    """The runs on disk, newest first."""
    runs = list_reports(limit=limit)
    return {"available": bool(runs), "count": len(runs), "reports": runs}


@router.get("/runs/current")
async def get_current_run() -> dict[str, Any]:
    """Is a run in progress — and if so, WHO started it and WHEN.

    **Declared before `/{run_id}` on purpose**: the literal path must be matched
    before the parameter, or a request for "current" is read as a run id. This
    codebase has already paid for that lesson once, on the sessions routes.

    The answer comes from the LOCK, which is the runner's own record: a
    page-invented notion of "running" would be the mock's progress bar again.
    `stale` separates "a run is going" from "a crashed run left debris".
    """
    lock = read_lock(Path(Paths.test_runs_dir))
    if lock is None:
        return {"running": False, "stale": False, "lock": None}
    alive = lock.alive()
    return {"running": alive, "stale": not alive, "lock": lock.as_dict()}


@router.post("/runs", status_code=202)
async def start_run(body: RunRequest) -> dict[str, Any]:
    """Start a run — the SAME runner a person starts from a terminal.

    The page does not get its own runner, its own queue or its own progress:
    it starts `scripts/testing/run_tests.py` under the run lock and then reads
    what the run writes. The response returns as soon as the run's OWN lock
    exists, which is what makes "it started" a fact rather than a hope.

    409 when a run is already in progress (the lock names it), 400 when the
    request does not describe a run, 500 when the runner died before taking its
    lock — with its console in the message, because "failed to start" alone is
    not something anyone can act on.
    """
    spec = runner.RunSpec(group=body.group, files=body.files, parallel=body.parallel)
    run_id = body.run_id or time.strftime("%Y%m%d-%H%M%S")
    try:
        # Popen and the lock wait are blocking; the event loop must keep serving
        # the SSE streams of the runs already going.
        return await asyncio.to_thread(runner.spawn, spec, run_id)
    except RunInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/runs/{run_id}/cancel")
async def cancel_run(run_id: str) -> dict[str, Any]:
    """Stop the run — **the whole process group**, then verify, then report.

    Killing the runner's pid alone leaves pytest's xdist workers alive and
    holding the database, which presents as flaky tests later. The kill mirrors
    `stop_process_group` in `cogitate.sh`: TERM the group, wait, KILL the group,
    and NAME any survivor rather than claiming success.

    A run this page did not start is refused, with the reason: stopping someone
    else's run is a deliberate act, not a side effect of a button.
    """
    result = await asyncio.to_thread(runner.cancel, run_id)
    if result.get("survivors"):
        logger.warning("run %s cancel left survivors: %s", run_id, result["survivors"])
    return result


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    """One run in full — its counts, its failures, and its skips WITH REASONS.

    **The skip reasons are the point.** A skipped test is evidence, not noise:
    "12 tests are not running because Ollama is down" is something a person can
    act on, where a bare count is not.
    """
    run = read_report(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="No such run")
    return run


@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    request: Request,
    offset: int = 0,
    tail: bool = False,
) -> StreamingResponse:
    """The run's event file, followed live.

    Replays from the start by default, so a page that opens mid-run still sees
    the whole run. `tail=true` skips to the end (a watcher that only wants what
    has not happened yet), and a browser reconnecting on its own resumes from
    its last received id — the byte offset — rather than starting over.
    """
    last_id = request.headers.get("last-event-id")
    if last_id and last_id.isdigit():
        offset = int(last_id)
    return StreamingResponse(
        run_event_stream(Path(Paths.test_runs_dir), run_id, offset=offset, tail=tail),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str) -> dict[str, Any]:
    """Retire one run — **moved into the trash, never unlinked**.

    Deleting is the person's own action, one folder at a time: no retention rule,
    no pruning, nothing automatic (the user-space boundary). The folder goes to
    `trash/test-runs/<name>` intact, so the action is recoverable rather than
    final, and the answer NAMES where it went.

    **A run in progress is refused**, with the lock's own sentence: deleting the
    folder under a live run would break its stream and strand its artifacts
    mid-write. That is a 409, not a 404 — the run exists, and the reason it
    cannot go is state, not absence.
    """
    try:
        result = trash_run(run_id)
    except RunInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="No such run")
    logger.info("run %s moved to the trash: %s", run_id, result.moved_to)
    return {"deleted": True, **result.as_dict()}


@router.post("/runs/retire")
async def retire_runs(body: RetireRequest) -> dict[str, Any]:
    """Retire SEVERAL runs at once — the same move, reported per run.

    **Every run is answered for.** A run in progress inside the selection is
    REFUSED by name (the lock's own sentence) while the rest still go, and a name
    that is not a run is reported as missing: a batch that stopped at the first
    refusal would leave a person guessing which of their nine were moved.

    Nothing is deleted here — each one is a move to `trash/test-runs/<name>`, and
    the trash view is where they can be put back.
    """
    if not body.runs:
        raise HTTPException(status_code=400, detail="no runs named")

    retired: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    missing: list[str] = []

    for name in body.runs:
        try:
            # The moves are filesystem renames: cheap, and blocking only in the
            # sense that a rename always is, so they run off the event loop.
            result = await asyncio.to_thread(trash_run, name)
        except RunInProgress as exc:
            refused.append({"name": name, "reason": str(exc)})
            continue
        if result is None:
            missing.append(name)
            continue
        retired.append(result.as_dict())

    logger.info(
        "retired %d run(s); refused %d; missing %d",
        len(retired), len(refused), len(missing),
    )
    return {"retired": retired, "refused": refused, "missing": missing}


# ── what changed, and keeping a copy ─────────────────────────────────────────


@router.get("/runs/{run_id}/diff")
async def get_run_diff(run_id: str) -> dict[str, Any]:
    """What CHANGED since the last **green** run of the SAME selection.

    *"Why did this fail?"* is far easier with what changed than with the failure
    alone, and the comparison needs two facts this page does not invent: the run's
    own selection fingerprint (so the baseline really ran the same thing) and the
    baseline's per-test outcomes.

    **There is no fallback to "whatever ran last".** A comparison against an
    unrelated selection would report a hundred "removed" tests as if something had
    happened, so when nothing comparable is on disk the answer carries a `reason`
    and the lists stay empty. 404 only when the run itself does not exist.
    """
    diff = await asyncio.to_thread(diff_against_last_green, run_id)
    if diff is None:
        raise HTTPException(status_code=404, detail="No such run")
    return diff.as_dict()


@router.post("/runs/{run_id}/save")
async def save_a_run(run_id: str, body: SaveRequest | None = None) -> dict[str, Any]:
    """**SAVE** a run — a COPY of its folder, to a destination the person names.

    The user keeps it: no repository is implied, nothing is registered, and the
    runs dir is untouched (Save copies; it never moves). The default destination
    comes from the locator, so the common case needs no argument at all.

    404 when there is no such run · 409 while that run is still being written (a
    torn copy is not a report) · 409 when a copy of it is already at the
    destination (never overwritten) · 400 for a destination that cannot be used,
    including one inside the runs dir or the trash, which are the page's own state.
    """
    try:
        result = await asyncio.to_thread(
            save_run, run_id, body.destination if body else None
        )
    except RunInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="No such run")
    logger.info("run %s saved to %s", run_id, result.saved_to)
    return {"saved": True, **result.as_dict()}