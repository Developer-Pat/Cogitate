---
title: Workflow Architecture
type: atlas-devnote
category: workflows
order: 1
confidence: medium
updated: 2026-08-05
tags: [type/dev-notes, domain/workflows]
---

# Workflow Architecture

## Overview

Workflows are **LangGraph graphs** (backend/app/workflows/graphs/):
simple_workflow, advanced_workflow, multi_agent_graph,
composition_graph, context_indexer_graph, file_clerk_graph,
boss_agent_graph, agent_workflows, default_provider_test_graphs.

## Dispatch model

- **Kind registry** — `domain/workflows/kinds/registry.py`: `KIND_REGISTRY`
  declares the kinds, and `KIND_GRAPH_FACTORIES` maps kind →
  `(module, factory)`, imported lazily by `resolve_kind_graph_factory()` to
  avoid circular imports at startup.
- **Routing**: a kind or template name resolves to its compiled workflow graph;
  results return as structured data.
- **Nodes**: backend/app/workflows/nodes/ (simple_nodes, router_node,
  classifier_node, agent_nodes, enhanced_nodes, boss_agent_nodes,
  file_clerk_nodes, context_indexer_nodes).
- **State**: RunMetadata + WorkflowState
  (state/workflow_state.py).
- **API**: workflow_router, composition_router, triggers_router,
  webhooks_router, approval_router, multi_agent_router,
  template_router (workflows/api/).

## Graph registration

A kind is registered in two places, and they must agree:

- `KIND_REGISTRY` — the kind's declaration (name, description, `builder_key`)
- `KIND_GRAPH_FACTORIES` — `kind_name: (module, factory)`, the lazy import the
  resolver calls

The `workflow_kinds` row stores the same `builder_key`, so a kind that exists in
one place and not the other cannot resolve a graph.

## State schema (workflows/state/workflow_state.py)

**WorkflowState** (LangGraph TypedDict):

| Field | Type |
|-------|------|
| `messages` | Annotated[list[BaseMessage], add_messages] |
| `workflow_id` / `template_id` | str |
| `inputs` | dict |
| `current_step` | Optional[str] |
| `execution_result` / `outputs` | Optional[dict] |
| `approval_required` | bool |
| `approval_status` | "pending" \| "approved" \| "rejected" |
| `metadata` | Annotated[RunMetadata, merge_run_metadata] |
| `tool_calls_history` | Annotated[list[dict], operator.add] |
| `tool_loop_count` / `current_agent_step` | int / Optional[int] |

**`metadata` is MERGED, not replaced** (`merge_run_metadata`, same module). LangGraph
replaces a key whose TypedDict declares no reducer, so a node returning a fresh
`RunMetadata(...)` **would** drop everything the run carried — `llm_resolution` first among
them, which would leave the failure gate unable to name the offender on the node path. The reducer
reads the update's NAMED fields only and applies two lists: **identity** (`workflow_id`,
`template_id`, `started_at`, `config`, `tags`, `trace_level`, `llm_resolution`) is carried —
a writer that does not name the field keeps the run's value; **verdict** (`status`, `error`,
`completed_at`, `retry_attempts`, `failure_statement`) is replaced — a writer that does not
name the field gets its default, so a later success still clears an earlier failure. Naming a
carried field explicitly (`llm_resolution=None`) clears it.

**RunMetadata**: `workflow_id, template_id, started_at,
completed_at, status ("running"|"paused"|"completed"|"error"|
"cancelled"), error, retry_attempts, config, tags, trace_level,
node_snapshots, llm_resolution, failure_statement`.

## The node failure contract — grades (`error_handling/grades.py`)

Every node catches its own failures, because a monitor must not die on a dead feed. Left
there, that meant nothing reached the RUN: the node said "error" inside the state, the graph
ended normally, and the run was recorded `completed` — no name, no toast. The **grade** is
the missing declaration, and it belongs to the NODE. It answers one question: when this node
fails, is the failure the run's?

| grade | meaning | what the node does |
|---|---|---|
| `tolerant` | resilience IS the purpose (the monitor family) | absorbs; writes NOTHING on the run — its per-item detail stays in `execution_result`, which is data, not a verdict |
| `recoverable` | the failure is absorbed but the run is marked (the default) | `absorb(...)` → `status="error"` + `error` + `failure_statement` on the run's metadata |
| `fatal` | the call IS the node's purpose | `absorb(...)` re-raises → the run takes the existing failed path, which records it, names the offender and fires the toast |

- **Declared on the node**, with `@node_grade("fatal")` — beside the catch that honours it,
  and the decorator returns the same function so graph wiring is unaffected: the four
  provider-test nodes, `plan_node` and `agent_invoke_node` are `fatal`; the eight monitor
  nodes are `tolerant`. `grade_for_kind` supplies the family default (`monitor` → tolerant,
  everything else → recoverable).
- **`absorb(node, state, error, *, error_text=None)`** is the one call for the absorbing
  grades and the raise. Fatal nodes call it with no assignment (it never returns); a
  recoverable node splats what it returns: `RunMetadata(..., **verdict)`.
- **The per-item families keep their own `_error_state`** (file_clerk, context_indexer,
  boss_agent): it marks the run `status="error"`, which IS the recoverable behaviour, so they
  need no `absorb` call. Grade the NODE; never infer it — a monitor graded fatal starts
  failing runs on a feed, a fatal node graded tolerant records a failed run as clean.
- `run_failure_statement` still gates naming: the statement is the sentence only when the
  exception came from the provider layer, otherwise the run is marked and nobody is fingered.
- **The frame writes the failed run's state** (`_failure_state` in `workflows/api/workflow_router.py`):
  a fatal node raises instead of returning an error state, so the frame supplies the metadata verdict
  AND the `execution_result.error_details.message` shape the run detail reads — one shape for both
  failure paths, so a fatal failure's detail is not poorer than the node path it replaced.
- Pinned by `backend/tests/workflows/test_node_grades.py` (13 tests; 5 fail when the
  declarations are ignored) and, on the capability side,
  `backend/tests/unit/test_workflow_llm_capability.py` (the planner's failure, the run-level
  sentence it produces, and the state shape the frame writes).

## The record of a degraded run

A run whose node absorbed a failure is `completed` **and** `degraded` — two axes, never one word.

- **The verdict** is read by the frame after a "successful" graph (`_run_verdict`,
  `workflows/api/workflow_router.py`), keyed on the final state's `metadata.status` — the node's
  own declaration — and **never** on `execution_result.error`, which the batch families fill with
  per-item errors (keying on it marks healthy batch runs degraded). The state is read from the
  CHECKPOINT, because the debug trace level returns a `RetryResult` rather than the state; a read
  that fails answers "no verdict" rather than guessing.
- **The row** gains no column: `status` stays `completed`, the message goes to `error_message`
  (the statement when one rendered, else the node's own error), and `degraded` is written into the
  row's `metadata` JSON. `list_executions` lifts the flag out for a reader, so no consumer parses
  JSON, and a row recorded before the flag existed reads as not degraded.
- **The state is corrected** (`_mark_run_degraded`): the node had left `status="error"` in it, so a
  degraded run would have read `error` on `/status` (and shown the run panel) while the list showed
  `completed` — the same disagreement in the other direction. The frame writes the OUTCOME back
  (`status="completed"`, `degraded=True`) and keeps `error`/`failure_statement` as the evidence. A
  copy, never a constructor.
- **`/status` serves `degraded`** beside `failure_statement`, so the detail and the row agree.
- **The toast** (`_announce_run_degraded`) fires whether or not the run named anybody: the run
  finished, and it is worse for it — an unattended run is exactly where nobody watches a panel.
- **The UI** shows the second axis BESIDE the status badge (a `degraded` chip with its tip), never
  folded into the status word: the Execution page's row and the Automation page's history.
- Pinned by `backend/tests/workflows/test_degraded_runs.py` (14 tests; the state-agreement test
  fails when the frame stops correcting the state).

## Run retention — the windows are CONFIG (`workflows/retention.py`)

Runs accumulate in three places at once: the identity ROW, the debug SNAPSHOTS inside its metadata,
and the checkpoint THREAD it owns. Measured before any of it was reclaimable: **4.85 MB** of
snapshots per list request (~95 KB a row, 213 KB on the heavier families) and **53 threads nothing
could delete**. A 5-minute monitor is 288 runs a day — ~28 MB/day of snapshots and ~4.3 MB/day of
threads.

**The policy is data, not code.** `RetentionPolicy` declares the shape and ONE default set
(`enabled: false, snapshot_days: 7, run_days: 90, abandoned_hours: 24,
schedule_hour: 3`); the effective policy is resolved from `user_settings.settings["workflow_retention"]`
field by field, so a stale, partial or hostile section falls back to the defaults instead of
loosening a window. `GET/PUT /workflows/retention` reads and validates it, and returns the DEFAULTS
alongside — a surface showing a number must be able to say whether it is the shipped default.

- **Three clocks, because the three things decay differently.** Snapshots go first (days — they are
  the weight and their value is recent); the row and its thread live months.
- **A preview is the default.** `POST /workflows/retention/prune?dry_run=true` measures the same
  counts and bytes the act would and changes nothing; `dry_run=false` is a person's decision and
  runs regardless of `enabled`, which governs only the SCHEDULED prune (a fresh install prunes
  nothing on its own — the trigger ruling). **An apply must be DECIDED, not merely requested**:
  `confirm=true` is required, and the endpoint's own check puts every way of not saying it on the
  same 400 — the flag is not a gate (any caller can send it), it is the difference between a
  request that decided and one that arrived.
- **The surface is the Settings page's Data tab** ([[atlas/ui/components/features/workflows/RetentionCard|RetentionCard]]):
  the five numbers, the store's own readout (rows, snapshot MB, oldest/newest), a Preview, and a
  Prune behind a confirm dialog that names what dies. Nothing about the policy is compiled into the
  UI — the card reads and writes the settings the maintenance job already resolves.
- **ORDER: rows, then threads.** A thread left without a row is invisible; a row left without its
  thread is a lie the UI shows (`/status` 404s for a run the list still lists — measured on two rows
  before this existed).
- **Stuck runs get a name.** A row still `started` past `abandoned_hours` becomes `abandoned` — a
  truthful status update, not a deletion, so it does not wait for `enabled`; the app reconciles them
  at boot. `completed_at` stays NULL: the run's end is unknown.
- **The list does not ship the snapshots** (`json_remove(metadata, '$.node_snapshots')`, guarded by
  `json_valid`): the row keeps them in the database, the payload drops from megabytes to kilobytes.
- **The job is hourly and self-gating** (`add_maintenance_job`, registered at startup): it reads the
  policy each time and prunes only at `schedule_hour` when `enabled`, so a settings change needs no
  restart. A maintenance job never fires a workflow and records nothing in the run history.
- Pinned by `backend/tests/workflows/test_retention.py` (each test on its own database file built
  from the live table's DDL; the preview test fails if the preview acts).

## Observability — where a run's traces go

Optional and keyed: with no keys, every tracing call is a no-op and nothing leaves the
machine. When it is on there is **one trace per run**, its id **derived** from the run's own id
(`run_trace_id(workflow_id)` → the first 32 hex characters of the hash) — so the run's row, its node
spans and `GET /workflows/{workflow_id}/debug/trace` name the same trace without any of the three
looking it up. A retry reuses that id: a retried run is the same run, and its attempts belong on one
trace.

The graph is linked by the callback handler (built with its public key — a keyless one drops every
span in a multi-client process) through a **trace context**; the trace's session, name and tags ride
the run config's reserved `langfuse_*` metadata keys, because the installed SDK has no trace object to
hang them on. A **node is a span**; an **LLM call under a graph is a generation**, which the LangChain
instrumentation supplies on its own.

The credentials are declared settings (`langfuse_public_key` / `_secret_key` / `_host` /
`_tracing_enabled`, read from `.env`), and the adapter resolves them from Settings before the
environment: pydantic's `env_file` never reaches `os.environ`, while the SDK reads `os.environ`, so a
`.env`-only key would otherwise reach nothing. Detail:
[[dev-notes/tracing/langfuse|Langfuse Observability]].

**Two senses of "trace" that a reader must not collapse:** the *service* traces above, and
`trace_level` — the run's own capture mode, which records per-node state snapshots into the row's
metadata and changes nothing about the graph or about what is sent.
