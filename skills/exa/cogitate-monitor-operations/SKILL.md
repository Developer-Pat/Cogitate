---
name: cogitate-monitor-operations
description: "The monitor workflow family — rss-monitor, market-watch, readiness-check: what they do, how to run/reset/configure them. Use for monitor questions or operations."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, monitors, rss, market-watch, workflows]
---

# Cogitate Monitor Operations

The monitor family: **fetch → summarize → format → deliver** —
deterministic control flow around the stochastic LLM step.

## The monitors

- **rss-monitor** — fetches Ars Technica + Hacker News frontpage
  feeds, summarizes new items, formats a linked digest ("At a
  glance" + "New items" with URLs), delivers to Products. Trigger:
  `monitor-rss-hourly` (hourly, `0 * * * *`).
- **market-watch** — checks a symbol's price (currently one price
  per run — a demo, not yet a series), threshold/trend compare,
  alert file. Trigger: `monitor-market-5min` (`*/5 * * * *`).
- **readiness-check** — the system readiness report.

## Operations

- **Reset a monitor** (full run — every item is new): `POST
  /api/v1/workflows/monitors/reset` with body
  `{"template_id": "rss-monitor"}`. Or the Reset button on the
  Workflow Templates table.
- **Trigger a run**: the trigger fires on schedule; a manual run
  goes through the execution API.
- **Configure**: the schedule via `PUT /triggers/{trigger_id}`
  (cron only — NEVER change the trigger's name; names are
  schedule-neutral). The feeds/symbols live in the template's
  config.

## The dedup state

`data/monitor/state.json` holds `last_seen` per feed — the reset
clears it per template. Do NOT edit it by hand; use the reset API.

## Verification

After a run, the Products page shows the delivered digest (Items
count + the linked list). Verify with `GET /workflows/products`
or `verify-trigger-config` on the monitor's trigger.
