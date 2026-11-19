---
tags: [type/dev-notes]
---

# Startup — the boot sequence

What runs before the application serves a request, in order, and what each step
is for. The whole sequence lives in `main.py` `lifespan`, before its `yield`.

| # | step | purpose |
|---|---|---|
| 1 | logging + settings | level, env, debug flags |
| 2 | `seed_external_access_flag()` | the external-access toggle exists and defaults **off** |
| 3 | `seed_agent_packages()` / `seed_akeys_macros()` | the canned agent blueprints and the A-Key macro starter sets — **idempotent**, never overwrites user edits |
| 4 | LiteLLM retry defaults | `num_retries` / `retry_delay` applied once, globally |
| 5 | `init_db()` | main tables created/verified (`create_all`) |
| 6 | `init_documents_db()` | the documents database |
| 7 | **the previous exit is reported** | reads the newest shutdown record and says how the last one ended — see [[dev-notes/lifecycle/shutdown|Shutdown]] |
| 8 | **`mark_running()`** | the liveness marker for THIS instance. Written *after* the report, never before, or it would overwrite the state being reported |
| 9 | agent-kit slot sync | the singular `agents.kit_id` slot converges into the kit join — missing rows only |
| 10 | `auto_sync_tools()` / `verify_tool_invariants()` | registry tool definitions synchronised to the database, then checked |
| 11 | the workflow trigger scheduler | started, then triggers loaded from the database |
| 12 | `ensure_pending_timers()` | Exa's one-shot timers are rebuilt from their records |
| 13 | the startup system sweep | gated — see below |
| 14 | `ensure_mute_restore()` | a scheduled mute whose end passed during downtime restores at boot |
| 15 | the inbox processor | gated — see below |
| — | `yield` | the application serves |

**Nothing in the sequence may be fatal to it.** Each block is individually
guarded and logs a warning rather than raising — a boot must not depend on any
one of these succeeding.

## What is gated

Steps 13 and 15 are **off by default** and controlled by two settings, along with
the reason you would turn them off: see
[[dev-notes/lifecycle/background-work|Background Work]].

## Boot is not one thing

Under development the backend runs with `--reload`, so **a boot follows every file
save** — a fact worth holding onto when reading startup logs, because the sequence
above repeats each time and the numbers move. The launcher passes two development
overrides; see the configuration notes.

## How to check this page

The boot sequence is a list, and a list can silently lose an entry. Compare it
against the code:

```bash
grep -n "await \|logger.info(\"✅" backend/app/main.py | sed -n '1,60p'
```

The startup log is the other witness — `Starting up Cogitate application...`
begins each boot, and every step that completes logs a line. If the page and the
log disagree, the log is right.
