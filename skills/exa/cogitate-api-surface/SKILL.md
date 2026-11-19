---
name: cogitate-api-surface
description: "The Cogitate HTTP API surface — the endpoints and payload shapes for agents, workflows, triggers, products, and tools. Use BEFORE exploring files: the API is the fastest path to the system's capabilities."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, api, endpoints, atlas]
---

# Cogitate API Surface

Base: `http://localhost:8000/api/v1`. The API is the extension
point of the system — consult it FIRST instead of reading source
files (avoids the explore-everything trap).

## Workflows

| Purpose | Route |
|---|---|
| List templates | `GET /workflows/templates?category=&tags=&limit=&offset=` |
| Get template | `GET /workflows/templates/{id}` |
| Create/update/delete | `POST` / `PUT` / `DELETE /workflows/templates[/{id}]` |
| Validate | `POST /workflows/templates/validate` |
| Execute | `POST /workflows/execute` — `{template_id, inputs}` |
| Execution status/history | `GET /workflows/{workflow_id}/status` · `/{id}/history` |

## Triggers (base: /triggers)

| Purpose | Route |
|---|---|
| List | `GET /triggers?include_inactive=true` |
| Get one | `GET /triggers/{trigger_id}` |
| Update schedule | `PUT /triggers/{trigger_id}` — `{"config": {"cron": "<5-field cron>", "timezone": "UTC"}}` |
| Delete | `DELETE /triggers/{trigger_id}` |

## Agents

`GET /agents` · `POST /agents` · `PUT /agents/{id}` ·
`DELETE /agents/{id}` (soft-delete + archive, recoverable).
`POST /agents` requires `{name, provider, model}`; depth is NOT a
direct field — set `cognitive_profile_id` (quick-response/conversational
= shallow; research-pro/research-std/code-gen = deep; balanced-chat/
system-admin = balanced; see `GET /cognitive-profiles`). ARM card at
`GET /agents/{id}/card` reports `arm.depth`. `POST /agents/select`
filters by `depth: deep|shallow|balanced` (among others).

## Provider completion (the connectivity test)

`POST /providers/complete` — `{provider, model, messages:[{role,
content}]}`; `provider` defaults ollama, `messages`+`model` required.
Returns `{content, model, provider, usage, response_time_ms, success,
error_message}`. Use this to exercise a model through its provider path
(an actual completion, not a config read).

## Products

`GET /workflows/products` · `POST /workflows/products/{basename}`
(regenerate) · `DELETE /workflows/products/{basename}` ·
`POST /workflows/monitors/reset` (clear a monitor's dedup
checkpoint — body `{template_id}`).

## Tools

`GET /tools` — the registry (capability, access_tier, grants).

## Knowledge (THE EXPERTISE LAYER — added 2026-08-22)

THREE surfaces for the system's accumulated knowledge — use them
BEFORE relying on your training. They are the wiki + RAG index +
topology graph, reachable over HTTP:

### Wiki search
`GET /wiki/search?q=<query>` — scans the wiki's markdown (title +
content, frontmatter-aware; title hits weigh 3x). Returns
`{results: [{path, title, score, snippet}], count}` — top 10.
THEN fetch the page: `GET /wiki/{path}` (the path from a result).
The wiki is the human-curated documentation — cite it.

### RAG search (the semantic index)
`POST /rag/search` — body `{"query": "...", "top_k": 5}`. Embeds
the query + ANN-searches the doc_chunks index (506 docs / 3527
chunks). Returns `{hits: [{source, heading, score, snippet}]}`.
Use for SEMANTIC lookups — "what do the docs say about X" — when
you don't know the exact page.

### Topology graph
`GET /knowledge/graph?entity=<name>` — the entity's neighbors/
edges (the derived FK walk + the wiki link graph). Entity ids are
SLUGS (e.g. `agent-hello`, not table names). Returns `{entity:
{id, kind, name, table}, edges: [{kind, direction, to, to_kind}]}`.
Use to TRACE data flow / relationships — "what fires X", "what
does X depend on".

### The pattern
1. Search the wiki for the human docs (the citation source).
2. RAG-search for the semantic content (the chunks).
3. Graph-query for the topology (the relationships).
A good answer cites the wiki page + the RAG source + the graph
edges — the verified, three-legged claim.

## Providers & Curated Models (added 2026-08-21, Ox Alpha run)

TWO separate surfaces — the curated list is HUMAN-OWNED and
deliberately NOT fed by provider configs or discovery.

### Curated list (`/curated-models`)
- `GET /curated-models?provider=<name>&include_inactive=` · `GET /{curated_id}`
- `POST /curated-models` — body: `{provider, model_id, model_name}`
  (required) + optional `category, description, context_length, is_free,
  featured, sort_order`. Categories: budget, code, featured, performance,
  reasoning, vision.
- `PUT` / `DELETE /{curated_id}` (PUT fields all optional, incl. is_active).
- NO fix-mode guard on this surface; writes go straight through.
- `verified` is ALWAYS `false` on create — it is EARNED by discovery:
  a live cache write (below) marks matching curated model_ids verified.
- Uniqueness enforced on (provider_id, model_id) → 400 on dupes.

### Provider configs (`/providers`)
- `GET /providers` (slug ids like `openrouter`) · `GET /providers/config`
  and `/providers/managed` (NUMERIC ids — browse takes these).
- CRUD: `/providers/config[/{id}]`, `/providers/managed[/{id}]`; keys via
  `/providers/managed/{id}/key` and `/api-key`; test via
  `/providers/{id}/test` + `/providers/complete`.
- The slug TEST route maps the slug to the provider ROW of that name and
  answers from the app's ONE availability read — so a slug with NO row
  behind it answers `unknown_provider`. The `GET /providers` list is UI
  copy, not inventory (`openai` and `anthropic` have no row here). Prefer
  `POST /providers/config/{int_id}/test`: same answer, and it REFRESHES
  the reading every other surface shows. Either form returns
  `{status: connected|unreachable|not_configured|error, message,
  latency_ms, models_available, state, checked_at}`.

### Machine discovery (`/providers/{id}/models/*`) — numeric id!
- `GET /providers/{id}/models/browse` — the live catalog (cached ~7 days).
  Filters: `search` (name/id/description), `capabilities`, `min_context`,
  `max_context`, `free_only`, `max_price_prompt`, `max_price_completion`;
  paging `page`/`page_size` (max 100); sort `sort_by`/`sort_order`.
  Each row is enriched with `curated: {is_curated, featured, verified}`.
- `GET /providers/{id}/models/{model_id}` — looks up the CACHED list only;
  a model newer than the cache returns `404 Model ... not found` even
  though it's live on the provider (see refresh). The model_id path
  segment must be URL-encoded — slashes as `%2F`, colons as `%3A`
  (e.g. `nvidia%2Fnemotron-3-ultra-550b-a55b%3Afree`).
- `GET /providers/{id}/models/capabilities` — filter facets.

### Refresh / verified-earning
- `GET /providers/managed/{id}/models?force_refresh=true` — bypasses cache,
  fetches the live provider list, writes the cache, and calls
  `mark_verified_for_models` (curated entries for fetched model_ids flip
  `verified=True`). Do this AFTER creating a curated entry for a model
  that is newer than the cache — it both earns verified and makes the
  model discoverable via browse.
- Sync schedule: `/providers/sync-schedule/{id}` (GET/DELETE/POST, run).

## Navigating the app (the user's screen)

`POST /agent-chat/ui-navigate` — body `{"route": "<path>", "replace": false}`.
Broadcasts a `navigation_request`; the frontend moves the user's view. Returns
immediately — the navigation happens asynchronously, so you cannot confirm it
by the response alone (say "opened", not "you are looking at").

Use it when the answer to a task IS a place: you are working on something and
the user should see the page it concerns. **Do not navigate as a reflex** — a
page move is the user's context changing under them, so it belongs to the ask,
not to your narration of it.

### This is HTTP on purpose — the registry tool is NOT reachable

`open-page` exists in the registry and is correct there, but you **cannot call
it**. The ACP client spawns you with `mcpServers: []`, and its contract is that
the runtime, tools, memory and streaming are all Hermes' — a `tool_call` frame
carries your OWN tools, never the host's registry. Same wall the knowledge
layer hit: `search-knowledge` and `graph-query` are HTTP surfaces for you, not
tools you invoke.

So: the host's capabilities reach you as **endpoints you curl**, never as
registry entries.

### The route must be real

Routes come from the app's own table. If you are unsure of a path, the safest
answer tells the user where to look rather than opening a guess — the frontend
validates and will refuse an unknown route, and a refused jump reads as a
broken assistant.

## Rules

- The cron is ALWAYS 5 fields (minute hour day month weekday).
- Write operations require fix-mode; the API rejects without it.
- Products are keyed by `created_at` (unique per entry) — not by
  basename alone (the old collision bug class).


## Agent tool provisioning (2026-08-22 — THE GRANT MODEL)

When you provision an agent, the TOOL SURFACE is tiered, not a
free list:

- **GRAS tools (read-only: file-info read, search-knowledge,
  graph-query, sqlite-query...) are default-ON** for every agent —
  no grant row needed. An explicit `agent_tools` row with
  is_enabled=0 EXCLUDES one.
- **KEYED tools (writes: file-manager write, run-post...) need an
  `agent_tools` link with is_enabled=1** (the grant, enforced at
  execution). file-manager is keyed — its `write` operation is the
  deliverable path (the agent writes its manifest to its own
  workspace: agents/<name>/out/).
- **The workspace is the sandbox**: the agent writes INSIDE
  agents/<name>/ (its own home: out/, inbox/, scratch/) — NOT the
  repo tree, NOT Exa's .exa-workspace. The base_path config must
  point at the agent's home.
- **OPEN DESIGN QUESTION (the user, 2026-08-22)**: per-agent
  grants (current) vs per-workflow/task grants. The lean: per-agent
  as the FLOOR (role tools), per-task as the OVERRIDE (job
  extras scoped to the execution).


## Workflow-execution gotchas (2026-08-23 — the deep-agent container)

When you dispatch a deep-agent job via POST /workflows/execute
(template deep-agent-job), these are the traps (each cost a
debugging cycle):

1. **The graph resolution is tiered**: legacy per-template table ->
   the KIND registry (kind_id -> factory) -> default simple graph.
   A NEW template silently falls to the DEFAULT SIMPLE graph —
   it 'completes' in 0.05s without invoking the agent (the
   silent-failure class: looks done, did nothing). Verify a
   template resolves to the intended graph before trusting a run.
   The agent-task kind resolves via create_agent_task_graph (the
   canonical registry path — NOT the legacy table).
2. **The task prompt goes in BOTH `initial_message` AND
   `inputs.{user_input_key}`** — the agent node reads
   inputs.task (the template's user_input_key), defaulting to
   'Hello' if absent. initial_message alone = the agent greets you.
3. **KEYED tools (file-manager write) need the run-scoped grant**:
   pass `tool_grants: [{"tool_slug": "file-manager"}]` in the
   execute request — issued at dispatch, revoked at run end. Without
   it: 'requires a grant to execute (keyed tier: file-write)'.
4. **file-manager needs the base_path in the agent_tools CONFIG**
   (the agent's workspace: agents/<name>/ — the sandbox root).
   The config comes from the agent_tools row; a missing base_path
   = 'base_path is required' even with the grant.
5. **The agent's deliverable home is ITS workspace**
   (agents/<name>/out/), NOT .exa-workspace — the ownership
   correction from the deep-agent study.
6. **The run-scoped grant's tool_config resolution** — a known
   check point: verify the config flows with the run grant (the
   agent link config may not merge with the run scope).
