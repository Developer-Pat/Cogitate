---
title: Testing Dashboard
type: atlas-page
path: frontend/src/pages/TestingDashboard.tsx
confidence: high
updated: 2026-09-20
tags: [type/page, domain/atlas-ui]
---
# Testing Dashboard

**Component**: `frontend/src/pages/TestingDashboard.tsx`
**Route**: `/testing-dashboard`

## Purpose

The user-testing page: catalog the project's tests, run them, watch the run, and read
what past runs actually said. **Every number on this page comes from a file** — the
catalog is DERIVED from the test tree (descriptions from the module docstrings,
clusters from the paths, time classes from the dependencies), the runs are the runner's
own artifacts read back from disk, and a RUN is the same `scripts/testing/run_tests.py`
a person starts from a terminal.

**User space.** The page owns no report repository, no rolling, no retention and no
system monitoring: it reads, it starts and stops one run, and it retires one run when
asked. The sweeps are developer / system-agent space.

## The tabs

| Tab | Shows |
| --- | --- |
| Runnable | tests with no external dependency |
| Conditional | tests that need a service/provider/LLM — the condition is on the row |
| Quarantine | parked tests, kept visible rather than deleted |
| Self-test | the page's OWN check (`backend/selftest/`, deliberately red) — run by name |
| Runs | the run folders on disk, with counts, failures and skips-with-reasons |
| Live | the run in progress: counts, per-test lines, Cancel |

The catalog tabs are ordered least-dependent-first, which is also the diagnosis:
runnable, then conditional, then parked. **Self-test is its own set** — the
page's exercise, not the suite — so the profile filter does not narrow it and no
sweep collects it.

## Retiring runs, and getting them back

The Runs tab ticks (`ReportsTable` gains the column; the page owns the set) and
**Retire N selected** moves them together, through `RetireRunsModal`, which lists
every run first and then reports the batch per run: Moved / Refused (the lock's
sentence) / Not found. Two quick-selects — *Select self-test runs*, *Select runs
that did not pass* — only TICK; they move nothing.

**Where they go.** Retiring a run moves its folder onto the trash's `test-runs`
shelf, and the Runs tab carries a **Trash** link to [[atlas/ui/pages/Trash|the
trash page]] — one surface for all five shelves, which lists what is there, puts an
entry back with **Restore**, and removes one for good with **Delete forever**. This
page no longer renders a trash view of its own: it retires a run and points there.

A run of the page's own check is marked **self-test** in the Runs table (the
server's `self_test`, derived from the run's own selection), so a deliberately red
run in history cannot be read as the suite failing.

## Saving a run, and what changed

**Save** (`SaveRunModal`) keeps a COPY: the destination is prefilled from the
persisted one (`stores/testingSavePreference` — one destination, chosen once), an
empty field means the server's own default, and the dialog names the exact path
when it is done and says the run stays in Runs. A refusal is shown in place (the
lock's sentence, or "already saved at …") and the dialog does not close on one.

**The run detail carries the diff.** `ReportsTable`'s `DetailPanel` fetches
`getRun` and `getDiff` together — *"why did this fail?"* is the question a failure
raises, and what CHANGED is most of the answer. The block names the baseline run it
compared against, lists newly-failing / fixed / added / gone, and **says why** when
there is no comparison to make rather than rendering an empty diff that would read
as "nothing changed".

## Running

- **Run** (the action bar) starts the ticked rows when there are any, else everything
  the current tab+profile shows; the control names the count. Each row's own **Run**
  starts that one file.
- **Profile** narrows the view before running: `Fast only` (the DEFAULT, so the first
  click is the quickest signal), `Everything`, `Needs the installation`.
- **One run at a time, globally** — the RUNNER owns the lock
  (`data/test-runs/.run.lock`, carrying id/pid/pgid/started/origin), so a page run, a
  terminal run and a sweep run collide through one mechanism. While the lock is held,
  Run is disabled and its tooltip repeats the lock's own sentence; a run started
  elsewhere (origin `terminal` / `sweep`) is picked up on its own and shown live, with
  **Cancel withheld** — a run the page did not start is watched, not stopped.
- The page polls `GET /testing/runs/current` every 10 s. **The lock is the only
  state**: the page keeps no notion of "running" of its own, which is why a run
  survives a backend restart and a reload re-attaches.

## The Live tab

The page — not the tab — opens the run's SSE stream (`useRunStream`), so switching to
Runnable to read a row does not tear down a feed from a run that takes half an hour.

- Counts are against **pytest's own collected total** (`collect`), never a percentage
  and never an ETA. Until the total arrives, a count is shown as a count.
- The counts are labeled: the live count while the run goes, pytest's own final tally
  once the run reaches a `summary`.
- The per-test lines are capped in view and the panel names how many it is not showing;
  the run's own `events.jsonl` holds them all.
- The `ui` (vitest) group reports an envelope only, and the panel says so instead of
  showing an empty feed that reads as stuck.

## Retiring a run

**Delete** on a Runs row opens a confirmation (`DeleteRunModal`) and then calls
`DELETE /testing/runs/{id}`, which MOVES the folder to `trash/test-runs/<name>` — a
recovery, not an erasure. The row's Delete is **disabled with its reason while that run
is in progress** (the lock answers), and nothing is pruned automatically.

## Components Used

| Component | Path | Purpose |
|-----------|------|---------|
| PageBanner | `components/ui/PageBanner.tsx` | Page header |
| CatalogTable | `components/features/testing/CatalogTable.tsx` | The catalog: tick, view, run |
| ReportsTable | `components/features/testing/ReportsTable.tsx` | Past runs: view, delete |
| TestDetailsModal | `components/features/testing/TestDetailsModal.tsx` | One module in full |
| LiveRunPanel | `components/features/testing/LiveRunPanel.tsx` | The run in progress |
| DeleteRunModal | `components/features/testing/DeleteRunModal.tsx` | The delete confirmation |
| Trash (link) | `pages/Trash.tsx` | The Runs tab's link to the trash page — the shelf view is not rendered here any more |
| ErrorBoundary | `components/ErrorBoundary.tsx` | Crash containment |

## Hooks Used

| Hook | Path | Purpose |
|------|------|---------|
| usePageTitle | `hooks/usePageTitle.tsx` | Sets document title |
| useRunStream | `hooks/useRunStream.ts` | Follows one run's event stream |

## API Endpoints Called

All under `/api/v1/testing`, through `services/domain/TestingService.ts`:

| Endpoint | Used for |
| --- | --- |
| `GET /catalog` | the derived test catalog |
| `GET /runs` | the runs on disk |
| `GET /runs/current` | the lock: is a run going, and who started it (polled) |
| `GET /runs/{id}` | one run in full, for the expanded row |
| `GET /runs/{id}/events` | the live stream (SSE, opened by `useRunStream`) |
| `POST /runs` | start a run, under the lock, with the id the page will watch |
| `POST /runs/{id}/cancel` | stop a run this page started (group kill) |
| `DELETE /runs/{id}` | retire a run (moved to the trash) |

Start and cancel carry a 30 s timeout: the spawn waits up to 20 s for the runner's
lock and a cancel is TERM → wait → KILL → reap → verify. At the client's 10 s default
both would abort work that had already succeeded. When either request fails, the page
asks the LOCK what happened rather than assuming the worst.

## State Management

Local state only — no store. The page holds the catalog, the runs, the selection, the
lock's answer, whether it is starting/cancelling, and the delete target. The live feed
is a pure fold of the run's events (`utils/runFeed.ts`).

## Related Pages

- [[atlas/ui/pages/Logs|Logs]] — the other live stream in the app
- [[dev-notes/testing/README|Testing dev notes]] — the runner, the groups, the artifacts
