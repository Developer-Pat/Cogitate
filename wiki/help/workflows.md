---
title: Workflow System
category: workflows
subtopic: Overview
order: 2
confidence: high
created: 2026-07-27
updated: 2026-08-14
tags: [domain/help]
---

# Workflow System

Workflows automate multi-step processes built on the agent pipeline.
Two concepts work together:

- **Templates** (Workflows → Templates) — the canonical process
  shapes the system can run: Monitor, File Processing, Chain,
  Multi-Agent, and more. A template defines WHAT the process does
  and what inputs it takes.
- **Workflows** (Workflows → Workflows) — your configured
  instances: a template with concrete parameters and a name.
  Example: the **Monitor** template instantiated as "RSS News
  Monitor" (feeds + item count) or "Market Watch" (symbol +
  threshold).

A **template is the recipe; a workflow is the meal made from it.**
Each run of a workflow is an **execution**; each execution delivers
a **product** (a report, file, or index entry) to the Products
page.

## Workflows (the configured instances)

The Workflows page shows your workflows — each is a template with
its parameters filled in. Browse, edit, or create new ones from
the Templates page. Lists group workflows for quick access
(e.g. "Onboarding", "Research").

**The monitor family** (rss-monitor, market-watch,
readiness-check) are workflows of the **Monitor** template: the
RSS digest runs hourly, the market watch every 5 minutes, and the
readiness check runs on demand (a full health report — POST
suite, providers, agents). Output lands in `data/monitor/`
(digest / alert / readiness markdown files) and the Products page.

## Testing fixtures

The Workflows page shows **your workflows by default** — the
system workflows and (soon) the ones you create. The **test
fixtures** (LLM/tool connectivity tests, agent demos, stress
tests) live in a separate **testing** area so they don't clutter
the user surface. Tick **"Show testing fixtures"** to see them —
they're how the system validates itself end-to-end, and they're
handy for checking that a provider or tool works.

## Workflow Execution

The Execution page is a two-panel layout:

- **Left panel — pick a workflow.** Use the direct workflow selector
  (searchable) or the list-based selector. The selected workflow's
  info shows before you run it.
- **Right panel — run + results.** Execute the workflow, then watch
  the output.
- **Recent Executions** — a table of past runs with status, start
  time, and duration. Rows show the workflow that ran and whether it
  succeeded.

## Scheduling (Workflow Automation)

The Automation page's triggers run on **cron expressions** — five
fields: `minute hour day-of-month month day-of-week`.

- `0 * * * *` — hourly
- `0 9 * * *` — daily at 9:00
- `0 9 * * 1` — Mondays at 9:00
- `*/5 * * * *` — every 5 minutes

The schedule editor shows the cron's meaning in plain English as
you type. For the full cron syntax, see the
[Cron expression reference](https://crontab.guru/) (crontab.guru).

## How runs behave

- Executions are **checkpointed** (LangGraph) — an interrupted run
  can be resumed rather than restarted.
- Runs that need review pause at an approval step; the approval flow
  (if enabled) decides whether to continue.
- Execution history is retained in the system (Recent Executions).

## Related

- [Cognitive Pipeline](/wiki/help/cognitive-pipeline) — the pipeline workflows run on
- [Logs](/wiki/help/logs) — trace and error visibility for runs
