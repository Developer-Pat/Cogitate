---
tags: [type/dev-notes]
---

# Background Work — what runs without anyone asking

Everything the application does on its own: the recurring loops, the scheduled
one-shots, and the switches that turn them off.

**This page exists because of a question that cost real time**: something was
running the pipeline and burning tokens while nobody was chatting. It was not —
but answering it meant auditing every automatic activity from scratch. That
audit is below, so it never has to be redone from nothing.

## The recurring work

| what | when | trigger | can it be turned off? |
|---|---|---|---|
| **Workflow trigger scheduler** | per trigger (cron/interval from the database) | `workflows/triggers/scheduler.py` | only by disabling the individual trigger |
| **Exa one-shot timers** | at their `fires_at` | `domain/external_agent/timer_service.py` | not needed — see below |
| **The workspace drain** (inbox processor) | every 900s (20s under the launcher) | `main.py` | **yes** — `EXA_BACKGROUND_PROCESSING_ENABLED`, default off |
| **The startup system sweep** | once, N seconds after boot | `main.py` | **yes** — `STARTUP_SWEEP_ENABLED`, default off |
| **The mute restore** | at a muted notification's end time | `domain/messaging/notifications.py` | no — it is what un-mutes things |
| **The log sweep** | on demand only | `POST /api/v1/system/sweep/log` | not applicable — it is always a user action |
| **The frontend's polling** | every few seconds per open tab | the frontend | by closing the tab |

**The Exa timers do not auto-fire.** A timer's expiry publishes a
`timer:{id}:fired` event and waits for pickup — it does not start an agent turn by
itself. A fired timer is not running work.

## The two switchable ones, and why you would switch them off

Both default **off**, and both are environment settings:

| setting | what it does | why you would turn it off |
|---|---|---|
| `STARTUP_SWEEP_ENABLED` | runs the system-audit graph at boot and files its report into the Exa workspace inbox | under `--reload` a boot follows every file save, so it produces a toast after every save — a stream of notifications about a system nobody is changing |
| `EXA_BACKGROUND_PROCESSING_ENABLED` | the workspace **drain**: moves reports out of `.exa-workspace/inbox/` into `system-reports/`, toasting when one carries a warning | while testing, an inbox that is continuously emptied and announced is noise, and nothing is waiting on it |

**They are coupled, and the code enforces it.** The sweep files into the inbox
and the drain is the only consumer, so **with the drain off the sweep is *held***,
not scheduled — otherwise it would fill a folder nothing empties. Both must be on
for the sweep to fire.

**The sweep costs no model tokens.** Its graph nodes are plain functions and the
Exa distributor only writes a markdown file — there is no LLM call in it. Worth
stating plainly, because the opposite was once assumed and chased.

**The sweep is always available on demand**, regardless of either setting:

```
POST /api/v1/workflows/execute   {"workflow_id": "system-audit"}
```

or the Workflows page, which handles `system-audit` directly.

### Turning them on

```
STARTUP_SWEEP_ENABLED=true
EXA_BACKGROUND_PROCESSING_ENABLED=true
```

Set the drain first: the sweep is held without it.

## How to check this page

A page listing automatic work is exactly the kind that drifts — the code gains a
loop and the doc does not. The authoritative list is two greps:

```bash
grep -n "create_task\|schedule_once\|add_job" backend/app/main.py
grep -rn "asyncio.sleep(\|schedule_once" backend/app --include=*.py | grep -v tests
```

And the live witness is the startup log, which announces each scheduled item and
names which are disabled. If a line appears there that this page does not
mention, **this page is wrong** — the log is generated, the page is written.

## Related

- [[dev-notes/lifecycle/startup|Startup — the boot sequence]]
- [[dev-notes/lifecycle/shutdown|Shutdown — the contract]]
- [[dev-notes/configuration/configuration-surface|Configuration Surface]]
