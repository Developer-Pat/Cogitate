---
title: Database Schema
type: atlas-entity
path: wiki/entities/database-schema.md
confidence: medium
updated: 2026-11-18
tags: [type/entity, domain/entities]
---

# Database Schema

## Database inventory

| DB | Location | Purpose |
|---|---|---|
| Main app | cogitate.db (root) | **56 tables on a live install** — the 53 the models build, plus `alembic_version`, the runtime `_sqlite_manager_audit_log`, and SQLite's own `sqlite_sequence` — agents, chat, sessions, providers, curated_models, tools, macros, workflows, collections, etc. (alembic: one baseline, `0001`) |
| Workflow checkpoint journal | checkpoints.db (root) | LangGraph workflow state (SqliteSaver); separate from the main DB |
| Documents | data/cogitate_docs_en.db | document corpus for RAG |
| Pipeline traces | data/pipeline_traces.db | per-request pipeline traces (30-day TTL) — **the single trace store** |
| Cognitive memory | data/cognitive_memory.db | shared memory store |
| Vector | data/system_docs_vector.db, system_code_vector.db | RAG/doc indexing embeddings |
| Per-agent memory | agents/{name}/cognitive_memory.db | deep-agent memory (researcher, system-manager, math-tutor...) |

**Topology principle** (see
[[dev-notes/configuration/database-topology|Database Topology]]):
the main DB holds identity + config (what the system IS); side
journals hold high-volume state (what the system DID):
checkpoints.db (workflow state), pipeline_traces.db (traces). Each
of these has exactly one home:
- **Traces** — pipeline_traces.db only. The main DB carries no
  `cognitive_traces` table, and the agent-chat trace reads point
  there.
- **Per-agent isolation** — each deep agent's `cognitive_memory.db`.
  There is no per-agent `cogitate.db` and no `agents/.templates/`.
- **The test checkpointer** — redirected to a tmp path by the test
  conftest, so tests never write `backend/checkpoints.db`.

## Main schema notes

- **Migration-managed**: one baseline revision (`0001`), generated from the models, so
  `create_all` (which `init_db` runs at startup) and `alembic upgrade head` build the same
  schema. See [[dev-notes/configuration/alembic-migrations]].
- **Curated models**: curated_models table (provider_id FK,
  model_id, name, category, verified) — DB is source of
  truth; frontend seed is fallback.
- **Providers**: providers table + keys in .env (see
  [[dev-notes/configuration/configuration-surface]]); api_key_
  encrypted column retired from new writes.
- **Agents**: agents + agent_versions + agent_templates +
  agent_tools (tool enablement) + health_dismissed_at (F6).
- **Macros**: macro_sets + meta_topics tables (AgentMacroService).
- **Workflows**: ab_test_configs, ab_test_results,
  workflow_* tables + workflow_execution_history (execution
  identity — see [[dev-notes/tracing/trace-store]] and the
  execution-identity proposal).

## Table-by-table reference

### Core: agents & chat

**agents** (17) — agent registry:
`id, name, description, provider, model, system_prompt, is_active,
profile_image_url, created_at, updated_at, parameters (JSON),
template_id, preferred_providers (JSON), fallback_enabled,
allow_delegation, is_builtin, execution_mode, behavior_config
(JSON), cognitive_profile_id, health_dismissed_at (F6)`

**chat_sessions** (2) — `id, title, agent_id FK, is_active,
created_at, updated_at, source` (default "agent")

**chat_messages** (86) — `id, session_id FK, role, content,
token_count, model, provider, total_time_ms, tokens_per_second,
created_at` — the metadata fields (see [[dev-notes/agents/message-metadata|Message Metadata]])

**chat_attachments** (5) — `id, session_id FK, original_filename,
stored_filename, file_type, file_size, file_path, mime_type,
created_at`

~~conversation_states~~ + ~~conversation_summaries~~ — gone
(legacy tables, zero references)

### Providers & models

**providers** (5) — `id, name, display_name, api_key_encrypted
(retired from writes), base_url, is_active, priority,
provider_type, config (JSON), is_default, created_at, updated_at`
— keys live in `.env` (EnvKeyStore), not the DB

**curated_models** (38) — `id, model_id, model_name, provider_id
FK, category, description, context_length, is_free,
is_active, verified, created_at, updated_at` — the
human-curated list (DB = source of truth; frontend seed = fallback)

**provider_model_cache** (496) — cached live model catalogs:
`provider_id FK, model_id, name, display_name, description,
context_length, pricing_prompt, ...` (populated by discovery)

**provider_sync_schedules** (0) — `provider_id, sync_interval_hours,
last_sync_at, next_sync_at, sync_enabled, last_sync_status`

### Tools

**tools** (42) — `id (TEXT), name, slug, description, version,
category_id, provider, type, config_schema (JSON),
arguments_schema (JSON), endpoint, timeout_ms, requires_auth,
icon, color, tags (JSON), is_active, is_builtin, usage_count,
created_at, updated_at`

**tool_categories** (6) — `id, parent_id, name, slug, description,
icon, sort_order, created_at, updated_at`

**agent_tools** (72) — junction: `agent_id, tool_id, is_enabled,
priority, config, created_at, updated_at`

**team_tools** (4) — team-tool assignments: `team_id, tool_id,
source_type, source_id, priority, is_active, config`

**tool_collection_permissions** (0) — `tool_id, collection_id,
permission_level, created_at, updated_at`

**tool_usage_logs** (144) — `tool_id, agent_id, session_id,
success, execution_time_ms, error_message, log_metadata, ...`

### Usage & health

**usage_logs** (435) — `id, session_id, agent_id, provider,
model, prompt_tokens, completion_tokens, total_tokens, cost_usd,
response_time_ms, success, error_message, created_at` — the LLM
call history; **the health-scan source** (naive-UTC timestamps).

### Macros

**macro_sets** (63) — `id, user_key, topic, name, description,
f1_macro..f5_macro, is_active, sort_order, namespace, created_at,
updated_at`

**meta_topics** (20) — `id, user_key, namespace, name, description,
topic_mappings (JSON), is_active, created_at, updated_at`

### Workflows

**workflow_templates** (30) — `id (TEXT), name, description,
category, version, author, tags, workflow_type, config, is_public,
is_customizable, inputs, created_at, updated_at`

**workflow_compositions** (1,112) — `name, description, config_json,
version, tags, is_active, ...`

**workflow_versions** (3) + **ab_test_configs** (2) +
**ab_test_results** (9,874) — the DORMANT experimentation family
(kept as test material; see [[atlas/api/routers/ab-tests|A/B Tests]]).
`ab_test_results.execution_id` joins `workflow_execution_history.id`
(the execution-identity join).

**workflow_approvals** (0), **workflow_triggers** (3),
**workflow_lists** (7)

**workflow_execution_history** (0) — execution identity records.
WIRED: written on every workflow run
(start/complete/error) with template, agent link (metadata JSON),
input/output, elapsed; DELETE endpoint + 30-day prune available.
The anonymous wf-<uuid> checkpoint thread is backed by a
first-class record.

### Cognitive

**cognitive_profiles** (7) — pipeline behavior profiles:
`name, context_builder, executor, response_formatter,
memory_profile_id, config_json, ...`

**memory_profiles** (3) — `name, strategy, window_size, persistence,
compaction_threshold, summarization, ...`

~~cognitive_traces~~ — gone.
This main-DB table was never written (no session.add anywhere);
the live traces live in pipeline_traces.db, and the agent-chat
trace reads (session/traces, metrics, trace-stream) now point there.

**cognitive_presets** (0)

### Platform

**logs** (35), **collections** (9) + **collection_items** (28),
**agent_lists** (2), **agent_templates** (3), **agent_versions** (0),
**frontend_agent_packages** (5), **prompt_templates** (0),
**runtime_configs** (0), **user_settings** (1),
**system_flags** (1 — external_access_enabled),
**system_manager_config** (0) + **records** (0),
**documents** (0) + **document_analytics** (0) +
**document_relations** (0) (RAG docs — empty in this DB),
**_sqlite_manager_audit_log** (0)

~~legacy macro-set tables~~ + ~~execution_plans~~ — gone
(legacy tables, zero references)
