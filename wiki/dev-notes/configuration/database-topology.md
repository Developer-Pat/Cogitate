---
title: Database Topology
type: atlas-devnote
category: configuration
order: 3
confidence: high
updated: 2026-08-09
tags: [type/dev-notes, domain/configuration]
---

# Database Topology

How the system's databases are organized. The guiding principle
(established by the DB cleanup, 2026-08-09):

> **The main DB holds what the system IS (identity + config).
> Side journals hold what the system DID (high-volume state).**

## The layout

| DB | What it holds | Writes |
|---|---|---|
| `cogitate.db` (root) | identity + config: agents, sessions, messages, providers, curated models, tools, macros, workflows, A/B configs, execution records, usage logs | per request |
| `checkpoints.db` (root) | LangGraph workflow journal (checkpoint + writes per thread) | per workflow step |
| `data/pipeline_traces.db` | cognitive pipeline traces (30-day TTL) | per pipeline run |
| `data/cognitive_memory.db` | shared memory store | per memory op |
| `data/system_docs_vector.db` + `system_code_vector.db` | RAG embedding indexes | on ingestion |
| `data/verification_store.db` | THE HONESTY LOOP (2026-08-19): verified_facts + the track record (claimed vs verified vs outcome, TTL-pruned) — the Exa-program Phase 6 store; see [[dev-notes/design/honesty-loop|The Honesty Loop]] | per verified op |
| `agents/{name}/cognitive_memory.db` | per-agent memory (the real per-agent isolation) | per agent op |

## Why this split

- **Identity/config belongs in one place** — it needs joins
  (agents ↔ sessions ↔ usage ↔ executions). A fragmented main DB
  makes those queries impossible.
- **High-volume journals get their own files** — checkpoint and
  trace growth shouldn't contend with the main DB's reads, and a
  misbehaving journal (unbounded growth, TTL bugs) is isolated.
- **Per-agent isolation = memory, not a DB clone** — agents keep
  their own `cognitive_memory.db`; a full per-agent `cogitate.db`
  was tried (provisioning copied a template) and removed: it was
  never written (chat uses the shared DB).

## What was removed (DB cleanup 2026-08-09)

- **Main-DB `cognitive_traces` table** — gone.
  Nothing ever wrote it (no `session.add` anywhere); the live
  trace store is `pipeline_traces.db`, and the agent-chat trace
  reads now point there. The Debugging UI's trace view works
  because of this fix.
- **Per-agent `cogitate.db` + `agents/.templates/`** — removed
  from provisioning (3A). No per-agent DB clone; isolation is
  `cognitive_memory.db`.
- **`backend/checkpoints.db`** — test pollution (default
  checkpointer path resolved to backend/ when pytest ran from
  there). The workflow-test conftest now redirects the default to
  a tmp path; the root `checkpoints.db` is the live store.

## Related

- [[entities/database-schema|Database Schema]] — the full table-by-table reference
- [[dev-notes/configuration/alembic-migrations|Alembic Migrations]] — the migration chain
- [[dev-notes/tracing/trace-store|Trace Store]] — the trace journal
- [[dev-notes/workflows/checkpointing|Workflow Checkpointing]] — the checkpoint journal
