---
title: TriggerManagement
type: atlas-component
path: frontend/src/components/features/workflows/TriggerManagement.tsx
confidence: high
updated: 2026-08-10
tags: [type/component, domain/atlas-ui]
---

# TriggerManagement

**Component**: `frontend/src/components/features/workflows/TriggerManagement.tsx`
**Used by**: [[atlas/ui/pages/WorkflowAutomation|Workflow Automation]] page (also was on Workflow Execution before the 2026-08-10 split)

## Purpose

The trigger control panel — monitor + activate/deactivate workflow
triggers (schedule, webhook, database). Shows every trigger
including inactive ones (a control panel must be able to
re-activate), with cron schedule, next run time, and a status
badge.

## Key Features

- Table of ALL triggers (`GET /api/v1/triggers?include_inactive=true`)
  — name, workflow, type, cron, next run, status badge
- **Activate / Deactivate** toggle per trigger with busy state
  and success/error toasts (`useNotificationStore`)
- **Refresh** button reloads triggers + schedules in parallel
- Warning banner: "triggers run on their own schedule… monitor
  triggers ship deactivated — activate only when you want them"
- Rows sorted active-first

## Data Flow

1. `triggerService.getTriggers()` + `triggerService.getSchedules()`
   in parallel (`Promise.all`)
2. Schedules merged onto triggers by `trigger_id` (cron + next_run)
3. Toggle: `deactivateTrigger(id)` or `activateTrigger(id)` →
   `POST /api/v1/triggers/{id}/deactivate` / `/activate`; on
   success the list reloads and `onRefresh` (if provided) fires

## Related

- [[atlas/ui/pages/WorkflowAutomation|Workflow Automation]] — host page
- [[atlas/api/routers/triggers|Triggers API]]
- [[atlas/ui/services/domains/llm/triggerService|triggerService]]
