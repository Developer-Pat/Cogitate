---
title: Approvals
type: atlas-api
path: wiki/atlas/api/routers/approvals.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/approvals, status/active]
---

# Approvals — API

## Purpose

Human-in-the-loop workflow approvals: pending, approve/reject, request-changes, timeouts.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `POST` | `/api/v1/approvals/check-timeouts` | Check Timeouts |
| `GET` | `/api/v1/approvals/pending` | List Pending Approvals |
| `GET` | `/api/v1/approvals/workflow/{workflow_execution_id}` | Get Approval By Workflow |
| `GET` | `/api/v1/approvals/{approval_id}` | Get Approval |
| `POST` | `/api/v1/approvals/{approval_id}/approve` | Approve Workflow |
| `POST` | `/api/v1/approvals/{approval_id}/reject` | Reject Workflow |
| `POST` | `/api/v1/approvals/{approval_id}/request-changes` | Request Changes |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/workflows|Workflows]]
