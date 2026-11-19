---
title: Workflow Checkpointing
type: atlas-devnote
category: workflows
order: 4
confidence: medium
updated: 2026-08-05
tags: [type/dev-notes, domain/workflows]
---

# Workflow Checkpointing

## Overview

LangGraph checkpointing for workflow state across steps
(backend/app/workflows/checkpointing/): config.py + the
checkpointer wiring in workflow compilation.

## Purpose

- Persist graph state between nodes so interrupted/resumed
  workflows continue where they left off.
- Config-driven (checkpointing/config.py) — toggle + storage
  backend.

## Storage backend

**SQLite** — `SqliteSaver.from_conn_string("./checkpoints.db")`
(checkpointing/config.py). LangGraph 1.0+ caveat: the factory
returns a **context manager**, not an instance (breaking change
from <1.0) — the config module handles this via `get_checkpointer()`
+ `close()` lifecycle.

## Resume surface

- Checkpoint state is persisted between nodes in `checkpoints.db`,
  enabling interrupt/resume for interrupted workflows.
- The workflows API exposes `POST /workflows/{workflow_id}/recover`
  + `POST /workflows/{workflow_id}/rollback` (workflow_router.py)
  as the resume/rollback surface.
- `GET /workflows/{workflow_id}/checkpoints` lists checkpoints.
