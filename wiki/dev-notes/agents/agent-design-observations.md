---
title: Agent Design Observations
type: dev-note
path: wiki/dev-notes/agents/agent-design-observations.md
created: 2026-09-22
updated: 2026-09-25
status: draft
tags: [type/dev-note, domain/agents]
---

# Agent Design Observations

> THE DATA — the seed of the agent-design knowledge base: one row per
> agent behaviour that taught us something about designing agents. The
> rules derived from these cases live in
> [[dev-notes/agents/agent-design-guidelines|Agent Design Guidelines]].
> Add rows as they are measured; a case that is not measured is not data.

## How to add a row

- State the CASE (what the agent had to produce), the DRIVER
  (`provider/model`), the BUDGET it ran under, what was OBSERVED, and
  where the EVIDENCE lives — a log path plus the command or report that
  shows it, never a memory of it.
- Record the measurement, not the story. The number is the asset.
- A row states what is measurable now; when a quantity changes (a budget
  is raised), the row is updated to the current fact and the finding it
  produced stays in the guidelines.

## Output budgets

| Case | Driver (provider/model) | Budget | Observed | Evidence |
|---|---|---|---|---|
| Long-form news output — a 10-day forecast table (7 columns × 10 rows) plus a summary | openrouter/inclusionai/ling-3.0-flash | `max_tokens` 8192 (the row's declared budget) | the whole output needs ~2,100 tokens; at 2000 it arrived cut mid-table / cut in the summary and the stream's `truncated` flag said so — the measurement the sizing rule comes from | `agents/bob/issues/forecast-truncation-2026-09-22.md`; `backend/logs/frontend.log` — `Response truncated (token count fallback)` with `estimatedTokens` 2173 / 2417 / 2199 / 1969 against `maxTokens` 2000 |
| The same turn's deep pass (the conduit's second, more thorough pass) | openrouter/inclusionai/ling-3.0-flash | `max_tokens` 8192 (the declaration — the pass takes the larger of it and its own 4096 minimum) | that pass used to close with no stop reason recorded anywhere, so a clipped pass was invisible; every stream now says why it ended (`finish_reason` + `truncated` on its `STREAM COMPLETED` line) | `backend/logs/app.log` — the `STREAM COMPLETED … session_id=115` lines and their `accumulated_chars` (the early measurement); current lines carry `finish_reason=stop truncated=False` |
| A thinking driver on a small budget (the pseudo-agent tag chain, pinned single-step specs) | openrouter/inclusionai/ling-3.0-flash-sante:free | 4000 → 16000 | at 4000: `out_tokens=4000` and an EMPTY answer (1 of 6 steps answered); at 16000: 5 of 5 answered, mean 20.7s, $0 | `backend/scripts/describer_dryrun.py --arm`; recorded in the backlog (the pseudo-agent `max_tokens` entry) |
| A long-form answer that fits — the largest recorded stream | openrouter/inclusionai/ling-3.0-flash | 2000 (streamed longest under it) | 8,363 characters (~2,090 tokens) streamed in one pass | `backend/logs/app.log` — `STREAM COMPLETED … accumulated_chars=8363` |
| A long-form ask at the raised budget — a 700-word explainer | openrouter/inclusionai/ling-3.0-flash | `max_tokens` 8192, both passes | 9,078 characters / 907 tokens rendered, 6.5 s, both streams `finish_reason=stop`, `truncated=False` — the size the sizing rule targets, with headroom rather than at the edge | `backend/logs/app.log` — the two `💰 EFFECTIVE OUTPUT BUDGET … session=133` lines (`max_tokens_sent=8192 reason=declared`), `STREAM COMPLETED … accumulated_chars=4539 finish_reason=stop`, and the turn's `🧮 TURN ACCOUNT` |
| A turn whose tool chain outran the loop — five rounds, nothing written | openrouter/inclusionai/ling-3.0-flash | `max_tokens` 2000 (the declaration then; the loop's own cap was what stopped it) | `provider_calls=5 paths=pass1:5 tool_calls=5 tokens_out=0`: the turn spent five provider round-trips on tools and produced no answer, and the row was refused for being empty — the turn said NOTHING on the transcript while the user watched a spinner. A turn that stops without an answer now persists the reason as the message (`stopped_without_answer`), so the stop is readable after a reload — and the loop's last round is followed by one more call with the tools withheld (the answer pass), so a turn in this state writes from the results it collected unless that call comes back empty too | `backend/logs/app.log` — the `🧮 TURN ACCOUNT … session=125` line and the `EMPTY-MESSAGE GUARD` refusal beside it; pinned by `tests/unit/test_hard_limit_stop.py` |
| A turn that ran the conduit's two passes | openrouter/inclusionai/ling-3.0-flash | the log's `max_tokens_sent`: **8192** on pass 1 AND on the deep pass (declared **8192**) | the number is the PATH's decision, not one a reader would guess from the profile: pass 1 runs at the DECLARED budget (`reason=declared`), and the deep pass takes the larger of the declaration and its own 4096 minimum — a declaration above it flows through, so this row logs `reason=declared` there too rather than `deep_min`. Both passes stopped cleanly (`finish_reason=stop`, `truncated=False`) and no request logged a budget mismatch. The same model returned a `reasoning` field on a question needing none, while the catalogue calls it `thinking: none` | `backend/logs/app.log` — the two `💰 EFFECTIVE OUTPUT BUDGET … session=133` lines and the `done` frame's `metadata.reasoning`; endpoint `POST /api/v1/chat/stream` with `{"agent_id": 19}` |

| A mandatory-reasoning stealth driver pinned to a tiny budget | openrouter/stealth/space-bunny-alpha | `max_tokens` 24 (a deliberate probe, not a turn) | HTTP 200, `finish_reason: stop`, `completion_tokens: 24`, **content `""`** — no error and no truncation flag, just an empty answer. The same question at `max_tokens: 300` answered in 20 tokens, so the budget is the only difference: this driver's reasoning is **mandatory, at default effort `max`** in the provider's own words, and it spends the budget before writing a word. No floor applied — the name-pattern list matches `r1` / `-r` / `deepseek-v4` only, and every call site omits the resolver's `thinking` argument | `POST /api/v1/chat/completions` — the three probe calls recorded in chat session 141 (message 773); the provider's claim `reasoning: {mandatory: true, default_effort: "max"}` in `provider_model_cache.raw_data` for `stealth/space-bunny-alpha` |
| The same driver on the agent-chat path | openrouter/stealth/space-bunny-alpha | agent `max_tokens` **2000** — the call ran at **1024** | the agent-chat path runs the executor directly, so that turn's budget was the executor's own constructor default (`HybridExecutor(fast_max_tokens=1024)`) floored by `effective_max_tokens`; the resolver is not called on this path at all, so the agent's declared 2000 was never read. The chat path for the same agent and model, minutes apart, sent the declaration (2000, then 16000 after the row was raised) | `backend/logs/app.log` — `app.services.cognitive_pipeline.executor \| HybridExecutor pass 1 (fast) — model=openrouter/stealth/space-bunny-alpha, max_tokens=1024` at the probe's turn (20:16:30); the `💰 EFFECTIVE OUTPUT BUDGET … session=144` lines beside it show what the chat path sent |
| A tool-heavy turn that outran the loop — four times in one session | openrouter/stealth/space-bunny-alpha | `max_tokens` 16000 (the row's declaration, after it was raised) | `provider_calls=5 paths=pass1:5 tool_calls=22 tokens_out=0` — and the same signature at 31, 13 and 11 tool calls across four turns of one session. Every iteration came back `finish_reason=tool_calls` with no prose, so the loop's own cap (5) ended the turn and the transcript got the stand-in sentence (`stopped_without_answer`). The four turns spent **249,377 input tokens and 77 tool calls** for no answer, and no budget line was involved: no clamp, no `length`, no hard limit — the only limits that spoke were soft (`tool_calls 22 ≥ 20`, `provider_calls 8 ≥ 8`). The loop executes the last iteration's tool batch and then asks for the answer with the tools withheld (the answer pass) — the call this state was missing | `backend/logs/app.log` — the four `🧮 TURN ACCOUNT … session=142` lines carrying `tokens_out=0`, beside the four `NOTHING TO SHOW session=142` lines and `⚠️ LIMIT SOFT key=tool_calls` |

| A turn on a driver our own label called non-thinking | openrouter/inclusionai/ling-3.0-flash | `max_tokens` 8192 declared → **16000 sent**, `reason=thinking_floor` | the curated row said `thinking: none` while the provider published `reasoning: {default_enabled: true}` — and the turn settled it: the stream carried **`reasoning` tokens before the answer** ("…This is a simple, direct request."), then `F3 CHAIN OK`. Both passes ran at 16000 and ended `finish_reason=stop truncated=False`, the turn spent 5310 input / 10 output tokens over two calls, and the saved row carries the thinking (`meta.reasoning`) for replay. The floor is what the 8192 declaration could not have covered on a driver that thinks first | `backend/logs/app.log` — `🧠 MODEL THINKING model=inclusionai/ling-3.0-flash provider=openrouter thinking=true mandatory=false source=provider_claim`, the two `💰 EFFECTIVE OUTPUT BUDGET … session=147` lines, `🧮 TURN ACCOUNT … session=147`; `POST /api/v1/chat/stream {"agent_id": 19}` |

| A package agent taking its CLASS default, with nothing typed on its row | codellama:latest (a local driver; no claim recorded) | `max_tokens` unset → **8192**, `reason=declared` | the row declared a bespoke 2000. Re-adopting the agent onto the seeded `shallow-agent` package — whose spec now declares `max_output: 8192`, the ladder's shallow class — put the class number on the agent's OWN row: the package states the class, the agent owns its copy, and the resolver reads that copy (the spec is the one declaration slot). Its driver has no thinking signal of any kind, so the floor correctly stays out of it | `POST /api/v1/agents/54/adopt-package` → 200 with `llm_spec.max_output = 8192`; the read-only chain check `local/token-limits/f3-chain-check.py` §3 prints `Wanda 8192 (declared)` |

## The window and the input side

| Case | Driver (provider/model) | Budget | Observed | Evidence |
|---|---|---|---|---|
| One ordinary turn, after the driver's window was VERIFIED | openrouter/inclusionai/ling-3.0-flash | input budget **16000** · `max_tokens_sent` **8192** on both passes | the window is `262144` and came from the **verified curated row** (`source=curated`), the assembly ceiling STAYED at 16000 (`min(16000, 262144 − 8192)` — a big window does not enlarge a prompt), the turn's own prompt came to **5354 tokens across both calls**, so the input soft (80 % of 16000 = 12800) never spoke, and both streams ended `finish_reason=stop truncated=False` | `backend/logs/app.log` — `🪟 MODEL WINDOW … window=262144 source=curated`; `📚 Context built: 0/0 messages, ~2625 tokens (input budget: 16000, dropped: 0)`; the two `💰 EFFECTIVE OUTPUT BUDGET … session=135` lines; `🧮 TURN ACCOUNT … session=135 … tokens_in=5354` |
| The driver's window, verified against the provider's own list | openrouter/inclusionai/ling-3.0-flash | — (a verification, not a turn) | the curated row was **NULL**; one `refresh: true` call wrote **262144** and `verified = 1` from OpenRouter's own entry. The same payload shows **reasoning enabled by default** while our row says `thinking: none`, and the provider's own cap at **32768** | `POST /api/v1/curated-models/10/verify-window {"refresh": true}`; `backend/logs/app.log` — `✅ WINDOW VERIFIED … window=262144` and `⚠️ THINKING MISMATCH … provider_claims=reasoning: default_enabled=True, mandatory=False` |
| A second row verified, on a driver whose reasoning is mandatory | openrouter/stealth/space-bunny-alpha | — (a verification, not a turn) | `verified = 1` and `context_length = 1000000` adopted from OpenRouter's own entry, in 0.76 s; the provider's own output cap is **524288**. The same payload reports **`default_effort=max, mandatory=True`** — thinking that cannot be turned off — while our row still read `thinking: none`. The create and update schemas expose neither `thinking` nor `location`, so the WRITE PATH is the verification itself: it now adopts the claim's level onto the row (`thinking_adopted` in its response), which is how both rows stopped being hand-set guesses (F.3) | `POST /api/v1/curated-models/12/verify-window {"refresh": true}` → 200 in 0.76 s; `backend/logs/app.log` — `✅ WINDOW VERIFIED model=stealth/space-bunny-alpha window=1000000` and `⚠️ THINKING MISMATCH … provider_claims=reasoning: default_effort=max, mandatory=True` |

## What each case teaches

1. **Size the budget to the longest output, not the average.** A budget
   that fits a headline scanner will cut a forecast table.
2. **A cut is not always the budget.** A stream can end after a few
   hundred tokens with no verdict at all, which is why the stop reason is
   now recorded on every stream — without it, the budget question cannot
   be answered from the log.
3. **Thinking is spent from the same budget as answering.** A thinking
   driver at a small budget produces an empty answer, not a short one.
4. **The shape of "fits" is measurable** — characters streamed, tokens
   spent, the budget it ran under. Measure before sizing.
5. **The provider's claim outlives our label.** `reasoning.mandatory` and
   `default_effort` come from the provider and survive a name change, while
   our `thinking` field is hand-set and starts at `none` on every new row.
   The floor therefore reads the CLAIM first, the label second, the agent's
   own declaration third and the name pattern last — and an unfamiliar
   driver's empty answer is a budget question first.
6. **A turn can end without ever being asked for an answer.** The tool
   loop runs a fixed number of rounds and ends after executing the last
   one's tools; a model that searches in parallel batches spends every
   round on tools, so a sweep that is not bounded in the PROMPT ends as a
   stop notice rather than a brief (measured at 22, 31, 13 and 11 tool
   calls in one session).
7. **The path decides the budget, and one path still does not ask.** The
   resolver decides the chat path's number per call; the agent-chat path
   runs the executor, which carries its own constructor defaults and never
   calls the resolver, so the same agent on the same driver sent 2000 on
   one surface and 1024 on the other.

## Related

- [[dev-notes/agents/agent-design-guidelines|Agent Design Guidelines]]
- [[dev-notes/agents/agent-provisioning-guidelines|Agent Provisioning Guidelines]]
