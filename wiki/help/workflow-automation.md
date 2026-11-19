---
title: Workflow Automation
category: workflows
subtopic: Automation
order: 1
confidence: high
created: 2026-08-18
updated: 2026-08-18
tags: [domain/help]
---

# Workflow Automation

The Automation page sets up **recurring workflow runs** — "keep
doing this thing" — and monitors their history. Two tabs:

- **Triggers** — the control table. Each trigger runs a workflow
  on its own schedule (or fires on a webhook). The play ▶ / stop
  ■ buttons start and stop a trigger; the calendar icon opens the
  schedule editor. The Status column shows whether a trigger is
  currently active.
- **History** — per-trigger run history: search + filter + page
  through past executions, with status, start time, and duration.

## Schedules (cron)

Triggers run on **cron expressions** — five fields:
`minute hour day-of-month month day-of-week`.

- `0 * * * *` — hourly
- `0 9 * * *` — daily at 9:00
- `0 9 * * 1` — Mondays at 9:00
- `*/5 * * * *` — every 5 minutes

The schedule editor shows the cron's meaning in plain English as
you type. For the full cron syntax, see the
[Cron expression reference](https://crontab.guru/) (crontab.guru).

## Notes

- Monitor triggers (RSS digest, market watch) ship **deactivated**
  — start them when you want them running.
- Every trigger fire is an execution; the delivered reports land
  on the Products page.
