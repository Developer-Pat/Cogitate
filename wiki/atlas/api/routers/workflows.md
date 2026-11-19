---
title: Workflows
type: atlas-api
path: wiki/atlas/api/routers/workflows.md
category: api-atlas
order: 5
confidence: medium
updated: 2026-08-14
tags: [type/api, domain/workflows, status/active]
---

# Workflows — API

> Routers: `backend/app/workflows/api/` — 8 modules (workflow,
> template, multi_agent, composition, approval, triggers,
> webhooks) + workflow_lists + versions routers.
> Status: **ACTIVE** — workflow execution is Cogitate's core
> purpose (workflow design + experimentation). Versioning +
> ab-testing (the DORMANT half) live in separate routers.

## Purpose

Workflow lifecycle: **execution** (run a workflow, status,
history, cancel, rollback, recover, checkpoints), **templates**
(categories + the configured workflow instances — the API keeps
the historical `templates` route name; the kind registry lives
under `/workflow-kinds`, see
[[atlas/api/routers/workflow-kinds|Workflow Kinds]]), **multi-agent**
(workflows that delegate between agents), **compositions**,
**approvals** (human-in-the-loop gates), **triggers** (schedules +
webhooks that launch workflows), **webhooks** (receive external
events), **workflow lists** (curated collections), and
**versions** (versioned workflow configs — DORMANT, see
[[atlas/api/routers/ab-tests|A/B Tests]] + versions note).

## Endpoints

### Execution (`workflow_router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/workflows/execute` | Execute a workflow |
| `DELETE` | `/workflows/products` | **Clear all products** (NEW 2026-08-10) — deletes product files + display index (keeps monitor `state.json`); the Products page's Clear action |
| `GET` | `/workflows/toasts?since=<cursor>` | **Product toasts** (NEW 2026-08-10) — drains the ToastDistributor queue (`toasts.json`); the frontend polls with a localStorage cursor and shows app-wide in-app toasts |
| `GET` | `/workflows/products` | **List workflow products** (NEW 2026-08-10) — the display index (`data/monitor/products.json`), written by DisplayDistributor; backs the Workflow Products page. |
| `GET` | `/workflows/executions` | **List execution records** (NEW 2026-08-10) — `template_id` / `trigger_id` / `limit` filters; reads `workflow_execution_history`. The scheduler records `input_data.trigger_id` on triggered runs, so direct vs triggered executions are distinguishable. Backs the Automation page's per-trigger run history. |
| `GET` | `/workflows/{workflow_id}/status` | Execution status |
| `POST` | `/workflows/{workflow_id}/approve` | Approve a step |
| `GET` | `/workflows/{workflow_id}/history` | Execution history |
| `DELETE` | `/workflows/{workflow_id}` | Delete workflow |
| `GET` | `/workflows/retention` | **The run-retention policy** — the effective windows, the shipped DEFAULTS they resolved against, and what the store holds (rows, snapshot bytes, oldest/newest) |
| `PUT` | `/workflows/retention` | Change the windows (a PARTIAL body; values are validated, so a nonsense window is refused rather than stored) |
| `POST` | `/workflows/retention/prune?dry_run=true&confirm=false` | **Preview (`dry_run=true`, the default) or apply the retention windows.** A preview measures exactly what the act would and changes nothing; applying requires `confirm=true`, and the endpoint's own check refuses an apply without it (every way of not saying it lands on the same 400) |
| `POST` | `/workflows/executions/{execution_id}/cancel` | Cancel |
| `GET` | `/workflows/{workflow_id}/debug/state` | Inspect state |
| `GET` | `/workflows/{workflow_id}/debug/trace` | The run's Langfuse trace: its **derived** `trace_id` (always — the id the run's node spans were sent under, so the three cannot drift) + `trace_url` (None when tracing is off, or when the SDK could not resolve the link — it needs the network), + `langfuse_enabled` |
| `POST` | `/workflows/{workflow_id}/rollback` | Rollback |
| `POST` | `/workflows/{workflow_id}/recover` | Recover failed |
| `GET` | `/workflows/{workflow_id}/checkpoints` | List checkpoints |

### Templates (`template_router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/workflows/templates/categories` | Template categories |
| `GET` | `/workflows/templates` | List templates (filters: category, tags, limit, offset) |
| `POST` | `/workflows/templates` | **Create template (NEW 2026-08-14)** — body: `{name, description?, category?, version?, author?, tags?, workflow_type?, config?, is_public?, is_customizable?, inputs?}`; the WorkflowTemplates editor's save path (was MISSING — 405, the New Template flow was dead end-to-end) |
| `PUT` | `/workflows/templates/{id}` | **Update template (NEW 2026-08-14)** — partial body; 404 if missing |
| `DELETE` | `/workflows/templates/{id}` | **Delete template (NEW 2026-08-14)** — 404 if missing |
| `POST` | `/workflows/templates/validate` | **Validate before save (NEW 2026-08-14)** — the editor's save gate; `{name, description?, steps?, config?}` → `{isValid, errors, warnings}` |
| `POST` | `/workflows/templates/{id}/validate-execution` | **Validate execution inputs (NEW 2026-08-14)** — body `{inputs: {...}}` (WRAPPED, matching the frontend) against the template's declared inputs; 404 if missing |

> CRUD was missing until 2026-08-14 (only GET list/categories existed;
> the 33 templates were seeded). The editor called POST/PUT/DELETE +
> both validate endpoints — all dead (405/404), so "New template" and
> "Save" never worked. Fixed with the endpoints above; 9 regression
> tests (test_workflow_template_crud.py); live-verified end-to-end.

### Multi-agent (`multi_agent_router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/multi-agent/execute` | Run a multi-agent workflow |
| `GET` | `/multi-agent/templates` | List templates |
| `GET` | `/multi-agent/templates/{template_id}` | Get template |
| `GET` | `/multi-agent/health` | Health check |

### Compositions (`composition_router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/compositions/{composition_id}` | Get |
| `POST` | `/compositions/{composition_id}/execute` | Execute |
| `PUT` | `/compositions/{composition_id}` | Update |
| `DELETE` | `/compositions/{composition_id}` | Delete |

### Approvals (`approval_router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/approvals/pending` | List pending |
| `GET` | `/approvals/{approval_id}` | Get |
| `GET` | `/approvals/workflow/{workflow_execution_id}` | By workflow |
| `POST` | `/approvals/{approval_id}/approve` | Approve |
| `POST` | `/approvals/{approval_id}/reject` | Reject |
| `POST` | `/approvals/{approval_id}/request-changes` | Request changes |
| `POST` | `/approvals/check-timeouts` | Check timeouts |

### Triggers + webhooks

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/triggers` | List triggers (`include_inactive` query — the control panel shows ALL triggers) |
| `GET` | `/triggers/{trigger_id}` | Get trigger |
| `PUT` | `/triggers/{trigger_id}` | Update |
| `DELETE` | `/triggers/{trigger_id}` | Delete |
| `POST` | `/triggers/{trigger_id}/activate` | Activate |
| `POST` | `/triggers/{trigger_id}/deactivate` | Deactivate |
| `GET` | `/triggers/schedules/list` | List schedules |
| `GET` | `/triggers/webhooks/endpoints` | List webhook endpoints |
| `POST` | `/webhooks/{endpoint_path}` | Receive external event |
| `GET` | `/webhooks/endpoints` | List endpoints |
| `POST` | `/webhooks/test/{trigger_id}` | Test trigger |

## Auth

All endpoints require an authenticated session. Webhook receive is
the exception — public by design (external systems post events).

## Status

**ACTIVE** — workflow execution/templates/approvals/triggers are
live and used by the Workflows page (the configured instances). The
versioning/ab-testing sub-system is **DORMANT** (core purpose,
un-expanded — see [[atlas/api/routers/ab-tests|A/B Tests]]).

## Related

- [[atlas/ui/components/features/workflows/Workflows Index|Workflows UI]]
- [[dev-notes/workflows/workflow-architecture|Workflow Architecture (dev-notes)]]
- [[atlas/api/routers/ab-tests|A/B Tests]] — DORMANT experimentation
- [[atlas/api/routers/workflow-lists|Workflow Lists]]
- [[atlas/api/routers/ab-tests|A/B Tests]] — includes workflow
  versions (DORMANT: versioned configs)
