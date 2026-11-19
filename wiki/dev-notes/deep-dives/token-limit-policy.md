---
title: The Token-Limit Policy
type: dev-note
path: wiki/dev-notes/deep-dives/token-limit-policy.md
confidence: verified
created: 2026-09-21
updated: 2026-09-25
tags: [type/dev-note, domain/deep-dives]
---

# The Token-Limit Policy — how a turn's budget is decided, spent, and reported

*The account of an arc. It starts with an answer that stopped mid-sentence and ends with one place
that decides what an agent may spend, a vocabulary for what a turn crossed, and a plug that keeps
the work.*

---

## The problem

The first symptom was small and easy to misread: a long answer arrived cut off in the middle of a
sentence and the app presented it as complete. Nothing in the transcript, the log or the UI said
otherwise. A fix went in for the reporting half of that — the stream now reads the provider's
`finish_reason` and marks a cut answer `truncated: true`, so a truncated answer can no longer pass
for a whole one. That made the cut visible. It did not explain it.

The explanation took a dig, and the dig ended in a sentence that reframed everything:
**the budget is advisory, and nobody can see which number was sent.** That is not a missing knob.
It is a missing policy, and the study that followed found three reasons why.

**Four budgets, decided in four unrelated places.** A request is governed by the model's context
window (recorded in the **model catalogue** — our own curated list of recommended models, carrying
each entry's declared window and thinking level; used only by the model matcher, never at request
time), the input
assembly (`DEFAULT_MAX_CONTEXT_TOKENS = 16000`, a constant with no relationship to the model), the
output budget (`max_tokens`, the only one the provider enforces), and a scatter of result and
rendering caps. Only the third one stops an answer — and it was the least coherent of the four.

**Seven writers for one number.** The output budget the app actually sent could come from the
agent's stored parameters, the executor's profile caps (512 for `fast`, 1024 for a hybrid turn's
first pass), the deep pass's forced 4096, a fallback when nothing was declared, the reasoning
floor, a per-session runtime override, or one of the auxiliary callers — the title service, memory
extraction, compaction, the health checks — each with its own number in its own file. A shallow
agent that declared 2000 ran **1024** on the first pass and **4096** on the deep pass. The profile
page showed 2000. Nothing anywhere said which one had been sent.

**"High thinking" was declared, never verified.** The catalogue and the agent package both carry a
`thinking` level, and the model matcher uses it — but the catalogue is our **curation** layer (what we
recommend), separate from what the provider actually offers, so an entry can disagree with both the
provider and the model's own behaviour. The budget floor therefore could not trust it, because
`inclusionai/ling-3.0-flash` is catalogued `thinking: none` and demonstrably streams reasoning
tokens. Thinking spends the same budget as answering: a thinking driver given 4000 tokens returned
`out_tokens=4000` and an **empty answer**, while the same driver at 16000 answered every step.

The measurement that sized the fix was concrete: a ten-day forecast table (seven columns, ten rows)
plus a summary needs roughly **2,100 output tokens**. At 2000 it arrived cut mid-table, in a stream
that said `truncated: true`, and the answer was unusable — a generous budget costs less than a
ruined answer, and this one had been ruined by a number nobody could see.

So the arc had a plain-words goal: *one place decides how much an agent may spend producing an
answer; the number that runs is the number we log, show and can check; every agent type gets limits
sized to its job, generous, because a cut-off answer is worse than a big bill; and when an agent
does go off the rails the app says so in the log and in chat, then pulls the plug with an error
rather than letting it loop.*

---

## The vocabulary, before it gets used

The arc runs on eight words, and three of them are easily confused with each other. Everything after
this section uses them in the senses defined here.

| Word | What it is | Who decides it |
|---|---|---|
| **the model's context window** | The driver's total capacity — prompt **plus** answer, in tokens. A fact about the model, e.g. `262144` for the working driver, `8192` for a small one, **unknown** for a driver nobody has recorded. | Nobody here. We **read** it (the catalogue's curated row first, else the provider's own discovered claim) and use it only as a bound. |
| **the prompt** (the input) | Everything sent to the model: system prompt, tool schemas, conversation history, the user's message. | The assembly (see below), plus whoever wrote the persona and the tools. |
| **the output budget** | The `max_tokens` sent with a request — the ceiling on the **answer's** tokens, thinking included. The only number the provider itself enforces: exceeding it cuts the stream. | The resolver, from the declaration → the path's policy → the floor. |
| **the input budget** (the assembly ceiling) | The app's own cap on how much **history** goes into the prompt. **This is not the window**, which is the trap the old name set: the constant was called `DEFAULT_MAX_CONTEXT_TOKENS` and read as the model's window, when it was only ever our assembly's ceiling. | The app policy (`16000`), lowered by the window when the driver cannot hold it. |
| **the headroom** | A small reserve (`512`) subtracted while assembling, for the reply. | The assembly constant. |
| **the floor** | A minimum a budget may not go below. The **thinking floor** (`16000`) exists because a reasoning driver given less spends it all thinking and answers nothing; the deep pass has a floor of its own (`4096`). | Policy. A floor **raises**. |
| **the clamp** | A **lowering** forced by a bound. Today exactly one thing clamps: the window, when prompt + budget would exceed it (`reason='window_clamp'`). | Physics (`roadmap` §2) — the only limit allowed to lower a budget we chose. |
| **the ceiling** | Two senses, kept apart: the **derived ceiling** is *policy* — one number derived from the per-type table, bounding what the UI, the API and the resolver will accept, so a typo of `200000` cannot reach a provider. The **window as a ceiling** is *physics* — an upper bound over the input budget that only lowers it. | Policy (derived) vs the driver (window). |
| **a limit** | One policy number with a **reason that is enforced at construction**. **Soft** means the log line and the user are told and nothing stops; **hard** means the turn stops, the partial answer is kept and the user is told. **Scope** is `call` (one provider call) or `turn` (everything the turn spent). A limit that cannot be judged yet is declared **inactive** and says so, with its reason — so a reader can tell "nothing is near a line" from "nothing is watching". | The policy, judged in one place. |
| **the path** | Which run a call is: `default`, `fast`, a hybrid turn's `pass1`, or the conduit's `deep` pass. **Not the agent's type** — today the path decides the number and the type decides nothing, which is exactly what the ladder changes. | The executor profile and the conduit. |
| **declared vs effective** | The **declared** budget is what the agent or package stores; the **effective** budget is the number actually put on the wire, and it is the one logged (`max_tokens_sent=… reason=… declared=… path=…`). Usually equal now; where they differ, the reason says who moved it. | The resolver, and the log is the proof. |
| **the ladder** | The seeded per-type budget table: lesser agents `4096`, shallow (Bob's class) `8192`, deep `16384–24576`, **doubled** for a driver that thinks. Deliberately generous defaults, corrected by real turns rather than a measurement phase (D5). | The policy — with the running app as the instrument that corrects it. |
| **truncated** | What the app reports when the provider cut the answer at the budget (`finish_reason=length`). Visible on the message and the saved row. | The provider, reported by us. |
| **the characterization table** | The test that records **every budget the app sends**, per type, profile and path — written before anything moved, so a later phase's diff can only be the rows someone meant to change. | The tests. |

**Where a floor is a SELECTION rule rather than a budget one.** `min_context` on an agent's
`llm_spec` filters the substitution matcher's candidates (`curated_models_service.match_spec`), and
a row whose window is **unrecorded is not offered** against a stated floor: the floor is a `>=`
claim, "unknown" is not a number that satisfies it, and the exclusion is logged
(`NOT OFFERED — … whose context window is not recorded`) so it is never silent. The Model Browser's
own context filter reads unknown as `0` and excludes it the same way. With **no** floor there is
nothing to prove and such a row is offered, with the window-fit warning as the honest state.

**The three traps, stated once:** the **input budget is not the window** (one is our ceiling, the other
is the driver's capacity); **a clamp is not a cap and not a floor** (a clamp lowers to fit physics, a cap
is a policy we chose, a floor raises to protect an answer); and **the path is not the type** (the executor
profile decides the number today; the agent's type will, once the ladder lands).

---

## The roadmap

Two things shaped the plan before any code was written.

**The policy was settled first, in a conversation.** Nine decisions were put to the user and ruled
on — a gate, with no code on the other side of it, because each one changes the shape of the work
that follows. They are known by their tags, **D1–D9**: *D* for **decision**, not to be confused with
the **P1–P9** in the study beside them, which were the *policies* the analysis derived — what we
could do, against what we ruled we would do. The tags are not private notation: the code and its
tests cite them (`limits.py` names `D5`, `D7`, `D8`), so this account keeps them. In one line each:

| # | Ruling |
|---|---|
| D1 | `fast` keeps a **declared, named, logged** policy constant — answering briefly is a legitimate profile choice. A hybrid turn's **first pass raises to the declared budget**, because a second pass meant to be the better one must not run on a quarter budget. |
| D2 | The package's `llm_spec` declares the **type default**; the agent's own `parameters` override it; the resolver reads both. A new agent gets a sane budget without anyone typing one. |
| D3 | **One ceiling**, derived from the type table rather than typed twice, shared by the UI bound, the API validation and the resolver — so a typo of `200000` cannot reach a provider. |
| D4 | The `/configuration` page is **removed** — a static mock, hardcoded inputs, nothing wired. |
| D5 | **There is no measurement pass.** Seed the ladder from the class that has a real measurement, then let real-world logging and chat messages correct it — *"if we get the limits wrong the system should complain loudly"*. The loudness of the limits **is** the measurement mechanism. |
| D6 | The stale deep-pass module is **deleted**. It looked like the same logic and was an earlier snapshot: no tool loop, no reasoning replay, no replace-over-append. Making it live would have regressed three already-paid-for fixes. |
| D7 | A hard plug **aborts the stream, emits `event: error`, keeps the partial answer**, and speaks in the tool guard's tone. Where the plug fires between iterations and the answer is nearly complete, it **finishes the answer and then stops**. |
| D8 | Cost limits are **declared INACTIVE** until pricing is verified, and the log says so — an active limit measuring $0 is a guard that does nothing while claiming to. |
| D9 | A window too small for the type's budget is **allowed**, the budget clamps to the window with `reason='window_clamp'`, and the mismatch warns at match time — because the catalogue's window data is not yet trustworthy, and refusing would fail working agents on bad data. |

**The build order put a safety net under the risky work.** Phase A removed dead code and one stale
page — no behaviour change, so nothing a decision governed blocked it. Phase B built the policy
core: the limit model, the resolver, the effective-budget log line, the tool guard re-expressed as
one more limit, and — the piece that mattered most — **a characterization table** recording every
budget the app sent, as it was, before anything moved. Phase C then did the dangerous refactor
behind that table: every path forced through the resolver, the silent caps deleted. Phase D added
the behaviour on top: the turn's account, then the soft lines, then the hard plug. The plan's tail
covers the input side derived from the window, the declaration surface with per-type defaults, and
one view that shows a declared budget against the effective one.

The structural rule that made the whole arc restartable was written into the plan before C started:
**from the moment the characterization table exists, every later phase is interruptible.** "Is the
tree as the roadmap says?" became a test run rather than a memory — which is what allowed a refactor
spread across eight commits and several sessions to be stopped, resumed and re-scoped without drift.

---

## What we did

### A — the dispositions (`b884489b`)

Dead code out, in both directions: a stale duplicate of the deep pass deleted (the D6 ruling above —
its survival would have regressed three fixes), the `/configuration` page, its route, its nav entry
and its types file removed, and a real bug fixed in the tool guard's **call site**, where the wrong
argument shape meant the guard's own limits were not the ones being applied. Nothing here changed
behaviour on purpose; it changed what was left to maintain.

### B — the policy core (`188cf52c`, `b967c55b`, `b83f5f0d`)

**One shape and one judge.** Every limit is a `Limit` — key, kind (`soft`/`hard`), scope
(`call`/`turn`), threshold, and a **reason that is enforced at construction**: a limit without a
reason cannot be built, because the reason is what reaches the log line and the user verbatim. One
function judges them all (`check_limits`). The comparison is `value >= threshold`, and an
unmeasurable quantity is **skipped rather than treated as a breach** — a missing measurement is not
a limit.

**The resolver.** `resolve_output_budget()` took the seven writers and made one decision:
runtime override → the agent's declared budget → the router's fallback, then the path's policy,
then the thinking floor. `apply_output_budget()` is that decision plus the write and the log line,
and every path calls it. The rules it enforces are the ones the study argued for: never below the
floor; never below the declared value unless the window forces it (and then the reason says so); a
path may **raise** with a reason; an unknown window never silently lowers a budget.

**One line that answers the original question.** Every call now logs
`💰 EFFECTIVE OUTPUT BUDGET max_tokens_sent=… reason=… declared=… path=… model=… session=…`, where
`reason` is one of `declared`, `runtime_override`, `no_declared_budget`, `fast_policy`, `deep_min` or
`thinking_floor` — each a named constant beside the code that sets it. A budget question is now
answered by reading the log rather than by reading the profile and guessing.

**The tool guard became a limit.** `ToolCallTracker` already warned one call before blocking, then
blocked with a message — the same soft/hard shape with different quantities. It now publishes its
own ceilings as `Limit` objects (`limits_for()`), so a blocked tool call reports as a limit verdict
and there is no third mechanism to keep in step.

**The characterization table** (`tests/unit/test_output_budget_table.py`) records every budget the
app sends — per limit type, per profile, per path — as a parametrized table. It is a description of
today's behaviour, not an aspiration; from B onward it is both the refactor guard and the arc's
resume point.

### C — one writer (`e09472f9`, `432df193`, `2315d25b`, `0a5b5227`)

Every remaining writer was put on the resolver: the router's paths, the completion service, the
chat delegate, the deep pass, the auxiliary callers. Then the silent overrides died.

The executor's profile caps went: `fast` became a **named policy** constant on the resolver's path
table rather than an executor's private cap, and a hybrid turn's first pass began running at the
**declared** budget instead of 1024. The deep pass stopped **forcing** 4096 and started taking the
larger of the declaration and its own minimum — so a raised declaration reaches both passes, and a
small one is lifted rather than shrunk. The reasoning floor dropped to a single site.

Finally, the refactor was made **self-policing**: a source guard fails the suite if a path starts
deciding its own budget again (`tests/unit/test_one_budget_writer.py`), because the failure mode
this whole arc exists to kill is exactly the ease of typing one more number in one more file.

### D — the ladder: the account, the soft lines, the hard plug

**D.1 — the turn's account** (`1f890d37`, `19b95bb5`). `TurnState` carries what a turn spent —
provider calls, tool calls, tokens in and out, elapsed time, the paths it ran — using the attribute
names the limit judge already read, so no adapter layer was needed. Provider calls are counted
**before** they are made (a call that dies still counts), tool calls are mirrored from the tracker
so there is one count rather than two, and a provider that reports no usage gets the app's estimate
**marked as one**. The account is reported from the stream's `finally`, so a turn that died still
reports itself, and it prints as a single greppable line: `🧮 TURN ACCOUNT … provider_calls=…
tools_offered=… tool_calls=… tool_calls_blocked=… tool_failures=… tokens_out=… elapsed_s=… paths=…`.
A source guard refuses an uncounted provider call. The four tool fields are the arc's later addition:
the **offers** are the denominator that separates a model which declined a tool from one that was
never offered one, the **blocked** count is the guard's own refusals (never among the calls that
happened), and the **failures** are the calls that ran and did not succeed — grouped by class in the
saved row's `tool_call_summary`.

**D.2 — the soft lines** (`1af34efa`, `b61fb88b`, `8b67a086`). The armed set: provider calls 8, tool
calls 20, wall clock 300 s (turn-scoped) and output tokens at 90 % of the **call's** budget. The
call-scoped quantities are judged by their own function, so a call's threshold can never be judged
against the turn's totals — the bug that makes a percentage limit useless. A crossing goes three
places: the log (every breach), the toast (**once per threshold per turn** — a five-iteration turn
must not toast five times), and the message, as `metadata.limits` plus the sentence in
`metadata.limit_notice`, riding both the stream's `done` frame and the saved row so the note
survives a reload.

**D.3/D.4 — the hard lines and the plug** (`c3c3d1e1`, `9f96700a`, `b40d4b45`). Provider calls 12
and wall clock 600 s are the hard pair. A crossing is judged at three boundaries — the loop's call
boundary, the deep pass's call boundary, and the turn's end — and the stop is one function:

1. the crossing is **recorded on the turn's account**, so the note on the message and a reloaded row
   both read it;
2. one log line writes it (`🚫 TURN STOPPED key=… value=… threshold=… reason=… partial=… stage=…
   mode=…`);
3. the stream emits `event: error` with `type=limit_stop`, in the tool guard's tone, ending with
   *"Say 'continue' and I'll carry on from what I have."*

Two outcomes, and the difference is the user's: **`abort`** when something was still to do, which
stops the turn and keeps what already arrived; **`finish`** when nothing was left to start or the
answer was nearly complete, which keeps the answer **whole** and lets the turn end normally with
only the note saying a plug fired.

**D.5 — the limit that says it is not there** (`91ac042c`). Cost limits stay inactive, and
`calculate_cost` now says `cost limit inactive (pricing unverified)` at the moment it falls back to
$0 for an unpriced model — because a $0 measurement is not a limit that passed. The turn's own
census declares the same fact with its reason, so the two agree by test.

**The budget raised where it mattered** (`b0a669f5`). With one writer in place, a raised number
actually reaches the wire: the class that had a real measurement — the long-form news agent whose
forecast was cut at 2000 — went to **8192**, and a real long-form turn then streamed
`max_tokens_sent=8192 reason=declared` on **both** passes (no longer `deep_min` 4096), 907 tokens,
complete, with no budget mismatch. Because a budget is behaviour, the characterization table moved
in the same commit, and the duplicate ladder rows collapsed into the anchor.

### F — the declaration and the defaults (`19616dc5`, `9f8674d1`)

**A budget stopped being a number someone types.** The ladder became code constants (`TYPE_BUDGETS`:
4096 lesser / 8192 shallow / 16384 deep / 24576 deep-long, ×2 for a thinking driver) and the
**ceiling is DERIVED from that table** (`max × 2 = 49152`) rather than typed a second time — it now
bounds the runtime config, the agent create/update/template validators and agent versioning, while a
legacy row above it stays readable. A package's `llm_spec.max_output` IS the declaration the resolver
reads — one slot, copied onto the agent at adoption, so a new agent gets a sane budget with nobody
typing one. And
`thinking` became a **chain of evidence** — the provider's own claim → our curated label → the agent's
own declaration → the name list — with the claim's level WRITTEN back onto the row, which is how two
mislabelled rows were corrected in one call each. **Why it was needed:** a live case arrived mid-arc
where the provider published `reasoning: {mandatory: true, default_effort: "max"}` while our own row
said `thinking: none`, and its session held four dead turns.

### G.3/G.4 — the numbers became checkable (`6a02a95c`)

The design note gained a numbers table whose `Where` column names the constant each value lives in, and
a test (`test_budget_docs_table.py`) reads those constants and fails the note when one moves. The
observations note gained the arc's measured rows, including the two live cases above.

### The turn's own numbers get one home (`c5f24a98`, `4923b2e0`)

The numbers that shape a turn's WORK and are judged by nothing — neither a budget (what a call may
spend) nor a limit (a quantity that is judged, with the sentence it tells the user). The tool loop's
rounds ran as **three** bare literals in one file (the main loop, the deep pass, and the delegate
endpoint — the third found only when the second sweep ran), the four timeouts sat at their call sites,
and the retry policy lived under two names no page carried. They are declared in `turn_config` now and
reached through **function calls**, so the source behind a number can change without a call site
moving — the shape `Paths` already has for paths. The tool guard's own ceilings deliberately stayed with
the guard: the arc's C.4 ruling made its defaults the policy there, and a second copy would be a second
plug on one event.

**The literature** (`6a02a95c`). The arc's durable output is a dev note — *Turn Limits and Budgets* —
covering the one decision point, the limit model, what a crossing does (frame, order, note, partial,
and the sentence a turn owes when it produces nothing), and **the log lines to check any of it by**.
The design note gained a numbers table **read from the constants and pinned back to them**, and the
observations note gained rows measured in the running app.

---

## How we tested

Four instruments, in the order they earned their keep.

**The characterization table.** Written before the refactor, it records every budget the app sends.
Its value is not that it asserts what we want; it is that it **asserts what is** — so the dangerous
phase could be stopped and resumed, and any later behaviour change has to move a row and say so. It
is also the arc's resume point: run it and you know whether the tree is as described.

**Source guards for the invariants that a unit test cannot catch.** "One writer" is not a value a
function returns; it is a property of the codebase. So a guard fails the suite if a path starts
deciding its own budget, and another refuses an uncounted provider call. Both were proved by
planting the violation and watching them fail — a guard that has never failed is a guard nobody has
tested.

**The standing gates.** The unit group (~1,200 tests), the UI group (~950), `tsc -b`, the system
sweep's sixteen checks, and the wiki validator (frontmatter, stale names, wikilinks, codebase sync,
mermaid fences) after any wiki move. Nothing landed on a red run.

**The running app, which found what the tests could not.** The tests prove the plug's mechanism;
only a real turn shows what it is like to be on the other end of it. Four defects came out of driving
the app:

1. **The armed numbers are unreachable by a normal turn.** A turn's ordinary work ends at the tool
   loop — its rounds plus the answer pass that follows them, six provider calls at most — so a
   `provider_calls` line at 12 fires only on a retry storm (a rate-limited call retries
   up to three times) or on the 600 s clock. That is a legitimate thing for a limit to be — a
   runaway detector — but the phase's own checkpoint had implied a line a long turn would approach,
   so the written claim was corrected to match the mechanism.
2. **An aborted turn that had produced nothing stranded the session.** Zero assistant rows, the
   bubble stuck on "Thinking", Send disabled: the empty-message guard was refusing to persist an
   empty answer, which is correct, and leaving the user with silence, which is not. A turn that
   stops without an answer now persists the reason as the message.
3. **The tool loop's own cap was a silent stop.** Same shape, different cause: the turn ended with
   nothing said. Silence is the defect class this arc was built to end, wherever it comes from. **Its
   fix came after the arc closed, and it is the largest thing this list produced**: when the loop's
   last round comes back with tool calls, that round's tools run and the turn is then asked for its
   ANSWER — one more call with the tools withheld, carrying the instruction that the collected results
   are everything there is. Four turns of one session had spent 249,377 input tokens and 77 tool calls
   to produce a sentence about their own limits; the same shape now writes the answer from the work it
   already paid for, and logs `tokens_out=163` where the old path logged `tokens_out=0`.
4. **The note rendered collapsed and did not survive a reload.** It was inside the chat footer,
   measured at 65 × 418 px instead of the 641 × 50 px a note needs, and — separately — the
   response schema whitelisted message metadata away, so the sentence vanished on the next load
   while the `done` frame had shown it.

A forced case covered what the app cannot be asked to do on demand: the hard thresholds were
lowered temporarily to prove both branches of the plug — the abort keeping a partial answer and
writing its row, the finish keeping the answer whole — then restored, and the live turn re-run to
confirm the shipped constants.

Two disciplines around the testing are part of the record. **Where a claim is a number, it was
measured rather than argued** — the note's defect was a screenshot and a pixel measurement, not an
opinion about layout. And **where a fact could not be established, the caveat travelled with the
change**: the catalogue's `context_length` for the working model is NULL, so the raise is recorded
as *a declaration the provider accepts*, not a window-verified number.

---

## Lessons learned

**A guard that judges nothing must say so.** The cost limit was measuring $0 for every call and
passing every time. The ruling that fixed the shape of this — declared inactive, with the reason in
the log — is the general rule: an inactive limit that looks like a passing measurement is worse than
no limit, because it manufactures confidence. `$0` is not evidence of frugality.

**Know whether you built a detector or a calibration line.** A hard limit at 12 calls when the loop
caps at 5 is a retry-storm detector. That is useful — but it is not a line a long turn approaches,
and describing it as one would have been a lie the first time someone tried to reason about it. The
number's job has to be stated, not assumed from its magnitude.

**Silence is the defect class, wherever it comes from.** The empty guard, the loop's cap, and the
plug's first version all produced the same user experience: a spinner and nothing else. A turn that
ends without an answer owes the user a sentence, and that sentence has to be **persisted**, not just
streamed, or a reload turns it back into silence.

**The number that runs must be the number logged, and there must be one writer.** Seven writers was
not a tuning problem — it made every other statement about budgets unfalsifiable. The moment one
function owned the decision, the original question ("which number was sent?") became a log line, and
a raised budget started working. Every additional writer is a silent override waiting for an author
who means well.

**Pin behaviour in a table before you refactor it.** A characterization table that states what the
code does *today* is what turns a multi-session refactor into something that can be stopped, resumed
and re-scoped. It is not a safety net for the limits; it is a safety net for the refactor.

**A frame the user must see goes out before the frame that ends the stream.** The sentence a stopped
turn owes cannot be emitted after `event: error`, because the frontend stops reading there. Order of
emission is behaviour, not implementation detail.

**A whitelisting response model drops fields silently.** The limit note was in the message metadata,
in the stream, and on the screen — and gone after a reload, because the persisted-row schema lists
the fields it carries. Any field that rides metadata needs every mapper to carry it, and the failure
is invisible until someone reloads.

**Numbers in prose drift; pin them to the code.** The design note described a budget ladder that the
code had outgrown. The fix was not a careful edit but a test that reads the constants and fails the
note when one moves — because "the doc says 2000" is only trustworthy if something breaks when the
code says otherwise.

**A declaration is not evidence.** The catalogue says `thinking: none` for a driver that streams
reasoning tokens; a thinking driver given its class budget returned an empty answer because thinking
spends the same tokens as answering. Declared metadata is a hint for matching, never a fact for
budgeting.

**Be generous, and make a wrong limit loud.** A cut-off answer costs more than a big bill, and the
only real measurement here was a user's ruined output. When the numbers are deliberately generous,
the way to find the wrong ones is not a measurement phase — it is honouring D5's rule that a wrong
limit complains: it either truncates visibly or it fires a named line. Never a silent cut, never a
silent clamp.

**Drive the app.** Four defects in this arc were invisible to a green test suite and obvious within
one turn of using the thing: an unreachable threshold, two silent stops, a collapsed note and a lost
one. Tests prove the mechanism; the app produces the behaviour.

---

## Where it stands

One module decides a turn's output budget, and every path goes through it. Every limit names its
reason, and the reason reaches the log and the user verbatim. A turn reports what it spent on a
single greppable line. Soft lines persist a note beside the answer; a hard line stops the turn,
keeps the work, and explains itself in the guard's own voice. Nothing that can cut an answer does so
quietly — a truncation is labelled, a clamp names itself, and a limit that is not watching says so.
**A tool-heavy turn that uses every round it has is not silenced either**: the loop asks for the
answer with the tools withheld, so the work it collected becomes the answer. And the numbers that
shape that turn — its rounds, its waits, its retry policy — are declared in ONE place
(`turn_config`) and reached through calls, so changing one is a change of source rather than a sweep
of call sites.

The checkable surface: `wiki/dev-notes/agents/turn-limits-and-budgets.md` (the model, the loop's
ending, and the log lines), `tests/unit/test_output_budget_table.py` (every budget the app sends),
`tests/unit/test_hard_limit_stop.py` (the plug through the real stream),
`tests/unit/test_answer_pass.py` (the turn that runs out of rounds, answered instead of silenced), and
`tests/unit/test_one_budget_writer.py` (the invariant that keeps it true).

---

## Appendix — the gate's decisions, verbatim

**Why this is here.** The tracked code and tests cite this arc's decision tags — `D1`–`D9`, plus the
step forms (`C.1`, `C.2`, `D7 (a)`) — in **135 lines across 12 tracked files**, and one of those
citations reached the app's own log output (`calculate_cost: … cost limit inactive (pricing
unverified)`). The definitions lived only in the arc's roadmap, which is untracked, so every citation
pointed outside the repository. This appendix is the key: the gate's rulings, copied verbatim from
`local/token-limits/roadmap.md` §9. **Paths and branch names inside the quoted table point at `local/` —
they are part of the quoted text, not links this page maintains.**

| # | Decision | RESOLVED | Why |
|---|---|---|---|
| **D1** | The executor caps (fast 512 / hybrid pass-1 1024) | **(a)** `fast` keeps a declared, named, logged policy constant; `hybrid` pass 1 RAISES to the declared budget | `fast` answering briefly is a legitimate profile choice; a second pass that is meant to be the *better* one must not run on a quarter budget — and the deep pass overwrote it anyway |
| **D2** | Where the budget lives | **(a)** the package `llm_spec` declares the TYPE default → the agent's `parameters` overrides it → the resolver reads both. The per-session `runtime_configs` override stays, but routes through the resolver — never a bypass | it matches how `thinking`/`min_context` already work, and a NEW agent gets a sane budget without anyone typing one |
| **D3** | A server-side ceiling | **(a)** yes: ONE constant, shared by the UI bound, the API validation and the resolver, **derived from the type table** (its largest budget) rather than typed twice; per-type soft/hard limits do the real work. **Note:** the lean's literal "1–8192" cannot stand beside the ladder — 8192 is now a *class* budget, so the derived ceiling is the deep class's top | a typo of `200000` must not reach a provider, and the OpenAI-compatible `/chat/completions` surface (which has no agent type) needs an absolute bound |
| **D4** | `/configuration` page | **(a) REMOVE** — page, route, nav entry, and its `types/configuration.ts` | a static mock: hardcoded inputs, no state, no API call; nothing on it is wired, and its subject matter now lives on the profile and provider pages |
| **D5** | Which agent types get measured before defaults are set | **AMENDED — there is no measurement pass.** Seed the ladder (§1) from Bob's class, then let **real-world logging and chat messages** correct it; the class order stays shallow → deep, but the instrument is the running app | the user's ruling: *"the best data will have to come from real world logging and messages… if we get the limits wrong the system should complain loudly"* — so the loudness of the limits IS the measurement mechanism |
| **D6** | The deep pass | **(b) RE-RULED at A.3: delete the stale module + its test.** The ruled (a) rested on the module being "the same logic"; it is an EARLIER SNAPSHOT — no tool loop (the turn-death fix), no reasoning replay, no replace-over-append (the double-glitch fix) — so making it live would have regressed three paid-for fixes. One implementation either way; the copy that survives is the router's current code | the evidence is in `phases/a-dispositions.md` Step 3 |
| **D7** | The hard plug's semantics | **(a)** budget/clock plugs abort the stream, emit `event: error`, KEEP the partial answer and tell the user in the tool guard's tone; **(b)** "let it finish, then stop" where the plug fires between iterations and the answer is nearly complete | the tool guard already does exactly this for tool loops, and its message persists as a real assistant turn — the user is never left with silence |
| **D8** | Cost limits | **(b)** declared **INACTIVE** until pricing is verified, and the log says so | an active limit measuring $0 is a guard that does nothing while claiming to; `calculate_cost` currently logs `no pricing for model=… — treating as $0` |
| **D9** | A window too small for the type's budget | **(b)** allow, clamp the budget to the window (`reason='window_clamp'`, logged), warn at match time | the catalog's window data is not trustworthy yet, so a refusal would fail working agents on bad data; provisioning is where it gets fixed |

The table is quoted unchanged, because it is the thing the citations point at. Where the build overtook
a row, the account above is the current record — and the code comments keep the tag as a trailing
pointer to this key rather than restating the rule.
