---
title: Cognitive
type: atlas-api
path: wiki/atlas/api/routers/cognitive.md
category: api-atlas
order: 8
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/cognitive, status/active]
---

# Cognitive — API

> Routers: `backend/app/api/v1/cognitive_pipeline/` (profiles),
> `cognitive_memory/`, `cognitive_vectors/`.
> Status: **ACTIVE** — the cognitive pipeline (memory, profiles,
> vector recall) behind agent behavior.

## Purpose

The cognitive layer: **cognitive profiles** (pipeline behavior
config — memory depth, summarization, retrieval strategy),
**memory profiles** (per-agent memory settings), **memory**
(cognitive_memory router — agent memory CRUD/queries), and
**vectors** (per-agent vector storage: index turns, search,
session removal, clear).

## Endpoints

### Cognitive profiles (`/api/v1/cognitive-profiles`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/cognitive-profiles/{profile_id}` | Get profile |
| `PUT` | `/cognitive-profiles/{profile_id}` | Update profile |
| `DELETE` | `/cognitive-profiles/{profile_id}` | Delete profile |

### Memory profiles (`/api/v1/memory-profiles`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/memory-profiles/{profile_id}` | Get profile |
| `PUT` | `/memory-profiles/{profile_id}` | Update |
| `DELETE` | `/memory-profiles/{profile_id}` | Delete |

### Vectors (`/api/v1/cognitive/vectors/{agent_folder}`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/cognitive/vectors/{agent_folder}/search` | Semantic search over agent memory |
| `POST` | `/cognitive/vectors/{agent_folder}/index` | Index a conversation turn |
| `DELETE` | `/cognitive/vectors/{agent_folder}/session/{session_id}` | Remove a session's vectors |
| `DELETE` | `/cognitive/vectors/{agent_folder}/all` | Clear agent vectors |

### Memory (`/api/v1/cognitive/memory` — KVStoreMemoryManager)

| Method | Path | Purpose |
|--------|------|---------|
| `DELETE` | `/cognitive/memory/session/{agent_id}/{session_id}` | Clear one session's memory |
| `DELETE` | `/cognitive/memory/agent/{agent_id}` | Clear an agent's memory |
| `DELETE` | `/cognitive/memory/all` | Clear all memory |
| `POST` | `/cognitive/memory/prune` | Prune old sessions (max_days=30 default) |
| `GET` | `/cognitive/memory/{agent_folder}/status` | Memory status (session/turn/fact/summary counts) |
| `GET` | `/cognitive/memory/agents` | List deep agents |
| `GET` | `/cognitive/memory/{agent_folder}/export` | Export memory |
| `DELETE` | `/cognitive/memory/{agent_folder}/clear/all` | Clear agent folder |
| `DELETE` | `/cognitive/memory/{agent_folder}/clear/sessions` | Clear agent sessions |

Facts recall/store happens through the pipeline (MemoryManager)
rather than REST; this router is the clear/reset/status surface.

## Auth

All endpoints require an authenticated session.

## Status

**ACTIVE** — cognitive pipeline is the memory/recall backbone;
memory isolation fixes are tracked in todo (facts key, session
bleed).

## Related

- [[atlas/ui/components/features/cognitive/Cognitive Index|Cognitive UI]]
- [[dev-notes/agents/cognitive-hub|Cognitive Hub (dev-notes)]]
- [[atlas/api/routers/agents|Agents]] — per-agent cognitive config
