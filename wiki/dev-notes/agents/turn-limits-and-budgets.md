---
title: Turn Limits and Budgets
type: dev-note
path: wiki/dev-notes/agents/turn-limits-and-budgets.md
created: 2026-09-23
updated: 2026-09-24
status: draft
tags: [type/dev-note, domain/agents]
---

# Turn Limits and Budgets

> What a turn may spend, who decides it, and what happens when a line is crossed.
> The design side — how to SIZE a budget for an agent — is
> [[dev-notes/agents/agent-design-guidelines|Agent Design Guidelines]]; the numbers
> per path and limit are tabulated there. The measured cases behind both are
> [[dev-notes/agents/agent-design-observations|Agent Design Observations]].

## One decision point for the output budget

`backend/app/services/cognitive_pipeline/output_budget.py` owns the number that goes
on the wire. `resolve_output_budget()` applies the runtime override, else the agent's
declared `llm_spec.max_output` (copied from its package's type default at adoption),
else the resolver's fallback, and then the PATH's policy; `apply_output_budget()` is the same decision plus the write and the log line,
and every path calls it (`tests/unit/test_one_budget_writer.py` fails if a path starts
deciding for itself again — its module list covers both chat paths, `/chat` and
`/agent-chat`).

| Path | What it sends |
|---|---|
| the ordinary turn (`default`) | the declaration (override first), then the thinking floor |
| `fast` (the fast profile) | the profile's policy constant — a legitimate brief-answer profile, named and logged |
| `pass1` (a hybrid turn's first pass) | the declaration — a first pass is not a cheaper pass |
| `deep` (the conduit's second pass) | the LARGER of the declaration and the pass's own minimum, then the floor |

`/agent-chat` is not a separate policy: it resolves the `default` path for the run and
hands the executors that number, so the same agent sends the same ceiling on both paths.

`reason=` on the log line names which of those spoke
(`declared` / `runtime_override` / `no_declared_budget` / `fast_policy` /
`deep_min` / `thinking_floor` / `thinking_mandatory` / `window_clamp`), so a budget question is answered from the log rather than from the
profile. The profile answers it too: the agent read carries the resolver's
`output_budget` **and** the last turn's own record (`observed`, from the turn's saved
row), so the declared number, the number that would go out and the number the last
turn actually carried are readable in one place.

## The model's window, and the input side

**The window is physics, not policy** — a fact about the driver (prompt **plus**
answer), read and never chosen. `domain/providers/model_window.py` answers it: the
curated row first (a verified statement), else the provider's own discovered claim,
else **unknown** — an unrecorded driver keeps the assembly ceiling and logs
`window unknown` once per model, so nothing is clamped on a number nobody has.

| What the window does | Where it shows |
|---|---|
| **Clamps an output budget** that cannot fit beside the prompt (`prompt + max_tokens ≤ window`) — the only lowering our policy allows | `🪟 WINDOW CLAMP model=… window=… prompt_tokens=… budget=… clamped=…`, and `reason=window_clamp` on the effective-budget line |
| **Caps the input side** — history is trimmed to `min(DEFAULT_INPUT_BUDGET, window − reserved output)`; a big window never RAISES it | `📚 Context built: 2/6 messages, ~T tokens (input budget: B, dropped: N, fixed: F = system S + tool schemas X, replayed reasoning: R)` |
| **Warns at provisioning** when a driver is too small for what an agent needs (the prompt floor plus its declared output) — reported, never a refusal | `⚠️ WINDOW FIT …` on the log and `window_note` in the provision response |
| **Is verified, not trusted** | `POST /api/v1/curated-models/{id}/verify-window` → the row adopts the provider's own number, `verified=1` only when the claim was fresh; a disagreement logs `⚠️ WINDOW MISMATCH model=… curated=… discovered=…` |

The **input side** has its own line: a soft at 80 % of the input budget in force, judged
against **one call's** prompt (never the turn's total). Its sentence **reports the measured
composition of the call it is warning about** — `This call's prompt measured: system 1,213 ·
history 11,212 · tool results 0 · tool schemas 3,560 · replayed reasoning 5,124` — from the same
rendering the log's own line uses (`prompt_accounting.describe_account`, one home for the part
names), and it states the budget's boundary: the count covers the system prompt, the schemas, the
replayed thinking and the kept history, while the tool results the turn adds *after assembly* are
not re-judged. Where the caller cannot measure (the declaration sites, a path with no messages in
hand) the sentence names no numbers at all. (It used to name a cause it had never measured — "the
persona, the tools and the message" — while the measurement said the persona is 579 tokens and it
is the fetched pages that fill the prompt; a sentence that cannot measure must not assert.)

**What the trim counts** (Phase B of the input-budget arc). The budget deducts the **fixed part**
— the system prompt, the **tool schemas** (the request's `tools=[…]` field, measured serialized:
the same number the window clamp uses, one home for both) and the response headroom — and then
selects history newest-first, counting each message's `content` **plus the `reasoning_content`
that message will re-send**. The turn's own tool results are message content and have always been
counted. Two consequences worth knowing:

- **history is dropped earlier** than it was before this arithmetic, by exactly the schemas' and
  the replay's weight. That is the deliberate behaviour change: a budget that describes the prompt
  rather than part of it;
- **a fixed part larger than the whole budget cannot empty the history** — the ≥1-pair rule
  stands, and the line says `reason=fixed_exceeds_budget` instead of failing quietly.

**The per-call account** (Phase A) is the reading behind all of it: every provider call logs one
line naming what its prompt carried, by contributor — `📐 PROMPT ACCOUNT … measured · system …
· history … · tool results … · tool schemas … · replayed reasoning … · the trim counts … of it
(content alone) · ceiling … · soft …`. It observes and nothing more: no line of it trims, blocks
or refuses a call. This is why the next prompt question can be answered from the log instead of
by a hand-written probe.

A fresh session's fixed prompt is ~2 k (shared rules 577 + persona 579 + the tools note 57, plus
an agent's own state/notebook blocks); the soft's 12.8 k line is reached by a turn that fetches.

## What makes a driver a thinking driver

The floor exists because a driver that reasons spends budget before it writes a word (the
ox-alpha incident: a 512-token budget came back empty). **What triggers it is a chain, and
the name list is its last resort** (F.3):

| Source, strongest first | Where it comes from |
|---|---|
| the provider's own claim | `provider_model_cache.raw_data.reasoning` — `mandatory` / `default_enabled` / `default_effort`, read by `domain/providers/model_window.resolve_model_thinking` |
| our curated row's label | `curated_models.thinking` — and `POST /api/v1/curated-models/{id}/verify-window` ADOPTS the claim's level onto it, which is the write path that field never had |
| the agent's own declaration | `llm_spec.thinking` (any level above `none`), read off the agent the resolver is already given |
| the name list | `reasoning_support.is_reasoning_model` — `r1` / `-r` / `deepseek-v4`, for a driver nobody has recorded |

Any one of them saying "this thinks" is enough: a driver that reasons cannot be talked out
of it by a row we hand-labelled — which is the whole point, because a live driver was
catalogued `thinking: none` while the provider published `default_enabled: true` and the
app's own stream showed it thinking. `mandatory` is not a fourth level of effort; it is a
statement that no parameter turns the thinking off, which is why it carries its own reason
(`thinking_mandatory`) and why a driver carrying it is one to replace rather than budget for.

## The limit model — one shape, one judge

`backend/app/services/cognitive_pipeline/limits.py` holds every limit and the only
judge, `check_limits()`:

- **A limit names its reason**, enforced at construction — the sentence reaches the
  log line and the user verbatim. A limit without a reason cannot be built.
- **`soft`** means: the log line, the user is told (a toast once per threshold per
  turn, plus the note on the message), and NOTHING stops.
- **`hard`** means: the turn is stopped (see the plug below).
- **Scopes**: `call` (judged per provider call) and `turn` (accumulated across the
  turn, both passes included).
- **The judgement is `value >= threshold`**, and an unmeasurable quantity is skipped
  rather than treated as a breach — a missing measurement is not a limit.
- **The census**: the armed set and the INACTIVE set print together, so a reader can
  tell "nothing is near a line" from "nothing is watching". The census names the
  turn-scoped lines, the call-scoped ones (the output soft, and the input soft at its
  threshold) and **one inactive row**: `cost_usd` (pricing is unverified — the price comes
  from the provider's own catalog, and several providers publish none at all, so the app
  cannot tell a genuinely free model from an unpublished one) — with
  `ProviderService.calculate_cost` saying `cost limit inactive` at the moment it falls
  back to $0 for an unpriced model, because a $0 measurement is not a limit that passed.
  `input_tokens` was the other inactive row until the window was derived; it is armed now.

The tool guard is part of the same model rather than a third mechanism:
`ToolCallTracker.limits_for()` publishes its own ceilings as `Limit` objects, so a
blocked tool call reports as a limit verdict.

## What a HARD line does — the plug

A crossing is judged at three boundaries: the main loop's call boundary, the deep
pass's call boundary, and the turn's end. The stop is one function
(`router._stop_turn`), which:

1. records the crossing on the turn's account, so the note on the message and a
   reloaded row both read it;
2. writes one log line — `🚫 TURN STOPPED key=… value=… threshold=… reason=… partial=… stage=… mode=…`;
3. emits the SSE frame `event: error` with `type=limit_stop`, in the tool guard's tone
   and ending with *"Say 'continue' and I'll carry on from what I have."*

Two outcomes, and the difference matters to the user:

| Mode | When | What the user gets |
|---|---|---|
| `abort` | something was still to do and the answer is not nearly complete | the turn stops here, **what already arrived is kept**, the frame + a warning toast | 
| `finish` | nothing was left to start, or the answer was nearly complete | the answer is kept WHOLE, the turn ends normally, and only the note says a plug fired |

**A plug that fires before the first token does not claim a partial it never had** —
zero kept is its own sentence, and the turn still persists a message (a stand-in
sentence marked `stopped_without_answer`) instead of leaving the transcript empty.
That sentence is streamed BEFORE the error frame, because the frontend stops reading
at that frame.

## What a SOFT line does

The log line (each breach), the toast (once per threshold per turn — a five-iteration
turn must not toast five times), and the note that rides the message: `metadata.limits`
(one record per crossing, including `mode` for a plug) and `metadata.limit_notice` (the
sentence the bubble shows). Both ride the DONE frame and the saved row, and every
mapper that carries message metadata carries them — the frontend's mappers list their
fields, so a key that is not carried is dropped silently and the note disappears on the
next reload.

Two of the soft lines are **call-scoped**, and both are fractions of a number the call
itself runs under: the output soft (90 % of that call's `max_tokens`) and the input soft
(80 % of the input budget in force). They are judged against THAT call's numbers, never
the turn's accumulated ones — the turn's total would fire the input line on the second
call of every multi-call turn, which is a false alarm rather than a limit.

## What the numbers mean in practice

**The armed numbers are runaway guards, not lines a normal turn approaches.** A turn's
ordinary work ends at the tool loop: its rounds plus the answer pass that follows them, which
is at most 6 provider calls (`turn_config.LOOP_ROUNDS` + the pass); the
`provider_calls` line sits above that, so it fires on a retry storm (a rate-limited
call retries up to three times) or the wall clock — i.e. on a turn that is stuck rather
than one that is merely long. Budget questions are answered by the output lines, not by
these.

**The loop's cap is the end of a tool-heavy turn, and it is not a limit.** When the last of the
rounds (`turn_config.loop_rounds()`, 5) comes back `finish_reason=tool_calls`, that round's tools
are executed — and the turn is then asked for its ANSWER: one more call goes out with the tools
**withheld** (the answer pass, `router._stream_answer_pass`), carrying the instruction that the
rounds are spent and the results it collected are everything available. The pass streams like any
other call, counts in the turn's account, and runs on the budget path already resolved for that
pass — so an exhausted loop produces the answer it collected instead of a sentence about its
limits. **Only when the answer pass comes back empty too** does the turn persist the stand-in
sentence marked `stopped_without_answer` (`NOTHING TO SHOW` in the log) rather than leaving the
transcript empty. Read the account line before reading a thin turn as a limit firing, because no
limit did.

## How to check any of this

```
# the census + the armed set, and the account of one turn
grep -E "TURN LIMITS limits:|TURN ACCOUNT" backend/logs/app.log | tail -4

# a fired plug and its handling
grep -E "LIMIT HARD STOP|LIMIT SOFT|TURN STOPPED" backend/logs/app.log | tail -10

# a loop that ran out of rounds — the call it is given instead, and a turn that produced nothing
grep -E "ANSWER PASS|NOTHING TO SHOW|EMPTY-MESSAGE GUARD" backend/logs/app.log | tail -5

# the budget each call actually sent, and the cost-limit statement
grep -E "EFFECTIVE OUTPUT BUDGET|BUDGET MISMATCH|cost limit inactive" backend/logs/app.log | tail -10

# the driver's window, what the assembly kept, and any clamp or fit warning
grep -E "MODEL WINDOW|Context built|WINDOW CLAMP|WINDOW FIT|WINDOW VERIFIED|WINDOW MISMATCH" backend/logs/app.log | tail -10
```

The turn's account line (`🧮 TURN ACCOUNT …`) reports what the turn spent —
`provider_calls`, tokens, elapsed, and the paths it ran — which is the
number every threshold is judged against and the one a calibration argument should use.

It also carries the turn's tool story, in the order a reader asks for it:
**`tools_offered`** (how many provider calls were given a tools array — the
denominator), **`tool_calls`** (the calls that happened), **`tool_calls_blocked`**
(calls the guard refused — deliberately not among the calls that happened) and
**`tool_failures`** (calls that ran and did not succeed). The pairs are the point:
`tools_offered=0 tool_calls=0` is a turn with no tool in play, while
`tools_offered=5 tool_calls=0` is a model that was offered tools and called none —
the reading that separates a broken tool-caller from a turn that never had the
option. A guard-killed turn reads `tool_calls=0 tool_calls_blocked=3` instead of
looking like a turn that never touched a tool.

The same numbers ride the saved row (`chat_messages.metadata.tool_call_summary`),
including the failure classes (`failures_by_type`, `failures_unnamed`) — so a turn
reloaded from the database still says what its tools did, and a model that was
offered tools and called none stays distinguishable from a turn that had none to
call.

## Tests that pin this behaviour

| What | Where |
|---|---|
| every budget the app sends, per type/profile/path (the resume point) | `tests/unit/test_output_budget_table.py` |
| the definitions, the copy, and the account's record of a stop | `tests/unit/test_hard_limits.py` |
| the plug through the REAL stream — frame, order, partial, no further call | `tests/unit/test_hard_limit_stop.py` |
| the answer pass — the extra call, its shape (no tools), the answer on the row, the empty case | `tests/unit/test_answer_pass.py` |
| the soft lines, the note and its metadata | `tests/unit/test_soft_limits.py` |
| one writer for the budget + the log line | `tests/unit/test_one_budget_writer.py`, `tests/unit/test_effective_budget_log.py` |
| the cost limit stating it is inactive | `tests/unit/providers/test_cost_limit_inactive.py` |
| the assembly ceiling and the window's lowering (E.1) | `tests/unit/test_input_budget.py` |
| the window's source, staleness and the fit warning (E.1/E.3) | `tests/unit/providers/test_model_window.py` |
| the window verified against the provider's own claim (E.4) | `tests/unit/providers/test_window_verification.py` |

## Related

- [[dev-notes/agents/agent-design-guidelines|Agent Design Guidelines]] — the design rules and the numbers table
- [[dev-notes/agents/agent-design-observations|Agent Design Observations]] — the measured cases
- [[dev-notes/agents/message-metadata|Message Metadata]] — the shape the note rides
- [[dev-notes/agents/agent-lifecycle|Agent Lifecycle & Provisioning]] — where a budget is declared
