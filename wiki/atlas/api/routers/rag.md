---
title: RAG
type: atlas-api
path: wiki/atlas/api/routers/rag.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/rag, status/active]
---

# RAG — API

## Purpose

Document ingestion (wiki/entities + wiki/dev-notes) + index health stats.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `POST` | `/api/v1/rag/ingest` | Trigger RAG documentation ingestion |
| `GET` | `/api/v1/rag/ingest/status` | Poll the current ingest job status |
| `GET` | `/api/v1/rag/status` | Get RAG index health stats |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[dev-notes/system-expertise/rag/rag-system|RAG System (dev-notes)]]
