---
tags: [type/dev-notes]
---

# The Shutdown Contract — a shutdown you can trust, and a record of how it ended

Cogitate's shutdown is **app-owned**: the launcher signals, the application
drains and reports. Every exit is recorded, and the next startup reads that
record and says what happened.

## The three states

A shutdown record is written on **every** exit, clean or not — that is what makes
its absence meaningful. It moves through three phases:

| phase | written | means |
|---|---|---|
| `running` | at boot | this instance is up |
| `draining` | when the drain begins | shutting down |
| `complete` | when the drain ends | finished |

**Why three and not two.** Against a hard kill, no shutdown code runs at all. With
only `draining`/`complete`, the newest row would be the *previous* clean exit, and
the next startup would read "clean" — a crash wearing the last good exit's clothes.
The boot-time `running` marker closes that: a death while running leaves a stale
`running` row behind, and its staleness is the evidence.

## The successor's report

At startup the application reads the newest record and reports one of four
outcomes. It claims nothing it cannot know:

| state | meaning |
|---|---|
| `clean` | phase `complete` |
| `died-mid-shutdown` | still `draining` — the process died during the drain |
| `died-while-running` | still `running` — killed, crashed, or the machine went down |
| `none` | no record at all — a first run, or the record store is missing. **No claim is made.** |

Abandoned work is **named, never counted**: "2 items abandoned" gives an operator
nothing to act on. The newest 20 records are kept, so a *pattern* of unclean exits
is visible rather than a single point.

## The drain

`SHUTDOWN_DRAIN_SECONDS` (5) sits deliberately **inside** uvicorn's
`--timeout-graceful-shutdown` (15). The transport is the outer bound and the
application's is the inner one, so the application finishes first and can *say*
what it did rather than be cut off mid-sentence. Without a bound, a reload with an
open event stream enters graceful shutdown and waits indefinitely.

The drain **awaits what it cancels**. `task.cancel()` only *requests*
cancellation — without awaiting, a coroutine can still be mid-`shutil.move` while
`close_db()` runs, so the application closes its own database underneath a live
task. `drain_task()` cancels and waits, bounded, and reports one of
`stopped` / `cancelled` / `timeout` / `error`.

The workflow trigger scheduler shuts down with `wait=True`. It is an
`AsyncIOScheduler`, so its jobs run in the event loop and `wait=True` genuinely
awaits them rather than abandoning a running job over an open database.

## Failure is degraded, never destructive

If the record cannot be written, that is logged and shutdown continues — nothing
about shutdown may be able to break shutdown. And if nothing can be written at
all, the missing completion is *still* the message.

The record module reaches the database directly (it runs during shutdown, when
FastAPI's dependency machinery is not available to ask), so its session factory is
**injectable** — which is also how tests keep it out of the production database.

## In-flight activity

`app/core/activity.py` holds a small in-memory registry of what is currently
running, so the record can *name* it. It is not a metrics system: it answers one
question, asked once, at shutdown. Every operation swallows its own errors — a
registry that can break the thing it observes is worse than none.

## Where it lives

- `app/core/shutdown_record.py` — `mark_running`, `begin_shutdown_record`, `complete_shutdown_record`, `report_last_shutdown`
- `app/core/activity.py` — the in-flight registry
- `main.py` `lifespan` — the wiring: the startup report, then phase one, the drain, phase two
- `shutdown_records` — the table (created by `create_all`)
- `tests/unit/test_shutdown_record.py`, `tests/unit/test_shutdown_drain.py`

## Related

- [[dev-notes/configuration/configuration-surface|Configuration Surface]]
- [[dev-notes/known-issues|Known Issues]]
