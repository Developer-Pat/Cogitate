---
title: Agent Design Guidelines
type: dev-note
path: wiki/dev-notes/agents/agent-design-guidelines.md
created: 2026-09-22
updated: 2026-09-24
status: draft
tags: [type/dev-note, domain/agents]
---

# Agent Design Guidelines

> THE HOW-TO for the design side of an agent, once the driver is chosen
> (driver selection: [[dev-notes/agents/agent-provisioning-guidelines|Agent
> Provisioning Guidelines]]). What an agent is SHAPED to do — its output
> budget, its prompt size, its tool surface — decides whether it can
> finish what it starts. Every rule here came from a measured case; the
> measurements live in
> [[dev-notes/agents/agent-design-observations|Agent Design Observations]].

## The output budget is a hard stop the model cannot see

Every chat turn sends an output ceiling — and it is not always the agent's own
`llm_spec.max_output`: the run path decides a turn's budget PER CALL. A hybrid
turn is TWO calls: pass 1 runs at the declaration, and the conduit's deep pass takes
the LARGER of the declaration and its own minimum — so a raised declaration flows
through both, and a small one is lifted rather than shrunk. The provider stops the
stream at whatever that call sent — mid-sentence, mid-table, mid-word — and nothing
in the model's context tells it how much room it has left.

**The log says which number was sent, and why.** Every request logs
`💰 EFFECTIVE OUTPUT BUDGET max_tokens_sent=… reason=… declared=… path=…`:
`declared` is the agent's stored number, `max_tokens_sent` is the one that went
on the wire, and `reason` names what decided it (`declared` /
`runtime_override` / `no_declared_budget` / `fast_policy` / `deep_min` /
`thinking_floor` / `thinking_mandatory` / `window_clamp`). A design question about a
budget is answered from that line — and both chat paths write it (`/chat` and
`/agent-chat`), so the line is the whole story wherever the turn ran.

- **Size the budget to the LONGEST answer the agent must produce, not the
  average one.** A news agent's beat sweep, a forecast table, a multi-
  section report: the average turn fits anywhere, and the long one is the
  one that matters.
- **The number lives on the agent's `llm_spec.max_output`** — the contract it OWNS,
  copied from its package at adoption — and is editable on the agent profile. It is
  per-agent on purpose — a headline scanner and a long-form reporter do not need the
  same ceiling. `parameters` is the sampling settings only (`temperature`, `top_p`);
  a budget sent there is refused by name, because one slot deciding is the whole point —
  and the agent column's own default types sampling only too, so an ORM-created row (which
  never meets a request schema) cannot put the retired key back.
- **One place decides it**: `backend/app/services/cognitive_pipeline/output_budget.py`.
  `resolve_output_budget()` applies the runtime override, else the declared
  value, then the path's policy (the `fast` profile's constant, the deep pass's
  minimum, the fallback when nothing is declared), and finally the thinking
  floor. `apply_output_budget()` is the same decision plus the write and the log
  line, and it is what every path calls — `tests/unit/test_one_budget_writer.py`
  fails if a path starts deciding a budget for itself again, and its module list
  includes both chat paths.
- **A declared budget is what the paths may RAISE, never silently shrink.** The
  deep pass takes the larger of the declaration and its own minimum; a
  declaration above that minimum flows through untouched. Only the model's
  **window** (`reason=window_clamp`, and only when prompt + budget cannot fit) and
  a hard limit may lower a budget, and each says so in the log.
- **Thinking drivers need the floor, not the default.** See below.
- **The number the paths run on is DECLARED per agent; the CLASS values are the
  defaults a package declares.** `llm_spec.max_output` is the per-agent number and
  what runs (a row that must run long is raised on its own row; a row that declares
  nothing runs on `FALLBACK_BUDGET`, and the log says `no_declared_budget`). The
  per-class values ARE code constants — `output_budget.TYPE_BUDGETS` (lesser /
  shallow / deep / deep-long) — and they are what a package declares as its type
  default (carried onto the agent at adoption), what the profile form should offer,
  and the source the **ceiling** is derived from
  (`BUDGET_CEILING = max(table) × THINKING_MULTIPLIER`, shared by the API validation
  and the UI bound).

**The profile answers the budget question too.** The agent read carries
`output_budget` = {declared, effective, reason, path} resolved by the SAME function the
turn runs, plus `observed` = {sent, declared, reason, path, at} read from the agent's
LAST assistant message — so the page shows the prediction and the last turn's fact side
by side, and the row shows `· last N` only when the two differ. A turn that recorded
nothing shows no observation rather than an older turn's number.

## The window is the ceiling; the budget is what we choose under it

The model's **context window** is a fact about the driver — prompt **plus** answer — and
it is the only thing allowed to LOWER a budget we chose: when prompt + budget cannot fit,
the runtime clamps (`reason=window_clamp`) and logs the window, the prompt and the
clamped number together. Two sizing rules follow:

- **A driver whose window cannot hold the prompt plus the answer is the wrong driver**,
  not a budget to shrink. Provisioning reports it (`window_note`) instead of refusing,
  and the runtime clamps so the turn still runs — read the note and replace the driver.
- **The input side is a ceiling, never a target.** History is trimmed to the assembly
  ceiling (`DEFAULT_INPUT_BUDGET`), lowered by the window when the window cannot hold it;
  a driver with room to spare does not get a bigger prompt. The trim says what it kept
  and what it dropped (`📚 Context built: 2/6 messages … dropped: 4`).

**The window is READ, and a window nobody recorded does not clamp** (`window unknown`,
once per model) — an unrecorded driver behaves exactly as it did before any of this
existed. **Verify a row rather than trusting it**: `POST /api/v1/curated-models/{id}/
verify-window` compares the row with the provider's own model list, writes the provider's
number, and reports a disagreement (`⚠️ WINDOW MISMATCH`). The same call returns the
provider's thinking signal and its own output cap (`max_completion_tokens`) — check both
before trusting a `thinking` label, because **that label is ours, not theirs**.

## The numbers, as the code holds them

Read from the constants, not from a profile — the table is pinned to them by
`tests/unit/test_budget_docs_table.py`, so a constant that moves without this table
failing would be the bug.

| What | Value | Where |
|---|---|---|
| The input budget | 100000 by default (`INPUT_TOKEN_BUDGET` in `.env` sets it), lowered by the window — **not** the model's window | `token_budget.DEFAULT_INPUT_BUDGET` |
| The fast profile's budget | 512 | `output_budget.FAST_POLICY_BUDGET` |
| The deep pass's minimum | 4096 | `output_budget.DEEP_MIN_BUDGET` |
| Undeclared fallback | 4096 | `output_budget.FALLBACK_BUDGET` |
| Thinking floor | 16000 | `reasoning_support.REASONING_MAX_TOKENS_FLOOR` |
| The lesser class — trivial agents, pseudo-agents, workflow nodes | 4096 | `output_budget.TYPE_BUDGETS["lesser"]` |
| The shallow class — a row and a workspace, no memory (the base) | 8192 | `output_budget.TYPE_BUDGETS["shallow"]` |
| The deep class — a workspace and memory | 16384 · 24576 long-form | `output_budget.TYPE_BUDGETS["deep"]` / `["deep_long"]` |
| A thinking driver's class DEFAULT (never a declared number) | ×2 | `output_budget.THINKING_MULTIPLIER` |
| The budget ceiling — DERIVED from the table, never typed | 49152 | `output_budget.BUDGET_CEILING` |
| Output soft (a fraction of the call's budget) | 90% | `limits.OUTPUT_SOFT_FRACTION` |
| Input soft (a fraction of the input budget) | 80% | `limits.INPUT_SOFT_FRACTION` |
| Provider calls | soft 8 · hard 12 | `limits.SOFT_PROVIDER_CALLS` / `HARD_PROVIDER_CALLS` |
| Tool calls | soft 20 | `limits.SOFT_TOOL_CALLS` |
| The tool loop's rounds | 5, both loops (pass 1 and the deep pass) | `turn_config.LOOP_ROUNDS` |
| The stream call's timeout | 300 s | `turn_config.STREAM_TIMEOUT_S` |
| The direct answer's timeout | 30 s | `turn_config.ANSWER_TIMEOUT_S` |
| The delegate's HTTP timeout | 120 s | `turn_config.DELEGATE_TIMEOUT_S` |
| The delegate's own call timeout | 120 s | `turn_config.DELEGATE_CALL_TIMEOUT_S` |
| A rate-limited call's retries | 3 attempts, 2 s × attempt | `turn_config.RETRY_ATTEMPTS` / `RETRY_DELAY_S` |
| The guard's dedup window | 30 s | `ToolCallTracker(dedup_window_seconds=30)` |
| Wall clock | soft 300 s · hard 600 s | `limits.SOFT_WALL_CLOCK_S` / `HARD_WALL_CLOCK_S` |
| One tool, same arguments, in a row | soft 3 · hard 4 | `ToolCallTracker(max_consecutive_calls=4)` |
| One tool, in total | hard 30 | `ToolCallTracker(max_total_calls_per_tool=30)` |
| Declared inactive | `cost_usd` | `limits.TURN_LIMITS_INACTIVE` (each with its reason) |

What the soft and hard columns DO — the toast, the note, the stop, and what a
retry-storm ceiling means for a normal turn — is
[[dev-notes/agents/turn-limits-and-budgets|Turn Limits and Budgets]].

## A cut answer is reported — never read silence as success

`choices[0].finish_reason` is the provider's own verdict on how the
stream ended: `stop` / `tool_calls` mean finished, `length` means CUT at
the output budget, and a missing value means the stream closed without a
verdict (a dropped connection, or a provider that never sends one).

| Surface | What it carries |
|---|---|
| Backend log (`backend/logs/app.log`) | `⚠️ OUTPUT TRUNCATED (finish_reason=length) … content=N chars (~T tokens) of max_tokens=B` — the comparison a designer needs |
| The same log, for a stream with no verdict | `STREAM ENDED WITHOUT A STOP REASON …` (log only: the shape is suspicious, not proven) |
| The turn's structured log line | `STREAM COMPLETED` carries `finish_reason` and `truncated` — every stream says why it ended |
| The done frame | `metadata.truncated` + `truncationReason: "max_tokens"` → the UI warns the user in a toast |
| The saved message | `meta.truncated: true` on the assistant row — a reloaded turn still says it was cut |

The truncation signal is emitted by the streamer
(`backend/app/api/v1/chat/router.py` → `_stream_llm_response`), carried on
`StreamResult.finish_reason` (`backend/app/api/v1/chat/schemas.py`), and
turned into the frame + row metadata by
`backend/app/api/v1/chat/finalization.py`.

## Thinking spends the SAME budget as answering

A thinking driver (streams `reasoning` / `reasoning_content`) spends
output tokens before it writes a word of the visible answer. Hand it a
budget that fits only the answer and the answer arrives empty — or cut
after a few hundred tokens.

- The chat path floors the known thinking families to 16000 output tokens. The
  detection and the constant live in
  `backend/app/services/cognitive_pipeline/reasoning_support.py`; the floor is
  applied by the resolver in `output_budget.py`, which is the one site that
  decides it. At 4000 a thinking model can spend the entire budget and answer
  nothing.
- **The floor's trigger is a CHAIN, and the name list is its last resort.** The
  provider's own claim comes first (`reasoning` in its model payload), then the curated
  row's label — which `verify-window` ADOPTS from that claim — then the agent's
  `llm_spec.thinking`, and only then the name patterns (`r1`, `-r`, `deepseek-v4`). Any
  one of them saying "this thinks" is enough, so a routed thinking model is no longer
  floored only when its name happens to match. Treat an empty or unexpectedly short
  answer from an unfamiliar model as a BUDGET question first.
- **The provider's own claim is the durable signal, not our label.** A
  driver's `reasoning: {mandatory, default_enabled, default_effort}` comes
  from the provider's model list, and `mandatory: true` means the thinking
  cannot be turned off — no parameter makes such a driver answer without
  spending budget on thinking first. The curated row's `thinking` field is
  OURS, is not writable through the API, and defaults to `none`, so it
  agrees with the provider only when someone verified it. Read the claim
  (`provider_model_cache.raw_data`, or the `verify-window` response) before
  trusting the label.

## Checklist before a long-form agent ships

1. The budget is sized for the longest output (measured sizes: the
   observations page).
2. Thinking driver? The budget must cover the thinking PLUS the answer.
3. Run the longest turn once and read the log:

   ```
   grep -E "OUTPUT TRUNCATED|WITHOUT A STOP REASON" backend/logs/app.log
   ```

   A clean run prints neither line. To see the verdict of the last few
   streams instead: `grep "STREAM COMPLETED" backend/logs/app.log | tail -3`.

## Related

- [[dev-notes/agents/agent-provisioning-guidelines|Agent Provisioning Guidelines]] — picking the driver
- [[dev-notes/agents/agent-design-observations|Agent Design Observations]] — the measured cases behind these rules
- [[dev-notes/agents/agent-depth|Agent Depth — the Nomenclature]]
- [[dev-notes/agents/beats|Beats — the agent's own news sweeps]]
