---
title: The Capability System
category: dev-notes
subtopic: API
confidence: high
created: 2026-10-05
updated: 2026-10-05
tags: [type/dev-note, domain/api]
---

# The Capability System

Every service the app calls — the chat model, the title generator, the summarizer, memory extraction,
the workflow steps, speech in and out, the external agent — is chosen by **one resolver**, from
configuration, and reported by **one read-out**. Nothing else in the app decides which service answers.

The system has three moving parts: a **capability** (who is asking), a **ladder** (the order in which
the answer is found), and a **chain** (the services that answer it, and what to try when one fails).

## The three words

| word | what it is | example |
|---|---|---|
| **capability** | the CONSUMER — the part of the app asking for a service. A fixed, seeded vocabulary; a capability is not created by a request. | `chat`, `title`, `workflow-llm`, `summary`, `memory`, `stt`, `tts`, `exa` |
| **service** | the configured endpoint that answers: a provider row, a speech engine, or an external process | the `deepseek` provider row; `edge`; `whisper`; `exa` |
| **model / voice** | the specific thing on that service; optional, and the row's own default applies when it is absent | `deepseek-v4-flash`, `Bonsai-27B-Q1_0.gguf`, `en_US-lessac-medium` |

A capability is not a service and neither is a model. The capability is *who asks*; the service is
*what answers*; the model is *the thing on it*. Keeping them apart is the whole point: a service named
in the database is a decision someone can change and read back, while a service named in the source is
a second answer nobody can see.

## The ladder — how a capability resolves

`resolve(db, "<capability>")` walks these rungs **in this order and stops at the first that answers**.
The answer carries which rung it was (`reason`), because a failure statement can only name the
offending service if the choice was made in one place and that place remembers why.

1. **`disabled`** — checked before every rung, an override included. A capability switched off answers
   with no candidates at all, and a consumer must **refuse** rather than fall through to the default
   row. "Off" is a state, not a suggestion.
2. **`override`** — an explicit `provider/model` supplied by the caller for this one request (the
   title service's model preference rides here). It picks the PRIMARY; the configured chain still
   supplies the backups.
3. **`agent profile`** — the agent's own declaration (`provider`, `model`, `preferred_providers`). It
   applies **only** to the capabilities a live consumer actually passes an agent for — today `chat`
   alone. The read-out takes an optional `agent_id` and applies the rung exactly the same way, so a
   card never shows a chain the capability would not use.
4. **`capability config`** — the capability's own configured chain, in order. If the capability is
   enabled but configures nothing, the ladder continues to the next rung.
5. **`global default`** — the provider row flagged as the default. One row, no chain.
6. **`none`** — nothing resolved. This is REPORTED, never raised: `reason` says `none` and the caller
   decides. It is a different fact from "configured to nothing", which is rung 4 falling through.

What comes back is a **resolution**, not a client: the ordered candidates (primary first, then the
backups), and the reason. Three of the four states a caller must handle are in that answer — resolve,
off, or nothing — and the fourth (the whole chain failed) belongs to the walk below.

## The chain, and what happens when a service fails

A capability's chain is walked by **one shared function**, used by everything that attempts a service:
the primary first, each backup after it, in order. Each failure is logged as it happens, naming the
capability, the service, its model, and **which attempt it was**, so a degraded turn is diagnosable
from the log alone — that requirement is why a backup's failure is logged too, not just the primary's.
The last error is what the caller sees.

Two states a caller can hit and must not confuse:

- **No backup configured** — a chain of one. A failure is the primary's, and a failure statement says
  so rather than blaming a failover that does not exist.
- **The walk is not allowed to fail over** — the agent-level switch that lets a turn fail visibly
  instead of silently walking to another service. The statement the user sees reads the same switch,
  so "no fallback configured" is one fact with one source.

## The kinds, and the three ways a candidate names a service

The ladder is shared; the **kind** decides what the caller receives:

| kind | the caller gets | examples |
|---|---|---|
| `llm` | a provider row and a model → a chat client | `chat`, `title`, `summary`, `memory`, `workflow-llm` |
| `speech` | a speech engine | `stt` → `whisper`, `tts` → `edge` |
| `process` | an external process | `exa` |
| `embedding` | a provider row, a model, and the vector WIDTH the model implies | `embeddings` → the RAG/vector-index family |

An `embedding` capability is the one kind whose last rung is skipped: the ladder's global default row
is the install's **chat** default, so letting it answer "which server runs my embedding model" would
be the app deciding that whatever chat model is default can embed. The kind is what makes an
UNCONFIGURED install legible — it reports (`no embedding model: indexing and search are off`) instead
of resolving to a chat row that reads as configured. The width is derived from the model
(`EMBEDDING_DIMS_BY_MODEL`), because a model and its dims are one fact: `nomic-embed-text` IS 768
wide, and two independent literals let a changed model write the wrong width into an index that
accepts it. The resolution itself is `app/domain/providers/embeddings.py`
(`resolve_embedding_service`); the ruling is `wiki/issues/resolved/embedded-service-literals/embedding-model-and-dims.md`.

A candidate names its service in **exactly one of three forms**, and the form matters because it is
what a write must send back:

1. **`provider_id`** — one provider row (the LLM case).
2. **`require_location`** — a LOCATION CLASS, e.g. `local`. This is configuration for "prefer a local
   service" rather than naming one; it expands to every row of that class, ordered by the provider
   row's own `priority` (which is what that column is for).
3. **`service_name`** — a named service that is not a provider row at all: `piper`, `edge`, `whisper`,
   `exa`.

## How to use it

### See what is configured, and what it resolves to

- **The page:** `/providers/capabilities` — one card per capability: the resolved service, the chain,
  the rung that answered, and whether the service is reachable right now.
- **The API:** `GET /api/v1/providers/capabilities` (all of them) and
  `GET /api/v1/providers/capabilities/{key}` (one). An unknown key is a **404**, not an empty answer.
- **For one agent:** add `?agent_id=<id>` to the list call to see what that agent's turns will use.
- **Availability** rides on every candidate: `available` | `down-by-occupancy` | `down` |
  `unconfigured` | `unknown`, with the reason and when it was read. `available: null` means *never
  checked* — deliberately not `false`, so a surface can say "not checked yet" instead of calling an
  unprobed service broken.

### Change a capability's chain

`PUT /api/v1/providers/capabilities/{key}` replaces the **whole ordered chain** as a unit. A
candidate's position in the list is its ordinal, so no request can leave two candidates sharing one,
and a refused request changes nothing.

```json
{
  "candidates": [
    { "provider_id": 3, "model": "deepseek-v4-flash" },
    { "provider_id": 6, "model": "Bonsai-27B-Q1_0.gguf" }
  ]
}
```

- **Read the `configured` field before editing** — it is the capability's own stored rows, which is
  what the write replaces. The `primary`/`backups` fields are the RESOLUTION and cannot be written
  back: the ladder may have answered with an agent's declaration, a location class expands into many
  rows, and a candidate switched off is filtered out of the resolution entirely.
- **An empty chain is not "off".** `{"candidates": []}` means this capability configures nothing of its
  own and the ladder continues to the default row. `{"enabled": false}` is OFF: the resolver answers
  `disabled` and consumers refuse.
- **Refusals:** `404` when the key is not a capability; `400` for a candidate that cannot be attempted
  (not exactly one of the three forms, an unknown provider id, an unknown location class, a thinking
  level outside the vocabulary, or a speech engine no registry can build).
- `label` and `enabled` are overwrite-only — leave a field out and it is left alone.

The write path is the ONLY way a capability's chain changes; nothing seeds it at runtime.

### Ask for a service from code

```python
from app.domain.providers.capabilities import resolve, attempt_chain

resolved = await resolve(db, "summary")        # never raises for "nothing configured"
if not resolved.candidates:
    logger.warning("summary is not configured — skipping")   # SKIP, do not invent a service
    return

outcome = await attempt_chain(
    list(resolved.candidates),
    call=lambda candidate: ask(candidate),     # one attempt; RAISE on failure
    capability="summary",
)
answer = outcome.response
```

Three rules the code depends on:

1. **A component with no database session cannot resolve.** Resolve where the session is and **carry
   the answer** to the component — on the turn's own object, or on the descriptor it was handed. Never
   write it onto a shared instance: the memory manager is a registered singleton serving concurrent
   turns, and per-turn state on it would race. (Its chain is carried on the turn's context for exactly
   this reason.)
2. **No chain means SKIP, and say so.** Log which capability had nothing configured. Falling back to a
   service name written in code is the defect this system exists to remove, and it hides the case where
   a service is simply not configured.
3. **A service name in code is a bug.** The one deliberate exception is the workflow routing seed,
   whose provider and model are an AGENT LOOKUP KEY — the router matches an agent row with them and the
   agent's own declaration supplies the service — and the code says so at the table.

### Reading the log

| what you see | what it means |
|---|---|
| `capability '<key>': attempt 0 (primary) '<provider>/<model>' FAILED — <error>` | the primary failed; a backup may still answer |
| `capability '<key>': attempt 1 (backup #1) '<provider>/<model>' FAILED — <error>` | the backup failed too; the last error is what the caller reports |
| `capability '<key>': the whole chain failed (<a -> b>) — the last failure is what the caller reports` | nothing in the chain answered |
| `capability '<key>' is DISABLED — nothing resolves` | the capability is switched off; the caller must refuse |
| `capability '<key>': nothing resolved — no enabled candidate and no default provider row` | the last rung; the caller is expected to fail loudly |
| a failure carrying `config_source=capability_resolution` | the service came from the resolver — name it in the statement |

## Where the code lives

| surface | path |
|---|---|
| the resolver, the ladder, the walk, the constants | `backend/app/domain/providers/capabilities.py` |
| the read-out and edit endpoints | `backend/app/api/v1/providers/capabilities_router.py` |
| the configuration rows | `capabilities` + `capability_services` tables |
| the availability read | `backend/app/domain/providers/availability.py` |
| the refusal statement | `backend/app/domain/providers/refusal.py` |
| the page | `/providers/capabilities` |
| the tests | `backend/tests/unit/providers/test_capability_resolver.py`, `test_attempt_chain.py`, `test_refusal.py`, `backend/tests/api/v1/test_capabilities_api.py`, `test_capabilities_write_api.py` |

## How to check this page is still true

- The live answer, as the app gives it:
  `curl -s localhost:8000/api/v1/providers/capabilities`
- The rung names and the walk's own log wording: `grep -n "REASON_\|attempt %d\|the whole chain failed" backend/app/domain/providers/capabilities.py`
- The three naming forms and the `disabled` rule: `grep -n "AGENT_INFLUENCED_CAPABILITIES\|require_location\|service_name" backend/app/domain/providers/capabilities.py`
- The tests above are the pinning ones — if the ladder's order or the refusal rule changes, they fail
  in the same commit.

## Related

- [[dev-notes/api/title-capability|The Title Capability]] — one consumer, end to end
- [[dev-notes/configuration/adding-a-provider|Adding a Provider]] — the rows a service resolves to
- [[dev-notes/configuration/configuration-surface|The Configuration Surface]] — where settings live
- [[atlas/ui/pages/ProviderCapabilities|The Capability Page]] — the page's widget map
- [[dev-notes/api/router-architecture|Router Architecture]] — why this sub-area registers before the
  provider routes
