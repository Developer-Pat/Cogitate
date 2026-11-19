---
title: Trigger Service
type: atlas-service
path: frontend/src/services/domains/llm/triggerService.ts
confidence: high
updated: 2026-08-10
tags: [type/service, domain/atlas-ui]
---
# Trigger Service

**Path**: `frontend/src/services/domains/llm/triggerService.ts`
**Type**: service

## Purpose

Control surface for workflow triggers — the data layer behind the
[[atlas/ui/components/features/workflows/TriggerManagement|TriggerManagement]]
control panel and the
[[atlas/ui/pages/WorkflowAutomation|Workflow Automation]] page.
Wraps `/api/v1/triggers` behind a typed `ITriggerService`.

**Added 2026-08-10** (with the trigger control panel + the
direct/triggered execution split).

## Methods

| Method | Endpoint | Purpose |
|---|---|---|
| `getTriggers()` | `GET /api/v1/triggers?include_inactive=true` | List ALL triggers (a control panel must show inactive ones too, so they can be re-activated) |
| `activateTrigger(id)` | `POST /api/v1/triggers/{id}/activate` | Activate a trigger |
| `deactivateTrigger(id)` | `POST /api/v1/triggers/{id}/deactivate` | Deactivate a trigger |
| `getSchedules()` | `GET /api/v1/triggers/schedules/list` | Schedule info incl. next run time |

## Related

- [[atlas/ui/components/features/workflows/TriggerManagement|TriggerManagement]]
- [[atlas/api/routers/triggers|Triggers API]]
