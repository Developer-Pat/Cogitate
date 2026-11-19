---
title: Logs
type: atlas-api
path: wiki/atlas/api/routers/logs.md
category: api-atlas
order: 6
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/logs, status/active]
---

# Logs — API

> Router: `backend/app/api/v1/logs/router.py`.
> Status: **ACTIVE** — the Logs page + monitoring surfaces.

## Purpose

Log ingestion + querying: **frontend log ingestion** (the UI
posts console/error logs), **file-backed logs**, **queries**
(recent, sources, stats), **streaming** (SSE live log feed),
**rotation/clear** (housekeeping), **test log generation** (dev
fixtures), and **trace export** (Langfuse-style traces).

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/logs/stats` | Aggregate log stats |
| `POST` | `/logs/frontend` | Ingest a frontend log entry |
| `POST` | `/logs/frontend/batch` | Batch ingest |
| `GET` | `/logs/sources` | Distinct log sources |
| `GET` | `/logs/recent` | Recent logs |
| `GET` | `/logs/stream` | SSE live stream |
| `GET` | `/logs/traces/export` | Export traces |
| `POST` | `/logs/file` | Write to log file only |
| `GET` | `/logs/file/recent` | Recent file logs |
| `GET` | `/logs/file/stats` | File log stats |
| `POST` | `/logs/rotate` | Rotate log files |
| `DELETE` | `/logs/file/clear` | Clear file logs |
| `POST` | `/logs/test/frontend` | Generate test frontend log |
| `POST` | `/logs/test/backend` | Generate test backend log |
| `POST` | `/logs/test` | Create test log |
| `GET` | `/logs/test` | List test logs |
| `DELETE` | `/logs/{log_id}` | Delete one log |

## Auth

All endpoints require an authenticated session. Frontend ingestion
is open to the UI session (it's the app's own logging path).

## Status

**ACTIVE** — Logs page, Debugging page (LogViewer), monitoring.

## Related

- [[atlas/ui/pages/Logs|Logs page]]
- [[atlas/ui/components/features/debugging/LogViewer|LogViewer]]
- [[dev-notes/tracing/tracing-architecture|Tracing Architecture (dev-notes)]]
