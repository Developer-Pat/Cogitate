---
title: The Workflow Run
type: dev-note
path: wiki/dev-notes/deep-dives/the-workflow-run.md
confidence: verified
created: 2026-10-07
updated: 2026-10-07
tags: [type/dev-note, domain/deep-dives]
---

# The Workflow Run — how an execution's outcome is decided, graded, reclaimed and observed

*A work account. It starts with a run that finished, said so, and had failed — the executions list
green, the detail panel red, for one run at one moment. It ends with two axes instead of a third
status, a grade declared where each failure is caught, a history that reclaims itself, and one
derivable id that ties a run's row, its node spans and its traces to the same name.*

---

## The problem

There was no crash to chase. There was a **disagreement**.

A workflow node that calls an LLM catches its own failure — deliberately, because a monitor must not
die on a dead feed — and returns an error state. The graph then ends *normally*. So the run takes the
same branch as a healthy one and is recorded `completed`, while the node's error survives only inside
the run's own state. The one surface built to name the offender, record the run failed and fire the
notification never runs for the failure it was built for.

The symptom was visible on two surfaces at once, saying opposite things about one run:

```
GET /api/v1/workflows/{id}/status   →  status: "error"   (the checkpoint state)
the same run in /workflows/executions →  status: completed   (the history row)
```

That is the shape of the defect, and it is worth stating precisely because it decides the fix: **the
gap is not a silence, it is a disagreement.** Nothing was missing from the system — a panel spoke, a
list contradicted it, and only one of them was telling the user anything.

### The anatomy, counted

Two paths a node failure can take, and they are not variants of one design:

| the path | who owns it | what the run reads |
|---|---|---|
| the node **raises** (after retries) | the frame's failed branch | `failed` + the offender's name + a toast |
| the node **catches its own error** | the node, alone | `completed` — the node's error stays in the state |

Four surfaces exist for one run, and they read four different things:

| surface | reads | written by |
|---|---|---|
| the detail panel (`/status`) | the **checkpoint state** | the last node's returned state |
| the executions list (`/executions`) | the **history row** | the frame's completion path |
| the notification | the **message bus** | the frame's failed branch only |
| the log | the logger | both the node and the frame |

The census that sized the work, taken over the whole recorded history:

| | count |
|---|---|
| runs ever recorded | **176** — 165 `completed`, 9 `started`, 1 `failed`, 1 `error` |
| times the failed branch has run | **twice** — a closed database, and a sync/async mismatch; both infrastructure, neither reached the provider layer, so neither named anybody |
| the run-level failure surface firing for an **LLM** failure | **never** |
| `completed` rows carrying an error inside their own record | **4**, found by scanning each completed row's debug snapshots for a node whose result holds an error — one of them an LLM connection test that failed on missing credentials |

Four is a floor, not a census: the snapshots keep only the last twenty chunks per row, so an older
swallowed failure is invisible. The point survives the caveat — in the entire history, no LLM failure
had ever escalated to the run.

### Two measured blockers to naming the offender

Both were found by reading and then **measured by execution**; either alone is fatal.

**The exception's identity dies when a node stringifies it.** The gate that decides whether the
provider layer failed works on the exception's own identity — its module, or an attribute only a
provider exception carries. A node's error state holds a *string*. Asked about a string, the gate
answers "not a provider failure" — so a frame reading only the final state's error text can never
name anybody, however hard it looks. The identity must be caught where the exception still exists.

**The resolution that would name the offender does not survive the first node.** The run resolves its
LLM once, at its start, and carries the answer (`llm_resolution`) on its own metadata. But a LangGraph
state key whose TypedDict declares no reducer is **replaced** by whatever a node returns, and every
node builds a fresh metadata object naming a handful of fields. Measured: **47 construction sites** of
that object across the backend (`grep -rn "RunMetadata(" backend/app --include="*.py"`, line-based),
**32** of them in the node modules alone (`nodes/*.py`, nine files), and **zero** of them carry
the resolution. A two-node probe showed the consequence directly — before the first node the
resolution is present; after a node returns, the next node sees `None`, and the run-level statement
returns `None` for a genuine provider failure.

The goal, in the words the item was filed with: *every workflow node swallows its own LLM error, so
the run-level statement and the toast can never fire for the failure they were built for.*

## The vocabulary, before it gets used

The arc runs on a handful of words, and several of them are the reason a reader gets lost.

| term | what it is | who decides it |
|---|---|---|
| **the graph's success** | the graph returned without raising | the graph |
| **the run's outcome** | what the history row records — and these two can disagree | the frame, from the state |
| **the state** | the run's mutable data, held by the checkpointer (its own database, one thread per run) | the nodes, then the frame |
| **the row** | one identity record per run in the execution history — the longest-lived surface | the frame |
| **the snapshots** | a *debug capture* of per-node state updates, kept inside the row's metadata (last 20 chunks). **Not the run's state, despite living in it** | the debug capture path, when enabled |
| **the thread** | the checkpointer's own per-run record — what `/status` reads | the checkpointer |
| **`status`** | the execution outcome: `running` · `completed` · `failed` · `cancelled` · `abandoned` | the frame |
| **`degraded`** | the second, independent axis: this run finished, and it finished badly | the frame, from a node's declaration |
| **a grade** | whether a node's failure is the RUN's failure | declared on the node; the workflow kind supplies the default |
| **`absorb`** | the one call the absorbing grades make — mark the run, or re-raise | the node |
| **the carry** | the run's resolved LLM, resolved once at the start and required to survive every node | the frame at run start; every node thereafter |
| **the raw error** | the exception, on the state's `error` field | the failing node |
| **the statement** | one rendered sentence naming the service that failed, on `failure_statement` (state) and `error_message` (row) | the gate that asks the provider layer |
| **`trace_level`** | the capture mode (`debug` / `release`). It gates CAPTURE only — the graph is identical — but the debug path returns a different object than the state | the request |

Three of those are misnomers the code itself carries, and each one is a mechanism by which two
concepts get mixed:

- **`node_snapshots` is not the run's state.** It is a debug capture stored *inside* the row's
  metadata. Reading it as state is how per-item batch errors were nearly mistaken for run failures.
- **`output_data` is not data on a debug run.** The debug path returns a retry-result object rather
  than the state, and the frame records that object — so every debug row's `output_data` is a memory
  address rendered as text (`<…RetryResult object at 0x…>`), in all 41 debug rows recorded before
  this work.
- **`error` and `error_message` are two different things.** The state's `error` is the raw exception;
  the row's `error_message` is where the rendered sentence goes.

The pairs worth separating once, plainly: **a graph's success is not the run's outcome**; **an
execution outcome is not cleanliness** (`status` and `degraded` are two axes); **a node's own error
text is not the run-level statement** (one is evidence, the other is an accusation that must be
earned); **a preview is not an apply**; and **an offline proof is not an arrival**.

## What was ruled, before any code

| the decision | why |
|---|---|
| **Two axes, not a third status** — `status` stays the execution outcome, and `degraded` + the statement is the second axis | a third status would have to be derived from error *text*, which marks healthy batch runs degraded — their per-item errors are data, not verdicts |
| **Three node grades, declared on the node, the kind supplying the default** | makes the monitor exemption structural instead of a special case: a monitor absorbs because resilience *is* its purpose |
| **A failure is never re-derived onto an old row** — the stuck rows get a truthful status, the swallowed ones stay as history | re-deriving a verdict onto a row nobody recorded one for fabricates it |
| **Retention ships disabled** | a fresh install must never run what its owner did not opt into |
| **The retention windows are config, resolved field by field** | one declaration, and a stale or partial section falls back to the default instead of loosening a window |
| **A destructive verb takes a decision, not a request** — a preview is the default, applying needs an explicit confirmation | the flag is not a gate (any caller can send it); it is the difference between a request that decided and one that arrived |
| **Tracing cannot be the run-status arbiter** | it is keyed, optional, and its flush is asynchronous and batched — the run record must stand alone |
| **One trace per unit of work, its id derived from the unit's own id** | so the run, its node spans and the debug endpoint name the same trace without any of them looking it up |

The build order is the ruling's own order, and it made the work restartable: **the carry first** (a
carried fact cannot be acted on while every node drops it), **then the grades** (the declaration each
node needs), **then the record** (the row and the surfaces). Each landed on its own, pinned by its own
suite, with a control run that fails when its mechanism is removed.

## What we did

### The carry — a key that survives its own writers

The reducer for the run's metadata is the whole of this phase. It reads the *named* fields of an
update and applies two rules: **identity** (the run's id, its template, its start time, its config,
its tags, its capture level, and the resolved LLM) is **carried** — a writer that does not name the
field keeps the run's value; **verdict** (status, error, completion time, attempt count, the
statement) is **replaced** — a writer that does not name the field gets the default, so a later
success still clears an earlier failure. Naming a carried field explicitly clears it, which is the
escape hatch.

The distinction is the design: a node should not have to know the run's identity to report its own
outcome, and it should not be able to silently inherit a verdict it did not make. The 32 node-side
constructions keep working unchanged; what changed is that what they do not mention now survives them.

### The grades — a declaration where the failure is caught

A node's failure is not automatically the run's failure, and only the node can tell the difference.
Each node that catches something declares its grade beside the catch:

| grade | the node's purpose | what the run reads |
|---|---|---|
| `tolerant` | resilience *is* the purpose (the monitor family) | `completed`, clean — no statement |
| `recoverable` | the failure is absorbed, but the product is poorer for it | `completed` + `degraded` + the statement |
| `fatal` | the call *is* the node's purpose (a "verify this connection" template) | the existing failed branch, which names the offender for free |

The declaration is a decorator that returns the same function, so graph wiring is untouched. The grade
answers one question — *when this node fails, is the failure the run's?* — and the answer is never
inferred from the error text: a monitor graded fatal starts failing runs on a dead feed, and a fatal
node graded tolerant records a failed run as clean.

### The record — two axes, and the state corrected to agree

After a graph that ended normally, the frame reads the final state's own declaration (from the
**checkpoint**, because the debug capture path returns a capture object rather than the state) and, if
a node absorbed a failure it did not mean to absorb, records the run as `completed` **and** degraded.
The row gains no column: the flag rides the row's existing metadata and the sentence rides
`error_message`, and the list lifts the flag out so no reader parses JSON.

Two details are the difference between a record and a claim. **The state is corrected**, so a degraded
run does not read `error` on the detail panel while the list shows `completed` — the same disagreement
in the other direction, which the fix would otherwise have introduced. And **the notification fires
whether or not anybody was named**: the run finished and it is worse for it, and an unattended run is
exactly where nobody is watching a panel.

The UI shows the second axis *beside* the status badge rather than folded into the status word — one is
what happened, the other is how well.

### Retention — the three stores, and the windows as data

The run history had grown without limit, in three places at once. Measured before any of it was
reclaimable: **4.85 MB** of snapshots per list request (~95 KB a row, 213 KB on the heavier families)
and **53 checkpoint threads nothing in the app could delete** — a five-minute monitor is 288 runs a
day, about 28 MB of snapshots and 4.3 MB of threads daily.

The policy is a declaration with one default set (disabled; snapshots 7 days, rows and threads 90,
abandoned after 24 hours, hourly maintenance at 03:00), resolved from the settings store field by
field so a partial or hostile section falls back rather than loosening a window. `GET` returns the
effective policy *and* the defaults, because a surface showing a number must be able to say whether it
is the shipped one.

- **Three clocks, because the three things decay differently.** Snapshots go first — they are the
  weight and their value is recent; the row and its thread live months.
- **A preview is the default**, and it measures exactly what the act would while changing nothing.
- **Order: rows, then threads.** A thread without a row is invisible; a row without its thread is a
  lie the UI shows (the detail endpoint 404s for a run the list still lists — measured on two rows
  before this existed).
- **Stuck runs get a name, not a deletion**: a row still `running` past the abandoned window becomes
  `abandoned`, a truthful status update with no completion time, and it does not wait for retention to
  be enabled.
- **The list stops shipping the snapshots** — the row keeps them, the payload drops from megabytes
  to kilobytes.
- **The job is hourly and self-gating**: it reads the policy each time and prunes only in its hour
  when enabled, so changing a setting needs no restart. A maintenance job never fires a workflow and
  records nothing in the history.
- **The surface is a card on the Settings page's Data tab**: the five numbers, the store's own
  readout, a preview, and the prune behind a confirmation that names what dies.

### The observability seam — the id, and the mirror that was deleted

Tracing was the last surface: the one that could show a swallowed failure in a run nobody is
watching. The integration was written for an older version of its SDK and had **never traced
anything** — the version-gap was invisible because the keys were absent, so nothing ever ran to fail.

The census before the repair: **104 matching lines across six files, and five call sites**, reaching
**seven of the manager's fourteen public names**. The other seven had zero callers — and every broken
call lived in that dead half. A 281-line local mirror beside it had **four writers and no reader**: its
three query methods had zero callers anywhere, and the node-tracing decorator was not even wired (no
callers, and async-only against 44 of 45 synchronous node definitions). It was deleted, and a test
pins the deletion — a module that comes back has to come back with a reader.

Three facts from measuring the installed SDK shaped the replacement:

- **The trace id is derivable, not fetchable.** It is the first 32 hex characters of the hash of a
  seed, and the same derivation ties a run's node spans, the run's own record and the debug endpoint
  to one name — computable with no client, no keys and no network. A retried run keeps its id,
  deliberately: a retry is the same run.
- **A trace's attributes ride its spans.** There is no trace object to hang them on: a session, a user
  or a trace name is set by entering a context that applies them to the current span and to everything
  created inside it, or — for a graph run — by reserved keys in the run config's metadata, which the
  callback handler parses.
- **Closing an observation takes no values.** The terminal output, level and status go on with an
  update *before* the end; the end accepts nothing but a time. The old code passed them to the end,
  which raises — silently, into a handler that only printed.

The endpoint that serves a run's trace now answers with the run's own derived id in **both** states,
and takes the UI link from the SDK — which is not a string builder (it resolves the project over the
network), so a failure degrades to the id alone rather than a 500.

One more defect surfaced last, and it was about reachability rather than shape: the adapter read its
credentials from the process environment, while **nothing in the application loads a `.env` file into
the environment** — every other integration in the codebase is a declared setting instead. A key put
in a `.env` enabled *nothing at all*. The settings are declared now, the adapter asks them first and
the environment second, and the resolved switch is handed to the SDK so the app and the SDK cannot
disagree about whether tracing is on.

## How we tested

The instruments, in the order they earned their keep:

- **A population census before any code.** Counting runs by status, then scanning each completed row's
  snapshots, turned "nodes swallow their errors" into "4 rows carry an error, and the failure surface
  has never fired for one".
- **A two-node probe** that measured the carry: the run's resolution present before the first node and
  `None` after it, with the run-level statement returning `None` for a genuine provider failure. That
  probe is why the carry came first.
- **The live disagreement**, read off the running application: one run, `/status` reporting an error
  and the executions list reporting completed.
- **One suite per seam, each with a control run that fails when its mechanism is removed.** The grades
  are pinned by 13 tests, 5 of which fail when the declarations are ignored; the degraded record by 14,
  one of which fails when the frame stops correcting the state; the tracing adapter by 18, with a
  mutation run for each mechanism (the attribute propagation, the handler's trace link, the shared
  derivation) confirming only the tests that assert it go red.
- **The SDK's own witness beats a mock.** The adapter's tests inject a real client built with an
  in-memory span exporter, so the **exported spans** are the application's actual output — the ids,
  the sessions, the node linking — with no keys and no network. A test that creates a client per test
  also discriminates a handler built without its public key, which silently drops every span.
- **Attribution from artifacts instead of a re-run.** When a suite reported a different skip count than
  the run before it, comparing the two runs' machine-readable reports named the ten tests — and the
  cause, a health gate racing its own run — without re-running anything.
- **The running application, driven.** A live chat turn (streaming, tools, the deep-pass router, the
  title service, memory) completed normally with the new tracing wrapper in place; the debug endpoint
  answered with the new shape; the retention card showed the store's own readout.
- **Pre-existing failures proven, not assumed.** Two tests failed in one tier when it ran in a single
  process. Checking the tree out at the commit *before* the work and running the same tier reproduced
  them exactly, which is the difference between "my change broke this" and "this predates me".

## Lessons learned

- **A swallowed failure is a disagreement, not a silence.** The symptom was two surfaces contradicting
  each other; a fix aimed at the silence would have added a notification and left the list green.
- **Two axes beat a third status.** Any status derived from error *text* is wrong for the families
  whose errors are per-item data — and a status cannot be un-said, while a flag beside it can.
- **A state key with no reducer is replaced, not merged.** That single LangGraph rule is how a
  carefully carried fact dies on the first node, and it is invisible in the writing node's code.
- **An exception's identity dies when it is stringified.** Whoever wants to name the offender must
  catch the exception while it is still an exception.
- **Declare the grade where the catch is.** A default inferred from the kind is a policy; a grade
  inferred from the error text is a guess.
- **Read the outcome from the store, not the return value.** One capture path returns a different
  object than the state, so a verdict read from a return value is silently absent exactly when the
  capture is on.
- **Correct the state when you correct the record,** or the surfaces swap which one is lying.
- **A destructive act takes a decision, not a request** — the confirmation flag is not a gate, it is
  the difference between a request that decided and one that arrived.
- **Delete the row before its thread.** A thread without a row is invisible; a row without its thread
  is a lie the UI shows.
- **A name can be truthful without being a deletion.** `abandoned` says exactly what happened; a row
  that is quietly removed says nothing.
- **A count with no pattern beside it is not a measurement.** The same family measured with a broader
  search gives a different number, and the two are not comparable.
- **A field that looks like data may be an address.** Every debug row's output field held a rendered
  object reference, because the capture path returns a wrapper the frame records verbatim.
- **Four writers and no reader is not a feature.** The local trace mirror looked like observability
  and was a second, dead copy; the question to ask of a store is who reads it.
- **A derivable id ties two systems without a lookup.** Two sides that hash the same seed agree
  forever, and one of them can be a debug endpoint holding nothing but a string.
- **The SDK's own witness beats a mock.** A fake client restates the code; the SDK's in-memory
  exporter reports what the app actually sent.
- **Credentials must be reachable, not merely declared.** A secret that only the process environment
  can carry is unreachable in an application that loads its configuration from a file.
- **Say which half a proof covers.** The call shapes are provable with no keys and no network; that
  traces *arrive* is not — and a pass that has not established arrival must say so.

## Where it stands

- **The run's record** — `status` for the execution outcome, `degraded` + the statement as the second
  axis, the flag in the row's metadata, the sentence in `error_message`, and the state corrected so
  the detail panel and the list agree. Surfaces: `GET /workflows/executions`, `GET
  /workflows/{id}/status`, the run panel's second chip, the degraded notification.
- **The grades** — declared per node in `workflows/error_handling/grades.py`, with `absorb` as the one
  call and the kind supplying the family default.
- **The carry** — the metadata reducer in `workflows/state/workflow_state.py`: identity carried,
  verdict replaced.
- **Retention** — `workflows/retention.py`, `GET/PUT /workflows/retention`, the prune endpoint with
  its preview default and its confirmation, the hourly self-gating maintenance job, and the card on
  the Settings page's Data tab.
- **Tracing** — one seam in `workflows/observability/langfuse_config.py`, one trace per chat turn and
  per run, the run's id derived from the run's own id, the graph linked by trace context plus the
  reserved metadata keys, and `GET /workflows/{id}/debug/trace` answering with the run's derived id
  whether or not tracing is on.
- **What is not established here, and is stated rather than implied:** this installation holds no
  tracing keys, so no trace has been sent from it. The call shapes, the ids, the sessions and the node
  linking are pinned by tests that read the SDK's own exported spans; whether traces **arrive** with
  the right session and the right node spans is the half that needs keys, and it is the only claim
  this account does not make.

### Checkable

```bash
# the record's two axes, and the store's own readout
curl -s "http://localhost:8000/api/v1/workflows/executions" | head -c 400
curl -s "http://localhost:8000/api/v1/workflows/retention"

# the run's trace, named by the id its own spans carry (works with tracing off too)
curl -s "http://localhost:8000/api/v1/workflows/<workflow_id>/debug/trace"

# the tests that pin each mechanism, with their control runs
uv run pytest backend/tests/workflows/test_node_grades.py -q
uv run pytest backend/tests/workflows/test_degraded_runs.py -q
uv run pytest backend/tests/workflows/test_retention.py -q
uv run pytest backend/tests/unit/test_langfuse_v4_adapter.py -q
```
