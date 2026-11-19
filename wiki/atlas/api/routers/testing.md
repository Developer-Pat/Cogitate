---
title: Testing
type: atlas-api
path: backend/app/api/v1/testing/router.py
category: api-atlas
order: 42
confidence: high
updated: 2026-09-20
tags: [type/api, domain/testing, status/active]
---

# Testing — API

> Router: `backend/app/api/v1/testing/router.py` (`/api/v1/testing`).
> Domain: `backend/app/domain/testing/` (catalog, reports, run_lock, stream,
> runner, and the runs shelf's own move mechanics in `trash`). Status: **ACTIVE** —
> the user-testing page's whole server side.

## Purpose

The user-testing page's backend, and **USER SPACE**: it presents the test catalog,
reads the runs on disk, starts and stops ONE run, and retires runs on request —
one, or several named at once. **A retire is a MOVE**: the folder lands on the
trash's `test-runs` shelf, and the shelf is read, restored and emptied at
`/api/v1/trash` — the shelf registry's own surface — rather than here. This router
owns no report repository, no rolling, no retention and no system monitoring — the
system sweep does that, separately.

Nothing here invents a state:

- "a run is in progress" is the **RUNNER's lock file** (`data/test-runs/.run.lock`),
  not a timer or a flag of the backend's own;
- the live feed is the run's own `events.jsonl`, served as it is written;
- a cancel reports what actually died (and names any survivor).

Because the lock is shared, a run started from a terminal, from the page and from the
sweep collide through ONE mechanism — and a run survives a backend restart.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/testing/catalog` | The test catalog, **DERIVED** from the test tree: one entry per test file (docstring description, cluster from the path, tier from the dependencies, the condition for a conditional file, and `run_path` — the path a RUN takes, `tests/unit/x.py`). No manifest file exists to drift |
| `GET` | `/testing/runs?limit=50` | The run folders on disk, newest first, with counts, failures and skips-with-reasons |
| `GET` | `/testing/runs/current` | **The LOCK's answer**: whether a run is in progress, whether the lock is stale, and who holds it (id/pid/pgid/started/**origin**). Declared BEFORE `/{run_id}` so the literal path is not read as a run id |
| `GET` | `/testing/runs/{run_id}` | One run in full — the counts, the FAILED list, and every skip **with its reason** (read from the JUnit XML, with the markdown parse as the fallback) |
| `GET` | `/testing/runs/{run_id}/events` | The run's own event file, followed live (SSE): replay from the start by default, `?tail=true` to skip what already happened, resume on `Last-Event-ID` (the byte offset), close on the run's end |
| `POST` | `/testing/runs` (202) | Start a run — **the same `scripts/testing/run_tests.py` a person starts**, under the lock, with `COGITATE_RUN_ORIGIN=page`. Body: `group` \| `files[]` \| `parallel` \| `run_id`. It waits for the runner's own lock, so "started" is a fact rather than a `Popen` that succeeded. 409 when the lock is held (naming it), 400 for a request that describes no run, 500 with the console when the runner died first |
| `POST` | `/testing/runs/{run_id}/cancel` | Stop the run — **a GROUP kill** (read the pgid from the lock, TERM, wait, KILL, reap, verify) and a report: `cancelled`, `forced`, `released_lock`, `survivors`, `console`. A run the page did not start comes back `cancelled: false` with its reason — a terminal run is watched, not stopped |
| `DELETE` | `/testing/runs/{run_id}` | Retire one run — the folder is **MOVED to `trash/test-runs/<name>`** (never unlinked; a collision gets a `-2`), and the answer names where it went. 409 with the lock's sentence while that run is in progress, 404 when there is no such run |
| `POST` | `/testing/runs/retire` | Retire **SEVERAL** — body `{runs: [names]}`: an explicit LIST, never a rule (no "older than", no "keep the newest N"). It answers for **every** name: `retired` (with `moved_to` + `contents`), `refused` (a run in progress, with the lock's own sentence) and `missing`. A batch that stopped at the first refusal would leave a person guessing which of nine went. 400 when the list is empty |
| `POST` | `/testing/runs/{run_id}/save` | **SAVE**: a COPY of the run's folder (all three artifacts) into a destination the person names — the locator's `data/test-reports/` by default, and a relative path is relative to the project root. The runs dir is untouched: Save copies, never moves, and keeps no registry of what has been saved. 404 no such run · **409 while that run is being written** (a torn copy is not a report) · **409 when a copy is already there** (never overwritten — the refusal names the path in the way) · 400 for a destination that cannot be used, including one inside the runs dir or the trash, which are the page's own state |
| `GET` | `/testing/runs/{run_id}/diff` | **What CHANGED** since the last green run of the SAME selection: `baseline`, `added`, `removed`, `newly_failing` (REGRESSIONS only), `fixed`, and the baseline's counts. When nothing comparable exists the answer carries a **`reason`** and empty lists — never a silent empty diff, which would read as "nothing changed". 404 only when the run itself does not exist |

## Where the retired runs are read and put back

**Not here.** This page retires a run INTO the trash and that is all it does with
it; the shelf, its entries, the way back and the permanent removal are
[[atlas/api/routers/trash|the trash surface]] (`/api/v1/trash`, the `test-runs`
shelf). The three delegates that used to stand here (`/testing/trash`,
`/testing/trash/restore/{name}`, `/testing/trash/empty`) were a second address for
one implementation and went with their last caller.

## The artifacts

One run is one folder, `data/test-runs/<name>/`:

| File | Answers |
|------|---------|
| `report.md` | what happened — the full console record, durations, the summary, ELAPSED and EXIT |
| `report.xml` | what each test did — pytest's own JUnit XML: outcome, skip message, duration |
| `events.jsonl` | what is happening NOW — `session_start` / `collect` / `test` / `summary`, and the runner's `run_start` / `run_end` envelope, one JSON line each |

Paths come from the locator (`Paths.test_runs_dir`, `Paths.trash_dir`), never from
arithmetic in the router.

## Auth

Authenticated session, like every other `/api/v1` route (the page is behind the app's
own login).

## Status

**ACTIVE** — the user-testing page (`/testing-dashboard`) is its only consumer: the
catalog table, the runs table (with the batch-retire ticks), the live feed, Run,
Cancel, Delete and Retire. What was retired is looked at, restored or removed for
good on the trash page (`/trash`) through `/api/v1/trash`.

`reports.py` also marks a run whose own recorded SELECTION was the page's exercise
and nothing else (`self_test`), so a deliberately red Self-test run cannot be read
as the suite failing in history.

## Related

- [[atlas/api/routers/trash|Trash]] — the shelf registry's surface: every shelf read, restored, purged and emptied
- [[atlas/ui/pages/TestingDashboard|Testing Dashboard]] — the page
- [[dev-notes/testing/README|Testing dev notes]] — the runner, the groups, the artifacts
