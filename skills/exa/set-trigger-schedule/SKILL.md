---
name: set-trigger-schedule
description: "Set a workflow trigger's schedule (the 5-field cron) via the Cogitate API. Use when asked to change when a workflow runs. Includes the validation rules and the NEVER-rename directive."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, triggers, cron, schedule]
---

# Set a Trigger Schedule

Change a workflow trigger's cron via the typed API. The tool
`set-trigger-schedule` exists in the registry; the API path is
the same operation.

## The API

`PUT /api/v1/triggers/{trigger_id}` with body:
```json
{"config": {"cron": "<5-field cron>", "timezone": "UTC"}}
```

## The rules

1. **The cron MUST have exactly 5 fields** (minute hour day month
   weekday). Examples: `0 * * * *` (hourly), `0 9 * * *` (daily
   9am), `0 9 * * 1` (Mondays 9am), `*/5 * * * *` (every 5 min).
2. **NEVER change the trigger's name, description, or active
   state.** The name is schedule-neutral — it describes WHAT the
   trigger monitors, not WHEN. (The 2026-08-18 lesson: a schedule
   change renamed the trigger 'RSS Monitor: daily 9am' — wrong.)
3. The trigger ids: `monitor-rss-hourly` (RSS Monitor),
   `monitor-market-5min` (Market Watch), and the example triggers.
   List them with `GET /api/v1/triggers?include_inactive=true`.
4. Only schedule-type triggers take a cron — webhook triggers
   reject it.

## Verification (ALWAYS)

After the PUT, read back with `GET /api/v1/triggers/{trigger_id}`
and confirm the config shows the new cron. Report the verified
value, not just "done".

## Common pitfalls

- A 4-field or 6-field cron → the server rejects it (loud).
- Changing the name while setting the cron → forbidden.
- "Every day at 9am" is `0 9 * * *` — NOT `0 9 * *` (4 fields).
