---
title: Multi-Agent
type: atlas-api
path: wiki/atlas/api/routers/multi-agent.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/multi-agent, status/active]
---

# Multi-Agent — API

## Purpose

Multi-agent workflow execution + templates + health.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `POST` | `/api/v1/multi-agent/execute` | Execute Multi Agent Workflow |
| `GET` | `/api/v1/multi-agent/health` | Multi Agent Health Check |
| `GET` | `/api/v1/multi-agent/templates` | List Multi Agent Templates |
| `GET` | `/api/v1/multi-agent/templates/{template_id}` | Get Multi Agent Template |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/workflows|Workflows]]
