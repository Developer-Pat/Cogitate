# Provider surfaces — the verified map

Everything below was verified live through the HTTP surface (backend
healthy, `GET /api/v1/health` 200) during roster-wide provider-health
surveys. Supports the SKILL.md method.

## Two provider stores (don't confuse them)

1. **Catalog (informational/UI)**: `GET /api/v1/providers` (`?all=true`,
   `?search=`) → name-keyed rows `{id:"ollama", name, type:
   local|cloud, base_url, configured}`. Observed: ollama, openai,
   anthropic, openrouter, deepseek. Does NOT list the `llama` row —
   absence here is cosmetic, not proof of absence.
2. **Managed config store (the real rows agents reference)**:
   `GET /api/v1/providers/config?include_inactive=true` →
   `{providers, total}`; each row `{id, name, display_name,
   provider_type, base_url, is_active, priority, is_default,
   config:{default_model,...}, has_api_key}`. Observed ids: ollama(1)/
   openrouter(2)/deepseek(3)/groq(4)/ollama_cloud(5)/llama(6). Agents'
   `provider` field = row NAME string. CRUD:
   `POST /api/v1/providers/config` (ProviderConfigCreate: name +
   provider_type required; base_url/api_key/is_active/priority/config
   optional), GET/PUT/DELETE `/config/{provider_id}`; a legacy twin
   surface exists under `/api/v1/providers/managed...`.
   `is_default` is frequently ABSENT/false on every row — read it, do
   not assume a default provider exists.

## Where a request's provider comes from (the code path)

Chat stream (`api/v1/chat/router.py`, `generate_stream`):

1. `model = agent.model`, `provider_name = agent.provider`.
2. `_litellm_model_name(provider_name, model)`
   (`api/v1/chat/context.py`) applies the prefix remap — `ollama` and
   `ollama_cloud` → `ollama_chat/<model>`, `llama` → `openai/<model>`
   via the alias map, everything else passthrough `provider/model`.
3. The `Provider` row is looked up BY NAME and `is_active` (READ ONLY):
   `base_url` → `api_base`; the key comes from
   `env_key_store.get_key(provider_name)` (i.e. `.env`), never the DB.
4. `build_llm_request()` assembles the kwargs. It adds `api_base`,
   `api_key`, and — the keyless local case — the dummy
   `api_key="local-llama"` when a base_url is present with no key; it
   also attaches `extra_headers["Authorization"]` when the base_url
   contains `ollama.com` (the `ollama_chat` handler adds no Bearer).

Deep pass / pipeline: `services/cognitive_pipeline/executor.py::
LiteLLMExecutor` builds `agent.provider/agent.model`, applies
`litellm_model()` per attempt, and passes `api_base` + the dummy key
for aliased local providers; cloud keys reach LiteLLM by env var.

Other surfaces with their OWN client construction (a change to the
chat path does not reach them): `domain/providers/llm_factory.py`
(LangChain `ChatOllama`/`ChatOpenAI`/`ChatAnthropic` chosen by
`provider_type`, used by workflow nodes and `get_default_llm()`), and
the raw httpx clients `openrouter_client` / `deepseek_client` /
`groq_client` (completion + title services).

## Health: tracked registry vs LIVE probe (the headline finding)

- `GET /api/v1/providers/health` → per-name tracked registry
  `{healthy, failure_count, last_failure, rate_limit}`, listing ONLY
  the providers `POST /providers/complete` has recorded an outcome
  for (changed 2026-11-22; it used to iterate the static
  supported-provider registry and report openai/anthropic
  `healthy:true` with no config or key). Nothing calling
  `/providers/complete` ⇒ `{"providers": {}}` — an absent name is
  UNKNOWN, not up. A failed `POST /{id}/test` and a failed real agent
  run both leave it untouched (they never pass through that
  endpoint), so it is **not a liveness source** either way.
- `POST /api/v1/providers/config/{int_id}/test` (NO body) → the LIVE
  probe: `{status: connected|unreachable|not_configured|error, message,
  latency_ms, models_available, state, checked_at}`. **The trustworthy
  check.** Connection-refused returns in ~30 ms. It re-probes and
  refreshes the reading every other surface reads.
- The slug form `POST /api/v1/providers/{name}/test` (the catalog slug,
  e.g. `/providers/ollama/test`) answers from the SAME read, but it maps
  the slug to the provider ROW of that name: a slug with no row answers
  `unknown_provider` (`openai` and `anthropic` have no row here).
- Agent-level health: each row of `GET /api/v1/agents` carries
  `health{status, consecutive_failures, last_error, last_failure_at,
  failures_7d}` — VERIFIED: a real failed agent run (provider down)
  left the agent at `ok / 0 failures`. Same default-green registry
  pattern; absence of recorded failures ≠ liveness.
- **The CURRENT question** on the same agent rows:
  `service_availability{state, available, reason, checked_at, provider,
  model}` — "can this agent run RIGHT NOW?". `available: false` = its
  declared service is down and it has no usable fallback; `null` = not
  checked (never `false`). Use this for down-now diagnosis; `health` is
  the history.
- Backend: `GET /api/v1/health` (healthy), `/api/v1/health/comprehensive`
  (path audit), `/api/v1/multi-agent/health` (db + templates).
- `GET /api/v1/providers/local/occupancy` → `{daemons: [{provider_id,
  name, display_name, provider_type, base_url, state,
  loaded_models}], running, generated_at}` — state classes: `healthy` /
  `down-by-occupancy` (another daemon serves; a swap-away, not an
  incident) / `down` (ownerless). Probes: ollama `/api/tags` + `/api/ps`;
  openai-compat `/v1/models` via a base+path join that DEDUPES a
  trailing `/v1` base root (the doubled `/v1/v1/models` bug read the
  live llama daemon as down; tests key on real URLs).

## The llama (llama.cpp / Bonsai-27B) wiring

- Managed row id=6: name `llama`, provider_type `openai`, base_url
  `http://127.0.0.1:8080/v1`, is_active, priority 99.
- The ONE map: `backend/app/domain/providers/litellm_aliases.py`:
  `LITELLM_PROVIDER_ALIASES = {ollama_cloud: ("openai",
  "https://ollama.com/v1"), llama: ("openai",
  "http://127.0.0.1:8080/v1")}`; `litellm_model(provider, model)` →
  `(f"{prefix}/{model}", api_base)`. litellm has no native 'llama'
  prefix — without the alias the raw string dies with 'LLM Provider
  NOT provided'.
- Consumers (all alias-aware): LiteLLMExecutor
  (`services/cognitive_pipeline/executor.py`) — builds
  `model=openai/<model>`, sets api_base, and forces a NON-EMPTY
  `api_key="local-llama"` (keyless local servers error 'Missing
  credentials' otherwise); chat stream path
  (`api/v1/chat/context.py` → `build_llm_request`, same dummy key);
  completion_service + title service.
- llama.cpp server: launched by `~/llama-models/bonsai-server.sh` →
  `~/llama.cpp/build/bin/llama-server -m
  ~/llama-models/Bonsai-27B-Q1_0.gguf --mmproj … --port 8080 --host
  127.0.0.1`. Readiness: `GET 127.0.0.1:8080/health` → ok; `/v1/models`
  lists the model id as the FULL gguf path with no short alias — use
  that full path as the model string.
- GPU contention is REAL and pre-documented (`title/services.py` OOM
  scar): Bonsai + ollama must not run together. USER POLICY: ollama
  :11434 stays DOWN while llama.cpp runs — deliberate, NOT an incident;
  never restart it unprompted.

## Agent-scoped completion tests (the throwaway-session pattern)

- `POST /api/v1/agent-chat/session` `{agent_id, title}` → `{id,...}`
  HTTP 201 (the id is the session handle; SendMessageRequest requires
  session_id + message; CreateSessionRequest requires agent_id).
- `POST /api/v1/agent-chat/message` `{session_id, message}` → HTTP
  200 EVEN on provider failure: `response:""` + `error` field with
  the full trace; the trace's executor section names the failing
  stage. Down-provider (connection refused) failure returns in ~0.23
  s (litellm retried 3x internally) — no hang, no crash, and the
  request-timeout / process-exit alarms do NOT fire on fast refusal.
- Cleanup: `DELETE /api/v1/agent-chat/session/{id}` → 204. Always
  use a throwaway session for provider tests, never the user's live
  sessions.

## Roster read (agents → providers)

`GET /api/v1/agents` rows carry name/provider/model/health/
preferred_providers/fallback_enabled/llm_spec; `provider` is a config
row NAME string. THE ROSTER DRIFTS — re-read it every run and never
cite an older snapshot (agents get repointed, renamed and retired
constantly; `is_default` can also change between runs). Durable facts:

- The user's live chat agent: `GET /api/v1/external-agent/model` →
  `{model, provider, base_url, reasoning_effort, vision_model}` —
  read it to know what the chat currently runs; never test against it.
- A roster agent pointed at a stealth/cloaked OpenRouter id is
  temporary by nature — expect the row to be repointed.
- No roster agent references `llama`: the llama.cpp path is wired but
  uncalled, so end-to-end use needs a caller.
- The curated list is a separate human-owned table; its row count and
  provider mix are read live (`GET /api/v1/curated-models`), never
  quoted from a snapshot.
