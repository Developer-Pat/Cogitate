---
title: Monitor Workflow Family
type: atlas-devnote
category: workflows
order: 6
confidence: high
created: 2026-08-10
updated: 2026-08-10
tags: [type/dev-notes, domain/workflows]
---

# Monitor Workflow Family

The system's first real user-facing workflows — the monitor →
analyze → report pattern with different cadences. Seeded by
`scripts/core/seed_monitor_templates.py` (idempotent); the graph
builders live in `graphs/monitor_graph.py`, nodes in
`nodes/monitor_nodes.py`.

## The three monitors

| Template | Cadence | What it does | Output |
|----------|---------|--------------|--------|
| `rss-monitor` | hourly (cron `0 * * * *`) | Fetch RSS feeds (XML parse, no key) → dedup → summarize (summarize-llm, plain-text fallback) | `data/monitor/rss-digest-<date>.md` |
| `market-watch` | 5-min (cron `*/5 * * * *`) | Keyless CoinGecko price → threshold/trend vs last price | `data/monitor/market-<date>.md` |
| `readiness-check` | manual (TestingDashboard) | POST health suite (5 checks via RunPostTool) + providers/env-keys + agents/curated-models | `data/monitor/readiness-<date>.md` |

## Examples — the three monitors, in depth

Each monitor has its own dedicated example page (tagged
`type/example` — find them via the `type/example` tag in the
graph):

- 📰 [[dev-notes/workflows/examples/rss-monitor|RSS News Monitor]]
  — hourly news digest: real output (5 stories + the dedup run),
  how to read it, how to run it
- 📈 [[dev-notes/workflows/examples/market-watch|Market Watch]] —
  5-minute price tripwire: quiet vs alert output, how to read it
- 🩺 [[dev-notes/workflows/examples/readiness-check|Readiness
  Check]] — "is my instance ready?": the 5/5 report, key states,
  how to run it

## Key design facts

- **Cross-run state lives in a file, not checkpoint state.**
  Each trigger fire creates a fresh `wf-<uuid>` thread, so
  LangGraph checkpoint state (per-thread) cannot carry
  "last seen" / "last price". Persistent cross-run state goes in
  `data/monitor/state.json` — survives restarts, explicit,
  testable. Do NOT "fix" this back into the checkpointer.
- **Error-resilient by design.** A dead feed/API records an error
  in the report but never fails the workflow run.
- **Summarize never blocks.** `rss_summarize_node` falls back to a
  plain-text digest if the LLM path fails.
- **Async bridge.** `RunPostTool.execute` is async, but the graph
  router invokes synchronously — the readiness node bridges with
  `asyncio.run` (no running loop inside a sync graph invoke).
- **Cadence = testability.** Hourly/5-min triggers verify
  in-session: fire, watch the execution record, iterate. Weekly
  digests would be unverifiable (wait 7 days for run #1).

## Inputs

The feeds reach a run through **four channels**, tried in this order (a monitor must run whether or not
it can read its config — but it must SAY when it read none):

| channel | who fills it |
|---|---|
| `metadata.config.feeds` | the API path's `RunMetadata` |
| `state.feeds` | an explicit seed |
| `inputs.feeds` (`+ inputs.max_items`) | a **manual** run's form input |
| **`state.config.feeds`** | **the template's own config — the channel a SCHEDULED run depends on** |

`MonitorState` declares `inputs` and `config`; LangGraph filters state through the schema, so undeclared
keys are dropped. **A scheduled run carries only `{"trigger_id": …}` in `inputs`**, so its feeds come from
`state.config` — read from the template by **one reader, `app/workflows/template_config.py`**
(`load_template_config`), which BOTH seeding doors call:

- the API's `POST /execute` (`workflow_router.execute_workflow`), and
- the scheduler's trigger path (`scheduler._build_trigger_state`).

That sharing is the fix for a long quiet failure (2026-10-13): the scheduler seeded `"config": None` while
the API seeded the config, so **every scheduled run resolved zero feeds** — and the crash that followed
(`None.get`) was swallowed by the node's declared-*tolerant* grade, leaving the digest reading
*"No new items this cycle."* A run whose feed list is empty now records an error and the digest reads
*"Nothing gathered this cycle — see the errors below."*

## Triggers

- `monitor-rss-hourly` (schedule, `0 * * * *`)
- `monitor-market-5min` (schedule, `*/5 * * * *`)

Both are seeded with **`enabled: false`** — the rows exist and no monitor fires until a person turns
one on. The scheduler machinery: [[dev-notes/workflows/event-triggers|Event Triggers]].

## Related

- [[docs/workflow-catalog|Workflow Catalog]] §4 — template table
- [[dev-notes/workflows/checkpointing|Checkpointing]] — why
  cross-run state isn't there
- [[dev-notes/workflows/event-triggers|Event Triggers]] — the
  scheduler machinery

## The system-sweep member — the SYSTEM monitor

The monitor family includes the SYSTEM monitor: the system-audit
workflow (audit → verify → analyze → report — the structural
verification: the verify node RE-RUNS the audit + compares), run
as the periodic System Sweep. Template `system-audit`, category
`monitoring`. The trigger paths: the scheduled one-shot (see
[[dev-notes/agents/system-sweep|the System Sweep]]), Exa-triggered
(the execute endpoint), or user-requested. The report lands on the
Exa desktop inbox + the notify event reaches the toaster. Full
story: [[dev-notes/agents/system-audit-arc|the audit arc]].
