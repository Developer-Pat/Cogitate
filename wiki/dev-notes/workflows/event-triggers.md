---
title: Event Triggers
type: atlas-devnote
category: workflows
order: 3
confidence: medium
updated: 2026-08-10
tags: [type/dev-notes, domain/workflows]
---

# Event Triggers

## Overview

Workflows can be triggered by events, not just direct dispatch.
backend/app/workflows/triggers/:

- **event_router.py** — routes events to workflows
- **scheduler.py** — scheduled/periodic triggers
- **webhook_handler.py** — inbound webhooks → workflow starts

API: triggers_router.py + webhooks_router.py
(backend/app/workflows/api/).

## Trigger config schemas (domain/workflows/schemas/trigger_config.py)

**WebhookConfig** — `endpoint` (path, e.g. "/github"), `secret`
(optional HMAC verification), `allowed_events` (list), `headers`
(expected validation headers).

**ScheduleConfig** — `cron` (5-field expression, e.g. "0 9 * * *"
daily 9am), `timezone` (default UTC), `enabled`. Backed by
APScheduler (`triggers/scheduler.py`): add_job(trigger_id,
workflow_id, cron_expression, timezone).

**The monitor family's scheduled triggers** — `monitor-rss-hourly` (cron `0 * * * *` → rss-monitor)
and `monitor-market-5min` (cron `*/5 * * * *` → market-watch), seeded by
`scripts/core/seed_monitor_templates.py`. **Both seed with `enabled: false`**: the rows exist and
nothing fires until a person turns one on. See [[docs/workflow-catalog]] §4.

**DatabaseTriggerConfig** — DB-event driven triggers (table
watchers).

## Event payload

Webhook receive: `POST /api/v1/webhooks/{endpoint_path}` — the
raw body is the event payload; validated against the trigger's
allowed_events/headers. Test via `POST /webhooks/test/{trigger_id}`.

## Scheduler format

Cron expressions (standard 5-field): minute hour day month
weekday. Examples: "0 9 * * *" (daily 9am), "*/5 * * * *"
(every 5 min).
