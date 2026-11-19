---
title: RAG System
type: atlas-devnote
category: rag
order: 1
confidence: medium
updated: 2026-10-12
tags: [type/dev-notes, domain/rag]
---

# RAG System

**The retrieval leg of [[dev-notes/system-expertise/System Expertise Index|System Expertise]]** — what
answers *"where in the corpus is the passage about this?"*, and everything that keeps that answer true.

## Overview

Retrieval-augmented generation over the app's documents. Backend:
backend/app/domain/rag/ + backend/app/api/v1/rag/.

## Current shape

- **RagIngestService** (domain/rag/service.py) — the ingestion
  engine: `run()` performs indexing; `get_status` / `is_running` /
  `get_index_health` expose state. Single-flight (is_running guard
  prevents concurrent ingest).
- **API** (api/v1/rag/router.py): GET /status, POST /ingest,
  GET /ingest/status.
- **Vector stores** — three, and they do different jobs:
  - `DocVectorStore` (`tools/builtin/doc_vector_store.py`) — the wiki index
    (`data/system_docs_vector.db`, table `vec_docs`), serving the doc tools;
  - `CodeVectorStore` (`tools/builtin/code_vector_store.py`) — the code index
    (`data/system_code_vector.db`, table `vec_code`);
  - `TurnVectorStore` (`services/cognitive_pipeline/vector_store.py`) — per-agent conversation recall,
    built per pipeline construction rather than held.
  **The first two are SINGLETONS, and they capture the resolved embedding service at FIRST
  CONSTRUCTION** — see "Index health" below for what that means for a running process.

## Ingestion pipeline

- **Trigger**: `POST /api/v1/rag/ingest` (mode: incremental | full
  | force-reingest) → background task → poll `GET /rag/ingest/status`.
- **Embedding model**: the **`embeddings` capability** names the provider row AND the model, and the
  vector width is DERIVED from the model (`domain/providers/embeddings.py`). No model is written in
  code: a fresh install ships the capability EMPTY and reports
  (`no embedding model: indexing and search are off`) — 503 on ingest, and null in the health response
  — rather than embedding with a model nobody chose.
- **Chunking**: files → markdown-only (`.md`) → incremental
  mtime checks → `DocVectorStore` chunking/embedding/indexing.
- **Source dirs** (`INGESTION_DIRS`, and these are what `/rag/status` reports): `wiki/entities`,
  `wiki/dev-notes`, `wiki/atlas`, `wiki/help`, `wiki/docs`, `wiki/references` — the whole-wiki surface
  below. `wiki/display-tests` and `wiki/_archive` are excluded.

## Retrieval flow (tools)

- `doc_index` + `doc_reader` (tools/builtin/) serve retrieval to
  tools: doc-index for topic lookup, doc-reader for semantic search
  over the vector store.
- The documents DB (cogitate_docs_en.db) holds the corpus.

## Index health

- `GET /api/v1/rag/status` — index stats, plus the embedding configuration in FOUR fields, because
  what an install CONFIGURED and what the running process is DOING are two different answers:
  - `embedding_model` / `ollama_base_url` — the `embeddings` capability's answer (null for each half an
    install has not configured);
  - `index_width` — the width the index was **created** at, read from its own `vec_docs` table;
  - `running_model` / `running_address` — what the stores in THIS process were built with (null when
    none has been built yet);
  - `note` — the sentence to show when the two disagree: *the change takes effect after a restart*, or,
    for a WIDTH change, *the index is 768 wide and this model is 1024 — re-run the ingest* (a restart
    does not repair that one: `init_db` declares the table with `IF NOT EXISTS`, so it keeps the width
    it was born with).
  The path it reads is `Paths.rag_index_path` — the same locator the ingest, both search routes,
  `doc_reader` and the registry use.
- `GET /api/v1/rag/ingest/status` — job status
  (`data/rag_ingest_status.json`).

## Changing the embedding model

`resolve_embedding_service` answers *(address, model, dims)* from the `embeddings` capability. The two
RAG stores capture that answer at FIRST CONSTRUCTION — and **the capability write path resets them**:
`capabilities.replace_chain` drops both when an `embeddings` chain changes (`reset_instance(close=False)`,
so an ingest that is mid-flight finishes against the service it started with). So:

- **a saved model reaches the process on its next use** — the store is rebuilt from the new chain;
- **an install that has configured NOTHING has no stale store** — every construction site refuses before
  building, so configuring one works immediately;
- **a model of a DIFFERENT WIDTH needs the index rebuilt, not just a reset**: `init_db` declares the vec
  table with `IF NOT EXISTS`, so an index keeps the width it was born with. The store refuses rather
  than inserting vectors its table cannot hold, and `/rag/status` (and the capability save) reports the
  mismatch in `note`.

An ingest is the expensive half of that change and nothing rebuilds itself: `POST /api/v1/rag/ingest` is
started by hand (or by Exa), and the index's currency is a policy decision — nothing auto-reingests.

## The whole-wiki surface + search-knowledge (2026-08-19)

Phase 4 of the Exa program: the ingest surface widened to the
WHOLE wiki (506 files — atlas 391, dev-notes 71, help 27,
entities 11, docs 5, references 1; display-tests + _archive
denied). Re-ingest: 506/506 files, 3527 fresh chunks, 0 failed,
~5.3 min at ~47 chunks/s warm. The index was STALE since 6/11
(the surface was 82 files) — the refresh cadence is an OPEN
policy decision (nothing auto-reingests).

The `search-knowledge` tool (GRAS) wraps the lookup — the query
is embedded + ANN-searched; results carry source paths + scores.
Live-verified: "how does the trigger service work?" →
useWorkflowAutomation.md (0.841) + event-triggers.md (0.821).
