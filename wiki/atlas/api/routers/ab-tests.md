---
title: A/B Tests
type: atlas-api
path: wiki/atlas/api/routers/ab-tests.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/ab-tests, status/dormant]
---

# A/B Tests — API

## Purpose

Workflow A/B experimentation: create/start/pause/stop, assign, compare, results.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/ab-tests` | List A/B Tests |
| `POST` | `/api/v1/ab-tests` | Create A/B Test |
| `DELETE` | `/api/v1/ab-tests/{test_id}` | Delete A/B Test |
| `GET` | `/api/v1/ab-tests/{test_id}` | Get A/B Test |
| `PUT` | `/api/v1/ab-tests/{test_id}` | Update A/B Test |
| `POST` | `/api/v1/ab-tests/{test_id}/assign` | Assign Version |
| `GET` | `/api/v1/ab-tests/{test_id}/compare` | Compare A/B Test Versions |
| `POST` | `/api/v1/ab-tests/{test_id}/pause` | Pause A/B Test |
| `POST` | `/api/v1/ab-tests/{test_id}/record` | Record A/B Test Result |
| `GET` | `/api/v1/ab-tests/{test_id}/results` | Get A/B Test Results |
| `GET` | `/api/v1/ab-tests/{test_id}/results/raw` | Get Raw A/B Test Results |
| `POST` | `/api/v1/ab-tests/{test_id}/start` | Start A/B Test |
| `POST` | `/api/v1/ab-tests/{test_id}/stop` | Stop A/B Test |

**DORMANT** — core purpose (workflow experimentation), un-expanded. Demo rows kept as test material (user decision 2026-08-07). Documented for the state map.
## Status

**DORMANT** — core purpose, un-expanded (kept; see audit).

## Related

- [[atlas/api/routers/workflows|Workflows]]
