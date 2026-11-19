---
title: Diagnostics
type: atlas-api
path: wiki/atlas/api/routers/diagnostics.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/diagnostics, status/active]
---

# Diagnostics — API

## Purpose

System diagnostics: run all/single, resolve, metrics, delete. Dev tooling.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/diagnostics` | List Diagnostics |
| `GET` | `/api/v1/diagnostics/metrics` | Get Diagnostics Metrics |
| `DELETE` | `/api/v1/diagnostics/resolved` | Delete Resolved Diagnostics |
| `POST` | `/api/v1/diagnostics/run` | Run All Diagnostics |
| `DELETE` | `/api/v1/diagnostics/{diagnostic_id}` | Delete Diagnostic |
| `POST` | `/api/v1/diagnostics/{diagnostic_id}/resolve` | Resolve Diagnostic |
| `POST` | `/api/v1/diagnostics/{diagnostic_id}/run` | Run Single Diagnostic |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/ui/pages/Debugging|Debugging page]]
