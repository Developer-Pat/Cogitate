---
title: Wiki
type: atlas-api
path: wiki/atlas/api/routers/wiki.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/wiki, status/active]
---

# Wiki — API

## Purpose

Wiki content API: index tree, help context, page content.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/wiki` | Get Wiki Index |
| `GET` | `/api/v1/wiki/` | Get Wiki Index |
| `GET` | `/api/v1/wiki/help` | Get Wiki Help Context |
| `GET` | `/api/v1/wiki/{path}` | Get Wiki Page |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/ui/pages/WikiViewer|WikiViewer]]
