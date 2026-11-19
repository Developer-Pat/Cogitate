---
title: Langfuse Observability
type: atlas-devnote
category: tracing
order: 4
confidence: high
updated: 2026-10-08
tags: [type/dev-notes, domain/tracing]
---

# Langfuse Observability

Workflow and chat tracing, sent to Langfuse. The whole integration is one seam:
`backend/app/workflows/observability/langfuse_config.py` (`LangfuseManager`).

## The SDK is v4, and it has no trace object

`langfuse==4.6.1`. There is **no `client.trace()`**, no `trace.span()`, no `trace.generation()`:

| what you want | v4 |
|---|---|
| open the trace root | `client.start_as_current_observation(name=…, as_type="span")` (a context manager) or `start_observation(…)` (a handle) |
| a child observation | `observation.start_observation(name=…, as_type=…)`, or an explicit `trace_context={"trace_id": …}` |
| an LLM call | `as_type="generation"` + `model`, `model_parameters`, `usage_details`, `cost_details` |
| terminal values | **`update(output=…, level=…, status_message=…)` then `end()`** — `end()` takes nothing but an end time |
| session / user / trace name | `propagate_attributes(session_id=…, user_id=…, trace_name=…)`, or a run's config metadata (below) |

## The trace id is derivable

`create_trace_id(seed)` is `sha256(seed)[:32]` — the same id the SDK's own
`create_trace_id(seed=…)` produces, computable with **no client, no keys and no
network**. Two named derivations exist so nothing can drift apart:

- `run_trace_id(workflow_id)` — a workflow **run**. The run's node spans, the run
  record and `/debug/trace` all ask this. A retry reuses it: a retried run is the
  same run.
- `chat_trace_id(session_id, turn)` — one chat **turn**.

A falsy seed yields a random id rather than the hash of `""`, which would give
every seedless caller the *same* trace.

## What a trace is

One trace per unit of work: **one per chat turn, one per workflow run**, with the
graph's nodes as spans under the run's trace. The chat turn's root span carries its
session and its outcome (`completed` / `interrupted` / `error`); an abandoned
stream still closes its span.

A run's root is **LangGraph's own graph span**, so its input and output are the run's
STATE — the dict every node reads and writes, not a summary of the work. That is kept
deliberately: the root is the engine's view of the run and the readable io lives on the
node spans. A hand-built root would mean re-curating what the graph already reports,
for a second copy of it.

For a LangGraph run the two halves are given separately:

- `get_langfuse_handler(trace_id=…)` — the handler, linked by **`trace_context`**.
  A handler must be built **with its public key**, or a process holding more than
  one client silently drops every span ("Skipping tracing ... to avoid
  cross-project leakage").
- `with_run_metadata(config, session_id=…, trace_name=…, tags=…)` — the reserved
  `langfuse_*` keys in the run config's `metadata`, which the handler parses and
  applies to the trace and so to every node span.

**The handler rides the run CONFIG, never an `invoke(callbacks=…)` kwarg.** LangGraph's
`invoke`/`stream` declare `**kwargs: Unpack[DeprecatedKwargs]` and read only
`checkpoint_during` from that channel, so a `callbacks=` kwarg is dropped without a
word and the run emits **nothing** — the handler-reaches-the-wire property is pinned by
a test that runs `run_workflow_async` for real, and by the sink.

**Session and user ids must be strings.** The SDK's `propagate_attributes` discards any
other type in silence, and the chat route holds an `int` session id — the adapter
coerces both before handing them over.

## The root marker

Pinning a trace id is done with `trace_context={"trace_id": …}` and no parent. The SDK
then mints a **synthetic parent span id** (`_create_remote_parent_span`) that no span
ever carries, and marks the span `langfuse.internal.as_root = true` — that attribute,
not an empty `parent_span_id`, is what identifies a trace's root on the wire. (The
read API's `isRootObservation` flag does not read it, so a root span can report
`false` there and still be the root.)

## A chat turn's model calls are generations

The chat path is not LangChain, so nothing instruments it for free. The calls are traced at the one
funnel every chat call goes through — `api/v1/chat/llm_utils.acompletion_with_retry` — which wraps
each call in `LangfuseManager.generation(...)`. A turn's trace is therefore its root span with a
`generate-response` **generation** under it, carrying the model, the messages, the assistant's text
and the tokens.

- **Each invocation is its own generation.** A retried call is a *second* observation, and an attempt
  the provider refused is marked `ERROR` with its message — one aggregated generation would hide
  exactly the half of a rate-limit story worth reading.
- **The streamed case spans the consumer's loop.** The funnel returns the provider's iterator
  wrapped: the generation opens when the consumer starts reading and closes when it stops, exhausts,
  or abandons the stream (the client disconnect the route already calls an interrupted turn). The
  chunks themselves are untouched.
- **A call with no open trace is not traced.** `chat_delegate` and the `/completions` passthrough
  call the model outside any turn; a generation there would become a trace of its own, so the adapter
  checks for an open span and does nothing.
- **Streamed usage is asked for, not waited on.** The funnel sets
  `stream_options={"include_usage": true}` on every streamed call (a caller's own value wins).
  Several providers report the tokens on a stream ONLY when asked — measured on llama.cpp and groq,
  documented by OpenAI and DeepSeek — and without it those generations carried the model, the text
  and the latency but **no tokens**, and so no cost. Non-streamed calls carry usage regardless.
- **The cost is the app's own.** The generation carries `cost_details`, computed from the same
  provider catalog (`provider_model_cache`) and the same per-1K arithmetic as the app's own usage
  row, so Langfuse needs **no model definition** for any of it: an OpenRouter id or a local server's
  name is priced the same way, and there is no second copy of the prices to keep in step with the
  catalog. A model whose price nobody publishes (`ollama_cloud`, the local servers) sends **no**
  cost, deliberately — a `0.0` on the trace would read as "this call was free".

## Configuration

| Variable | Meaning |
|---|---|
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | required — tracing is off without them |
| `LANGFUSE_BASE_URL` | the destination. **`LANGFUSE_HOST` is the deprecated alias**, read second. The adapter passes the value to the SDK **explicitly**, so a hosted install must set this — the SDK's own fallback is `cloud.langfuse.com`, and the regional clouds are `us.cloud.langfuse.com` / `eu.cloud.langfuse.com` |
| `LANGFUSE_ENVIRONMENT` | the environment tag (`production` / `staging` / `development`); defaults to `development` here, so a keyed install's traces are separable from production ones. **The SDK's own name for this is `LANGFUSE_TRACING_ENVIRONMENT`, and setting that one does nothing** — the adapter passes `environment=` explicitly (`langfuse_config.py:191`), so the SDK's environment fallback is never consulted |
| `LANGFUSE_TRACING_ENABLED` | the **SDK's own switch**, `"false"` to switch tracing off |

Keys are optional: every verb degrades to a no-op and each catches its own
failure, so a tracing fault never changes a request's outcome. `get_client()` does
**not** call `auth_check()` — that is a network round trip in a getter, and a flaky
link would silently disable tracing.

**`os.environ` already holds the whole `.env`.** litellm calls `load_dotenv()` at import
time and the app imports litellm, so every variable in `.env` is in the environment of
any process that touches the providers layer — which is why the adapter asks `Settings`
**first** and the environment second (a declaration outranks that copy), and why a
diagnostic or test that redirects tracing must clear the whole `LANGFUSE_*` family from
the environment as well as stand in for `Settings`.

## Turning it on and off

Optional and **off by construction**: with no keys every verb is a no-op and nothing leaves the
machine — that is a fresh install's state. With keys present, one switch decides, and it is the SDK's
own name so that the app and the SDK cannot disagree:

| state | keys | `LANGFUSE_TRACING_ENABLED` |
|---|---|---|
| off — the unkeyed default | absent | not consulted |
| **on** | present | unset, or any value but `false` / `0` / `no` |
| off | present | `false` |

With tracing off there is **no client at all**: `get_langfuse_handler()` returns `None`, so a run
config carries no callbacks; `flush()` and `shutdown()` do nothing; `create_trace` yields `None`, so a
caller writes one code path instead of two; and `/api/v1/workflows/{id}/debug/trace` still answers —
with `langfuse_enabled: false`, the derived `trace_id`, and no URL.

**Toggling needs a backend restart, and that is deliberate.** `get_settings()` is `@lru_cache`d, so
an edit to `.env` is invisible to a running process, and the client is built once and cached;
`uvicorn --reload` does not watch `.env`. **The switch is `.env`-only, by decision**: no endpoint, no
UI control, no settings page. Turning tracing on or off is an operator's action, and it belongs with
the keys — which are also an operator's action — rather than on a control a user flips mid-session.

A live switch would be easy and is deliberately not built: `is_enabled()` is asked on every call and
`get_client()` returns `None` when it is false, so mutating the loaded Settings object (which is what
`EnvKeyStore` does for provider keys) would take effect on the very next turn.

## What proves what

Three layers, and none of them substitutes for another:

| layer | what it proves | where |
|---|---|---|
| the call shapes | the app speaks v4's language (names, ids, sessions, node linking), with no keys and no network | `backend/tests/unit/test_langfuse_v4_adapter.py`, on the SDK's in-memory span exporter |
| the wire payload | what the app builds is what **crosses the wire**: the derived trace id on the run's node spans, the chat turn's session, the graph's spans under one root, `get_trace_url` resolving | `scripts/diagnostics/langfuse_sink.py` — an OTLP protobuf sink on loopback (`--serve` to point an install at it, no argument to self-test) |
| the arrival | a real project accepts and renders it | real keys against the project |

**Reads are observations-first, and the legacy trace API is gone for a new project.**
This project's organization was created on the v4 platform, where `GET /api/public/traces*`
answers **410 LEGACY_API_UNAVAILABLE_FOR_NEW_ORGANIZATION**. Read a trace back through

```
GET /api/public/v2/observations?traceId=…&fields=core,basic,trace_context,io,usage,model
```

— the `fields` groups are opt-in, and fields from groups not requested are **absent**,
not `null`. There is no trace-level `input`/`output` in v4 (deprecated): the overall
request and response live on the **root observation**, which is why the chat root is
given the user's message as its input.

The UI link comes from the SDK's `get_trace_url()`, which is not a string builder —
it resolves the project id over the network. It can fail, so `trace_url()` returns
`None` and `/api/v1/workflows/{id}/debug/trace` answers with the derived `trace_id`
alone rather than a 500.

## Known noise

With keys set and the host unreachable, the SDK's exporter prints a full traceback
to stderr from its background thread for every finished span.
