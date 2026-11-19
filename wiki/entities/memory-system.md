---
title: Memory System
type: atlas-entity
path: wiki/entities/memory-system.md
confidence: medium
updated: 2026-08-05
tags: [type/entity, domain/entities]
---

# Memory System

## Overview

Multi-layered memory:

1. **Per-agent cognitive memory** — agents/{name}/cognitive_memory.db
   (SQLite per deep agent). Facts stored under agent_{id}:facts keys.
2. **Shared cognitive memory** — data/cognitive_memory.db.
3. **Chat history** — chat_sessions + chat_messages in cogitate.db.
4. **Pipeline traces** — data/pipeline_traces.db (30-day TTL).
5. **Vector stores** — system_docs_vector.db + system_code_vector.db
   for RAG.

## Cognitive pipeline

backend/app/services/cognitive_pipeline/ — pipeline.py + models.py
(CognitiveResult) + trace_store.py. Deep agents use cognitive
profiles (conversational, research-std, code-gen, system-admin...) —
capability-based, not role-based (see
[[concepts/cognitive-profiles]]).

## KV store schema (KVStoreMemoryManager)

Persistent SQLite memory (`data/cognitive_memory.db`), JSON blobs
keyed per agent+session:

| Key | Content |
|-----|---------|
| `agent_{id}:facts` | extracted facts for the agent |
| `agent_{id}:summary:{session_id}` | per-session summary |
| `agent_{id}:session:{session_id}` | conversation memory |

Contrast: `DefaultMemoryManager` is in-memory (lost on restart).
Deep agents use the KV store (persistent).

## Pipeline architecture

The cognitive pipeline (services/cognitive_pipeline/: pipeline.py,
models.py, memory_manager.py) runs: context builder → executor →
memory update → response formatter, per the cognitive profile
(context_builder/executor/memory_manager/response_formatter
strategies). See [[concepts/cognitive-profiles]] + the services
map [[atlas/services/cognitive|Cognitive Services]].
