---
name: cogitate-provider-health
description: "Cogitate provider architecture, wiring and health — the three layers and three client adapters, the model-string remap (ollama → ollama_chat), how to switch providers or point an agent at provider Y, the tracked-vs-live discipline (GET /providers/health is a default-green registry that never records failures; POST /providers/config/{id}/test is the live probe — the slug form needs a provider row of that name), the two provider stores, and the llama/llama.cpp wiring. Use for provider questions, switching/adding providers, health surveys and down-provider diagnosis."
version: 1.0.0
author: Exa (agent-created)
tags: [cogitate, providers, health, survey, llama]
---

# Cogitate Provider Health & Wiring

Complements [[provider-orientation]] (the orientation charter) and
[[verify-backend-health]] (backend scope). This skill carries the
VERIFIED survey discipline and the discovered surface map — the
details that orientation said to discover and document.

## The core discipline: tracked state ≠ liveness (verified 2026-09-08)

- `GET /api/v1/providers/health` is a TRACKED registry. It defaults
  to `healthy:true` (even for UNCONFIGURED providers) and NEVER
  records failures — verified twice: a failed live test AND a failed
  real agent run both left the provider at `healthy:true,
  failure_count:0`. Never cite it as liveness evidence.
- Agent-level health (each row of `GET /api/v1/agents`:
  `health{status, consecutive_failures, last_error, ...}`) has the
  SAME default-green pattern — a real failed agent run left the agent
  untouched. Absence of recorded failures ≠ liveness.
- **The CURRENT question (2026-10-05):** each agent row also carries
  `service_availability{state, available, reason, checked_at, provider,
  model}` — *"can this agent run RIGHT NOW?"*, built from the resolver +
  the app's one availability read. `available: false` means its declared
  service is down AND it has no fallback it may use. `available` is
  `null` (never `false`) when nothing was checked. Read THIS for
  "is it down now"; the `health` block answers "has it been failing
  lately" and is history.
- The live probe: `POST /api/v1/providers/config/{int_id}/test` (NO
  body) → `{status: connected|unreachable|not_configured|error, message,
  latency_ms, models_available, state, checked_at}`. Connection-refused
  returns in ~30 ms. It re-probes and REFRESHES the reading the
  capability page and the agent badges read. THIS is the trustworthy
  check — every health report row should cite it.
- The slug form `POST /api/v1/providers/{name}/test` still works but now
  maps the slug to the provider ROW of that name: with no row behind it
  it answers `unknown_provider` instead of probing a hardcoded address
  (`openai` and `anthropic` have no row here). Prefer the int-id route.

## The survey recipe (roster → providers → health → table)

1. **Roster**: `GET /api/v1/agents` — each row carries
   name/provider/model/health/preferred_providers/fallback_enabled.
   Agents reference providers by NAME string.
2. **Group by provider**; check the managed store
   (`GET /api/v1/providers/config?include_inactive=true`, int-id
   rows) for the config truth.
3. **Live-probe each distinct provider** via
   `/api/v1/providers/config/{int_id}/test` (per-call timeout caps) —
   and read each agent's `service_availability` for "can it run now".
   Cross-check a suspicious verdict directly (e.g. curl the base_url) —
   independent evidence beats one source.
4. **Report claimed vs verified per row** (report-verified-state
   discipline): tracked state, live probe result, direct check.
   A tracked/live MISMATCH is a finding, not an embarrassment.

## Two provider stores (don't confuse them)

1. CATALOG: `GET /api/v1/providers` (`?all=true`) — name-keyed,
   informational/UI. Does NOT list every real row (the `llama` row
   is absent here) — absence is cosmetic.
2. MANAGED config rows (what agents reference): `GET
   /api/v1/providers/config` — `{providers, total}`, int ids,
   `provider_type`, `base_url`, `is_default`,
   `config.default_model`. CRUD via `POST /api/v1/providers/config`
   (ProviderConfigCreate: name + provider_type required).

## The architecture: three layers, three adapters

**Layers** — top is what agents use, bottom is what decides the class:

1. CONFIG ROWS (`providers` table) — the live connection: `name`,
   `provider_type`, `base_url`, `is_active`, `priority`, `is_default`,
   `config.default_model`. Agents reference rows by NAME string; a name
   with no ACTIVE row resolves no credentials and the call fails.
2. CATALOG (`GET /providers`) — a hardcoded display list in
   `api/v1/providers/router.py`; UI copy, never inventory (no `llama`).
3. PROVIDER CLASS (`domain/providers/provider_classes.py`) — a cloud
   whitelist plus a loopback tiebreaker, so a cloud type pointed at
   127.0.0.1 (`llama`, registered as type `openai`) is LOCAL. Only the
   cloud class requires a key.

**Adapters — one provider, several client paths. A change in one does
NOT reach the others; name the surface before editing or explaining:**

- Chat stream (the user's live chat) + cognitive deep pass → LiteLLM:
  `api/v1/chat/context.py::build_llm_request` (the stream's kwargs come
  from HERE, not the router) and
  `services/cognitive_pipeline/executor.py::LiteLLMExecutor`.
- Workflow nodes + the `get_default_llm()` convenience path →
  LangChain clients, `domain/providers/llm_factory.py`, picked by
  `provider_type`.
- Completion + title services → raw httpx clients
  (`openrouter_client` / `deepseek_client` / `groq_client`).

**The model string is per-adapter, and this is where a switch breaks**
(`chat/context.py::_litellm_model_name`):

- `ollama` → `ollama_chat/<model>` — LiteLLM's plain `ollama` handler is
  function-unsupported: tool calls arrive as inert JSON text and the
  tool loop never runs.
- `ollama_cloud` → `ollama_chat/<model>` PLUS an explicit
  `Authorization` header, because that handler serves the keyless local
  ollama and attaches no Bearer — ollama.com rejects the call without
  it.
- `llama` → `openai/<model>` + api_base via the alias map (see below).
- openrouter / deepseek / groq / openai / anthropic → passthrough
  `provider/model`.

**Model ids do NOT transfer between providers.** OpenRouter ids are
vendor-prefixed (`deepseek/deepseek-v4-flash`, `stealth/<name>`),
DeepSeek ids are bare (`deepseek-v4-flash`), Ollama ids are tags
(`phi4-mini:latest`), llama.cpp's id is the FULL gguf path. An id
copied across providers is the usual cause of a silent blank reply.

**Keys live in `.env` only** (`domain/providers/env_key_store.py`, one
var per provider_type; the DB has no key column since the
`api_key_encrypted` drop). A row's `has_api_key` means "the .env line
exists" and nothing more.

## Switching providers — the operative switch is the AGENT

Three levels; only the first changes behaviour:

1. AGENT (the real switch): `agent.provider` + `agent.model`, set on the
   agent profile. Failover is per-agent: `fallback_enabled` +
   `preferred_providers` (default chain openrouter → deepseek → ollama,
   primary skipped), and a failover publishes a visible "fell back"
   warning — falling back is never silent.
2. CONNECTION CONFIG: add/edit the row (`/providers/config` CRUD;
   `/providers/cloud` and `/providers/local` in the UI). Adding a row
   does NOT make its models selectable in the agent form — that is the
   curated list, a separate human-owned table.
3. DEFAULT: `is_default` on a row, used only by `get_default_llm()`.
   VERIFY it is set before claiming a default exists — rows commonly
   carry none.

## The llama (llama.cpp / Bonsai-27B) wiring — built 2026-09-01

FULLY wired; no registration needed. Managed row id=6 (name `llama`,
provider_type `openai`, base_url `http://127.0.0.1:8080/v1`) + the
shared map `backend/app/domain/providers/litellm_aliases.py`
(`llama` → openai adapter + api_base; keyless local servers need the
NON-EMPTY `api_key="local-llama"` or litellm errors 'Missing
credentials'). Both call paths apply it (LiteLLMExecutor +
`chat/context.py build_llm_request`). llama.cpp model id = the FULL
gguf path (no short alias). As of 2026-09-08 no roster agent
references `llama` — a caller is the missing piece.

**GPU contention**: Bonsai + ollama OOM together (scar in
`title/services.py`). USER POLICY: ollama :11434 stays DOWN while
llama.cpp runs — deliberate, NOT an incident; never restart it
unprompted.

Daemon launch + readiness facts (bonsai-server.sh, the health
endpoints) live in the reference map's llama section — consult it
before touching the process.

## The LOCAL occupancy endpoint (the A3 live state)

`GET /api/v1/providers/local/occupancy` → `{daemons: [{name,
state, loaded_models, ...}], running: [...]}` — the LOCAL daemon
truth, per class: `healthy` (answers), `down-by-occupancy` (silent
because ANOTHER daemon serves — a swap-away choice, NOT alert
noise), `down` (silent and ownerless). `running` = the serving
daemons; `loaded_models` = what occupies VRAM now. This is the
authoritative local-state surface (the occupancy UI + the swap
flow both read it); the tracked `/providers/health` registry is
NOT — same default-green caveat as ever.

**The probe-URL pitfall (verified 2026-09-09, live):** the service
probes `base_url + path` with a /v1 dedupe, because managed local
rows carry the litellm-style trailing root (`llama` =
`http://127.0.0.1:8080/v1`). When the occupancy says `down`, curl
the EXACT URL it probes before acting — a healthy llama.cpp once
read as `down` purely from a doubled `/v1/v1/models` join.

## Agent-scoped test pattern (throwaway session)

- `POST /api/v1/agent-chat/session` `{agent_id, title}` → `{id}` 201
- `POST /api/v1/agent-chat/message` `{session_id, message}` → HTTP
  200 EVEN on provider failure: `response:""` + `error` with the
  full trace; down-provider failures return in ~0.23 s (litellm
  retried 3x) — no hang, alarms don't fire on fast refusal.
- Cleanup: `DELETE /api/v1/agent-chat/session/{id}` → 204. Never use
  the user's live sessions (external-agent is the live chat agent —
  untouchable for tests).

## The MODEL-level test call (lighter than an agent)

`POST /api/v1/chat/completions` with `{model: "<provider>/<model_id>",
messages: [{role, content}], options: {max_tokens: N}}` — an
OpenAI-shaped NON-streaming completion through the backend, which
already holds the provider key. Use it to prove a model ID answers (and
to A/B a budget) with NO agent, session, or cleanup. `options` maps ONLY
temperature / max_tokens / top_p, so no reasoning effort can be sent
from this surface.

A 200 is NOT proof of an answer: read `choices[0].message.content` and
`usage.completion_tokens`. A starved reasoning model returns 200 with
empty content and completion_tokens == the cap — nothing raises, nothing
logs an error, the reply is simply blank.

## Pitfalls

- Reading `/providers/health` (or agent `health`) as liveness.
- Trusting the catalog for what providers exist.
- Restarting ollama to "fix" it (deliberately down).
- Trusting an occupancy/health "down" without curling the exact
  probe URL — managed local base_urls end in /v1; a doubled join
  (/v1/v1/models) read a healthy daemon as down (2026-09-09).
- Long JSON one-liners from the API: save to /tmp, parse with
  python3 (jq is NOT installed on this host).
- Do NOT combine a stdout redirect with curl's `-w` in one command: the
  write-out line lands INSIDE the JSON file and `json.load` dies with
  "Extra data". Use `-o file -w "..."` so body and status line stay
  separate.
- Assuming a row's `config.default_model` is what an agent runs — the
  AGENT's `model` wins; the row default serves only paths that name no
  model.
- Assuming some row carries `is_default` — read the rows and say so
  before promising a default provider.
- Editing or explaining ONE adapter and treating it as the whole
  provider system — the chat stream, the workflow/default path and the
  completion/title path each build their own model string and
  credentials separately.

## References

- `references/provider-surface-map.md` — the full verified map:
  endpoints, payload shapes, roster snapshot, failure-path behavior.
