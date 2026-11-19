---
name: cogitate-curated-models
description: "Use when managing the curated model list — adding, editing, or verifying a curated model row."
version: 1.1.0
author: Exa (agent-created)
tags: [cogitate, providers, curated-models, models]
---

# The Curated Model List — add / edit / verify a row

The curated list (`curated_models` table) is the HUMAN-owned set the agent
profile picker (ProfileDetail) shows; it is curated-FIRST since the
2026-09-08 fix. It is NOT provider discovery — `provider_model_cache` and
`GET /providers/{id}/models/browse` are machine-owned. Deleting a curated
row never touches the provider's own catalog, and adding one never
installs anything: the row is a recommendation.

DB is the source of truth; `curatedModels.ts` is only a seed fallback for
when the DB/API is unreachable.

## Procedure (verified end to end)

1. **Confirm the ID exists AS SERVED, before writing anything.**
   - The provider's own catalog, no key needed: `curl -s
     https://openrouter.ai/api/v1/models -o /tmp/or_models.json`, then
     filter with python3 (never by eye).
   - Through Cogitate: `GET /api/v1/providers/{provider_id}/models/browse?search=<term>`
     → `{models, total, from_cache, provider_name}`. An ID absent here
     fails at CHAT time, not at add time.
   - Read the metadata that shapes how the model must be driven:
     `context_length`, `top_provider.max_completion_tokens`, `pricing`,
     `supported_parameters`, and **`reasoning`** (`mandatory`,
     `supported_efforts`, `default_effort`). A stealth/cloaked release is
     id-prefixed `stealth/` on OpenRouter and can vanish without notice.
2. **Read the list first**: `GET /api/v1/curated-models?provider=<name>&include_inactive=true`.
   Check for an existing row — it is unique on provider + model_id. There is no
   ordering number to pick: **`sort_order` is RETIRED** (the column is gone, and a
   request still carrying it is refused, with the reason) — display order belongs to
   the reader, so clients sort what they show.
3. **Create**: `POST /api/v1/curated-models` with
   `{provider, model_id, model_name, category, description, context_length,
   thinking, location}` → **201**.
   - `category` ∈ `chat | code | reasoning | vision` (matches the frontend's
     ModelCategory). Anything else is a 400:
     `Invalid category: X. Valid: [...]`.
   - **An omitted `category` is NOT defaulted.** The row stores nothing, and `None`
     is the honest "nobody has described this row yet" — no layer anywhere supplies a
     default. Name a category deliberately, or leave the row genuinely unstated.
   - **`is_free` and `featured` are NOT accepted** — both are refused with the reason.
     `is_free` is DERIVED as the row is created, from the provider's own cached
     pricing (an unpriced model stays `None` rather than becoming a guess);
     `featured` is retired, because the app does not privilege models. `featured` is
     not a category value either.
   - `provider` must match a provider NAME exactly (name-keyed); a
     duplicate (provider, model_id) is a 400, not a second row.
   - **`thinking` and `location` are part of this body — and the row is VERIFIED
     AGAINST THE PROVIDER AS IT IS CREATED.** The window and the reasoning level both
     come off the cached catalog payload, so `reasoning: {mandatory: true}` is stored
     as `mandatory`, and a value you send that DISAGREES with the payload is replaced
     by the provider's and logged. Send a level only for a driver whose payload says
     nothing. `location` is always yours to state. An unknown value is a **422** whose
     message lists the valid ones.
   - **The response tells you which happened:** `verified: true` with the provider's
     `context_length` means a FRESH claim was found and adopted. `verified: false`
     means nobody has fetched this model yet — the row is honest, not checked. The log
     names it (`WINDOW VERIFIED|MISMATCH|UNVERIFIED at create`, `THINKING ADOPTED at
     create`); read it before reporting.
   - Write the description so the NEXT reader is warned about anything
     operational (a mandatory-reasoning model, a context ceiling): the row
     is what the picker shows.
4. **Verify three ways — never the POST response alone.**
   - `GET /api/v1/curated-models/{id}` → 200, fields as posted
   - re-list the provider (`?include_inactive=true`) and count
   - read the live DB read-only: sqlite URI
     `file:<project-root>/cogitate.db?mode=ro`, table `curated_models`
     (the root DB is live; `backend/cogitate.db` is a decoy)
5. **Report claimed vs verified** ([[report-verified-state]]): what was
   posted, what each read-back returned, the row id. Lists, one item per
   line — no pipe tables, no crammed lines.

## The capability columns — yours to set, and load-bearing

`thinking` and `location` are written THROUGH THE API: both are on
`POST /api/v1/curated-models` and on `PUT /api/v1/curated-models/{id}`, and
both are validated against a CLOSED vocabulary.

| field | values | what it decides |
|---|---|---|
| `thinking` | `none` · `low` · `medium` · `high` · `mandatory` | the substitution matcher's FLOOR, and the output-budget floor |
| `location` | `local` · `cloud` | the matcher's EXACT compare — `any` is the SPEC's tolerance, never a value a row carries |

**The claim decides, at create and at verify.** `POST` reads the model's cached
catalog payload with the same parsers verification uses, so `reasoning:
{mandatory: true}` is recorded as `mandatory` and the provider's window lands on the
row. A level you send is the FALLBACK for a driver whose payload says nothing; when
the two disagree the provider's record wins and the disagreement is logged. That is
E.4's rule for the window, applied to the label — and it matches what the READ path
does anyway, which resolves the claim before it ever looks at the row.

A deliberate override lives on `PUT` (edit a row), not at create: an update sets what
you send and the row stays yours until somebody verifies it. `mandatory` is **not** a
degree of effort — it says the driver cannot be told not to think, and it is kept as
its own state rather than folded into `high`.

Omitting the level is the shorter path AND the more honest one: the row is born
saying what the provider says, and the description stays free for the operational
caveat a reader needs.

**How far the label reaches.** It is the SECOND source of a driver's thinking
signal: the provider's cached claim is read first and wins when the two disagree.
Any source saying "this thinks" is enough, and the signal floors the output budget
at **16000 tokens** (`thinking_floor`). So a reasoning driver whose row says `none`
AND whose provider claim is silent is the one case that gets no floor — and
`verify-window` below is how that row gets corrected.

`PUT` is **overwrite-only**: a field you do not send is left alone, and no value
means "reset to the default". Send the value you want.

## `verified` — earned, and the two ways a row gets corrected

`verified` is factual and earned against the provider's own catalog — at CREATE
(when the cached claim is fresh the row comes back `verified: true`), by
`POST /api/v1/providers/{id}/sync` (which marks every row whose model_id the fetch
returned), or per row by the verify endpoint below. It is NOT a field you set —
never promise it; read it.

**Per-row correction is a different call, and it is the narrow one:**

```
POST /api/v1/curated-models/{id}/verify-window      body: {"refresh": false}
```

It reads the provider's claim we already cached, adopts the WINDOW onto the row,
adopts the reasoning claim onto `thinking`, and returns `mismatch` + `note` when the
two disagreed instead of overwriting in silence. `"refresh": true` asks the provider
for its catalog first — slower, and the answer says whether the claim is fresh.

It touches **ONE row** and has no side effects elsewhere. That is what makes it the
right tool for "this row looks wrong", where a full provider sync is a different
decision: it re-evaluates EVERY curated row for that provider and can change their flags. **ASK
before running a sync**; verify-window you can simply run.

## Test the model before recommending it

`POST /api/v1/chat/completions` with
`{model: "<provider>/<model_id>", messages: [{role, content}], options: {max_tokens: N}}`
— an OpenAI-shaped NON-streaming call through the backend, which already
holds the provider key (never read `.env` yourself). No agent, no session,
no cleanup. `options` maps ONLY temperature / max_tokens / top_p, so no
reasoning effort can be sent from this surface.

**That surface cannot reach every provider.** It forwards `model` straight to LiteLLM with no
`base_url` and no key, so a provider the app reaches by resolving its OWN row cannot be
exercised this way — `ollama_cloud` (`https://ollama.com` + the cloud key) is the live case,
and `ollama_cloud/<model>` dies as an unknown provider rather than reaching ollama.com. Drive
the app's own builder instead — `app.api.v1.chat.context.build_llm_request` over a
`ChatContext` carrying that provider's `api_base`/`api_key` — or add the row and test through
a real turn.

A 200 is not proof of an answer: check `choices[0].message.content` AND
`usage.completion_tokens` against the cap. A starved reasoning model
returns 200 with `content: ""` and `completion_tokens` == the cap.

A 200 is also not proof the account can use it: a provider with plan limits answers the
request with its own refusal (`ollama.com`: *"this model is not included in your free
usage"*), which LiteLLM surfaces as an `APIConnectionError`. Probe the whole served
catalog and classify the refusals before curating — a row for a model the account cannot
call is a trap for whoever picks it.

Answering is not the whole contract — check TOOL CALLS too. A model can
answer fluently and still ignore the tool definitions it was sent, so a
tool-dependent agent (a scout, a reporter) then declines the very task it
exists to do. Before recommending a model for a tool-heavy role, run a turn
that needs a tool and confirm the tool loop fires; a clean answer proves
nothing about tools.

## The reasoning floor: where it actually comes from

The floor is decided from THREE sources, strongest evidence first:

1. **the driver's own record** — the provider's cached `reasoning` claim, else
   the curated row's `thinking` label;
2. **the agent's own declaration** — `llm_spec.thinking`;
3. **the name-pattern list** — `r1`, `-r`, `deepseek-v4`
   (`is_reasoning_model` in `backend/app/services/cognitive_pipeline/reasoning_support.py`).

So the vendor's metadata is LIVE for any model the catalog has fetched: its
`reasoning` field is parsed and floors the budget. The name pattern is the LAST
resort, for a driver nobody has recorded — it is a floor, not the trigger, and any
pattern change is a CODE change → propose it, get the go.

Budgets that then apply: nothing declared → 4096, fast path → 512, deep pass → 4096;
a thinking driver → floored to **16000** with the reason named in the log
(`thinking_floor` / `thinking_mandatory`).

PROVE it with a two-call A/B on one prompt (tiny `max_tokens` vs generous) through
`/chat/completions`; the generous call answering well inside its cap is the positive
control that the tiny call was starved, not broken.

## Pitfalls

- Trusting the POST 201 as the result — read the row back (API + DB).
- **Sending the retired fields is a 422, not a silent ignore**: `sort_order` (its column is
  gone), `featured`, and `is_free` (derived at create). A writer that keeps sending them
  keeps failing on purpose — a field silently ignored looks exactly like a working save.
- **"As served" can ROTATE.** `ollama.com`'s catalog (its ungated `/api/tags`) returns a
  different sample on each call, so one snapshot is not a promise: pin the ids you curate
  from a single fetch, and re-check before relying on the row later.
- Listing without `include_inactive=true`, missing a deactivated row, then
  adding a duplicate.
- Promising `verified`, or reporting the picker's stale list as done.
- **Leaving `thinking` at its default `none` for a driver whose catalog says
  `reasoning.mandatory`** — the row then states the opposite of the provider, and
  `verify-window` will report the disagreement and adopt the claim. Read the metadata
  in step 1 and set the label there.
- Assuming a curated row makes a model usable: the ID has to exist in the
  provider's served catalog, and a mandatory-reasoning model needs a real
  output budget at chat time.
- A stealth/cloaked model is temporary by nature — re-check the catalog
  before relying on the row later.

> Canonical copy: `skills/exa/cogitate-curated-models/SKILL.md` (tracked in the repo,
> provisioned into this home). Edit the tracked copy.
