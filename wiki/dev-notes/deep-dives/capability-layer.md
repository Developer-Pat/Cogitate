---
title: The Capability Layer
type: dev-note
path: wiki/dev-notes/deep-dives/capability-layer.md
confidence: verified
created: 2026-10-05
updated: 2026-10-05
tags: [type/dev-note, domain/deep-dives]
---

# The Capability Layer — how the app decides which service answers

*A work account. It starts with a question the app could not answer — "which service is my title
using?" — and ends with one resolver every consumer asks, a chain that logs the backup's failure, a
page that reports the answer, and a codebase with no service name left in it except one, for a
reason the code now states.*

---

## The problem

The question came before the symptom.

Nothing was broken in an obvious way, and that was the point: the app answered "which service?" four
different ways, they agreed by luck rather than by construction, and only one of them could be seen
from the outside. The measurement that turned a vague discomfort into a piece of work was a census of
those answers:

| # | the answer | who it decided for |
|---|---|---|
| 1 | the **default provider row** — a single `is_default` boolean | every consumer that had no better idea, which was almost all of them |
| 2 | the **agent's own declaration** (`provider`, `model`, `preferred_providers`) | the chat path only, and only where the executor chose to honour it |
| 3 | a **capability's private rule** — the title service loading the default row and then applying its own validation | the title service |
| 4 | a **raw construction** — a client built by whatever file needed one | everything else |

Four answers is a defect even while they agree, because the day they disagree there is no surface
that can say which one produced the request you just paid for. Two details made that concrete.

**One boolean fed everybody.** The default row was the whole of "the default provider": one row with
one flag, read by seven consumers — the title service, a built-in tool, the factory's own fallback
helper, the management API, and three workflow nodes. Per-capability selection was not merely
unimplemented, it was structurally impossible: there was exactly one *the* provider, and the only way
to give a second consumer a different service was for that consumer to name one in code.

**A column that promised a chain nobody built.** The provider row has carried a `priority` integer all
along, and a census showed it written by two surfaces, ordered by two list queries, serialized by two
endpoints — and read by no selector at all. Its documentation implied an ordered failover chain; no
materialized list existed anywhere.

**The one real failover was hardcoded, and it was alone.** The executor could fail over — primary,
then each entry in a chain, logging each failure and surfacing the last error — but the chain it
walked was a literal written into the module: `["openrouter", "deepseek", "ollama"]`. Every other LLM
path had no chain at all. Title, the workflow nodes, memory extraction, conversation compaction and
the built-in tools each took a single service or built their own client, which meant the requirement
that a *backup's* failure be logged had nothing to log there: there was no backup to fail.

**Service names in code, and a failure that could not be seen.** Beyond the list above, eighteen
direct LLM constructions lived outside the one factory that was supposed to be the only place a client
is built, each carrying its own provider and model as literals. The consequence was not theoretical.
Two of the services the app was supposed to be able to name — summarization and memory extraction —
were consumed by nothing at all, while the code that should have asked for them named `ollama` and
`llama3.2` directly. On the machine in question no daemon listens on ollama's port, and the memory
path swallowed its own exceptions by design, so fact extraction ran against a service that could not
answer and left no trace in the log either way. The app could not tell "not configured" from "worked".

The goal, in the words the work started from, was to stop coding to a hardwired provider and to have a
unified provider service locator that exposes the different providers as sub-areas of the API — *"so
you can fetch the llm provider for TTS or title service or system agent as needed"* — with a failure
logged, **including the failure of the backup service**.

## The vocabulary, before it gets used

The arc runs on four words and three pairs that a reader collapses if nothing separates them.

| term | what it is | who decides it |
|---|---|---|
| **capability** | who is asking: `chat`, `title`, `workflow-llm`, `stt`, `tts`, `exa`, `memory`, `summary` | the consumer's own name for itself — a fixed set, one row per capability |
| **service** | the configured endpoint that answers a capability: a **provider row**, a **speech engine**, or an **external process** | the capability's configuration, or a rung of the ladder below |
| **model / voice** | the specific thing on that service (`deepseek-v4-flash`, `en_US-lessac-medium`) | same row as the service; a per-request or per-agent override may replace it |
| **kind** | what the caller receives: `llm`, `speech`, `process` | the capability's row — the ladder is shared, the kind decides the shape of the answer |
| **chain** | the ordered list of services a capability may use: the primary first, its backups after | the resolver, from the capability's configuration, an agent's declaration, a request override |
| **resolution** | the ANSWER: what was chosen, in what order, and **which rung answered** | the resolver, once per ask |
| **attempt** | one try against one service in the chain, with its own ordinal and error | the walk that drives the chain |

Three pairs, stated once:

- **A capability is not a service, and neither is a model.** The capability is who asks; the service is
  what answers; the model is the thing on it. A row may name a service and no model, and the row's own
  default then applies — the two are separate fields for that reason.
- **A resolution is not an attempt.** A resolution says what *would* be tried and why that choice was
  made; an attempt is one try, and it either answered or it failed. Chain degradation lives on the
  attempt side, which is what makes a failure reportable.
- **A name in configuration is not a name in code.** The whole point of the arc: a service named in
  the database is a decision someone can change and read back; a service named in the source is a
  second answer nobody can see.

## The roadmap

The build was ordered so that nothing depended on a mechanism before that mechanism was proven to
reproduce the behaviour already in force. That single rule is why the work could be stopped, resumed
and re-scoped across many sessions without drift: at every step there was a live comparison to fail.

| phase | what it was for |
|---|---|
| 1 | the **store and the resolver** — the tables, the ladder, and the read path; no consumer migrated |
| 2 | the first **consumer**: the title service asks the resolver instead of loading the row itself |
| 3 | the **chain, generalized** — one walk, every failure logged, the hardcoded list deleted |
| 4 | the **workflow side**: the node factories resolve, and a node with nothing resolved gets `None`, not a model |
| 5 | the **speech services** onto the same ladder, through the third kind of candidate |
| 6 | the **surfaces**: how availability is read, when a turn is REFUSED, and what a failure statement says |
| 7 | the **page**: the read-out, its documentation, its help, and the tooltips that never fired |
| 8 | the **audit**: re-measure the census, adjudicate every flagged item, and close the arc |

## What we did

**The resolver came first, and was proven to change nothing.** Two tables — a capability, and the
ordered services each one may use — seeded from the behaviour already in force: the default row for
title, workflow-llm, memory and summary; the live settings blob's own engines for speech, which meant
seeding `tts → edge` rather than the `piper` the code had always defaulted to. Then one function,
`resolve()`, returning the chosen service, the ordered backups and **which rung answered** — an
explicit override, the agent's declaration, the capability's own configuration, or the global default
row — and never raising for "nothing is configured". A read-only checkpoint script compared every
capability's answer against what the app resolved at the time and printed, against the live database,
that nothing had moved. That script is the phase: it is the whole claim, and it is why the rest of the
arc could proceed on a mechanism rather than a hope.

**The consumers came one family at a time.** The title service was first, because it had the most
private logic to remove: it now asks for the `title` capability and loads the row that answer names,
with its per-request override riding the ladder's own override rung, and its resolution was proven
identical to the old one on a real title. Then the workflow factories: a node asking for `workflow-llm`
receives a configured client or **nothing** — `None`, logged, never a model written in code — for
every case where the old code would have quietly created one (nothing resolved, a candidate naming no
provider row, a row the database no longer holds, an inactive row). Two nodes lost their
`gpt-4o-mini` fallback in the same landing, and a callerless helper that existed only to hand out a
default client was deleted outright. The speech services followed through the same ladder but the
third kind of candidate — a service that is a *name* rather than a provider row — which is what
`piper`, `edge`, `whisper` and the external agent actually are.

**The chain got one home.** The executor's failover was generalized into a single walk used by
everything: the primary first, each backup after it, every failure logged with its service, its model
and **which attempt it was** (primary, backup #1, …), and the last error surfaced to the caller. The
hardcoded chain constant was deleted — along with three copies of the same list in other modules,
which had also been firing a "fell back" warning to the user *before anything had been attempted*. The
chat stream gained failover for the first time, under the rule that it may only fail over while an
attempt is still opening: once the user has read the first chunk of an answer, that answer is theirs.

**Availability, and the refusal.** A service's availability became a first-class read — reachable,
unreachable, or the specific case of a local port where *something* answers but the engine does not —
cached, stamped with when it was read, and reported on every resolved candidate. That made a refusal
possible: a turn is now refused, in the same shape a failed turn uses, when the capability is switched
off or its primary is cached as down with nothing the walk is allowed to fail over to. A capability
that is off is off; it does not quietly fall through to the default row.

**`priority` finally had a job.** Ordering the rows a class of candidates expands into is the first
reader the column has ever had, which is what it was always for: a chain that prefers local services
tries its candidates in priority order. That settled the column's fate rather than deleting it, and it
made visible a configuration fact worth knowing — a dead local row ordered first is still tried first.

**The audit, and what it found.** Re-measuring the census at the end of the arc produced the arc's real
finding, and it was not in the register: the two capabilities that nothing consumed. The ruling was
that both resolve — a working cloud service as the primary, the local engine as the backup, so a
compaction or an extraction still works when the network is out. The compaction now takes the
`summary` capability's chain; the memory manager takes the `memory` capability's chain.

That second one carried the arc's one genuine design constraint. The memory manager is a registered
singleton, shared by concurrent turns, holding no database session — it could not resolve anything
itself, and its per-turn state must not be written onto the instance, because two turns would race for
it. So the chain is **carried**: resolved where the session is, placed on the turn's own context, keyed
by capability, and read from there. And with no chain supplied the call **skips and says so** rather
than falling back to a name in code — which is the difference between "not configured" and a second
answer. Its last resort asks no service at all.

**And the census pattern itself was wrong.** Running the arc's exit criterion exposed that every
headline number had counted one shape — LLM clients constructed by name — while the rule the work
settled on is wider: *no service named as a decision*. A provider name used as a **default** is in that
class and the old pattern could not see one. Re-censused by property, the class held two live sites: an
agent's default backup list, which was a provider name and therefore landed in every agent created
without one (now empty — an agent that declares nothing declares nothing, and the ladder falls to the
capability's configuration), and a workflow routing seed whose provider and model are **agent lookup
keys** rather than a call: the router matches an agent row whose declaration names them, and the agent's
own declaration supplies the service. That one is kept, and the code now says why.

## How we tested

The instruments were chosen so that each landing had a comparison that could fail.

**Read-only checkpoints against the live database, run before the change was trusted.** A script that
printed every capability's resolved service and compared it with the behaviour in force; a second that
re-titled a real conversation and compared the resolution before and after; a live-row failover fixture
that armed a failure on a real provider row, drove the chain through the app, and restored the row in a
finally block. These are the instruments that make a claim like "nothing moved" a measurement.

**Targeted tests per mechanism, with the delta as the evidence.** The resolver's ladder (each rung in
order, and that an agent influences only the capabilities a live consumer actually passes an agent
for), the three ways a candidate can name a service, the walk itself — including that an empty chain is
reported rather than silently attempted — the refusal path, and the read-out's contract. The test-count
delta on each landing was reported alongside the gate, because "N new tests, no removals" is checkable
in a way that "tests pass" is not.

**Deliberate provocation for the fixes that carried a property.** Where the change was "this must stop
happening", the test was proved discriminating by putting the defect back: slicing a chain to its
primary reddens the backup test; restoring a default provider name reddens the test that says no
service may answer for a caller that named none; neutering a skip guard reddens the tests that assert
the skip is announced. A test that has never been red is a test that proves nothing.

**What driving the running app found that a green suite could not:** a pre-existing defect where a
provider row reported a key as present while the secret lived under the provider's *type* (both are now
reported consistently); two tooltips that could never appear because they sat on controls that are
disabled in the state that needed the explanation, and a disabled control fires no hover; a dead
duplicate of a fact-extraction routine on a base class, unreachable because the subclass overrides it;
and the swallowed exception that made a dead service invisible.

## Lessons learned

- **A derived question has N answers — census by the QUESTION, not by the symbol a plan named.** The
  same "is this service up?" had four implementations in the tree, two with different vocabulary, one
  with no caller at all. Building on the named one would have made N+1.
- **A count carries its pattern.** The census's headline figure was taken with a broader grep than the
  command that later "reproduced" it, and the two were not comparable — and separately, a pattern that
  counts CONSTructions cannot see a name used as a DEFAULT. State the pattern beside the number, or the
  number is not a measurement.
- **"A service is named in code" is a claim about the CONSUMER, not the literal.** A routing table
  naming a provider is a match key if the code matches rows with it and never calls it. Read the
  consumer before declaring the defect; the fix for a non-defect is a comment explaining why it is not.
- **A resolution has to carry the reason it resolved that way.** Without it, a failure statement cannot
  name the service that broke, and a read-out is a list of services with no explanation of the choice —
  which was the original complaint, restated.
- **A chain walked by something that holds no session must be CARRIED, never written onto a shared
  instance.** A registered singleton serving concurrent turns cannot hold per-turn state; put the
  answer on the turn's own object and let the component read it there.
- **No chain must SKIP and say so.** The failure the arc set out to remove was invisible precisely
  because the absent case fell back to a name in code and then swallowed its own exception. Silence is
  the defect; a warning naming the capability is the fix.
- **A last resort that asks no service is still a last resort.** Falling back to a plain-text summary
  or to nothing at all is honest; falling back to a *service* nobody configured is the defect wearing a
  helpful face.
- **Defaults are answered by the resolver, not by a name.** A provider name in a column default landed
  in every new row silently — the widest possible reach for the least visible decision.
- **Delete the dead duplicate rather than porting it.** A routine on a base class that its subclass
  overrides is not an interface; it is a second copy of the truth, and it will be edited one day by
  someone who does not know it cannot run.

## Where it stands

The resolver is one module (`domain/providers/capabilities.py`): the ladder, the walk, the refusal, and
the shared attempt helper. Two tables hold the configuration, one row per capability and one per
service in its chain. Three endpoints serve it — list the capabilities with each one's resolved chain,
read one, and write one — and the page at `/providers/capabilities` renders the same answer a person
asked for at the start, including which rung answered and whether the service is reachable right now.

Everything that answers a capability asks the resolver: chat, title, the workflow LLM steps, the speech
engines, the external agent, summarization and memory extraction. No service is named in code, with one
deliberate exception whose reason is written at the table it lives in. The walk logs every attempt with
its service, model and ordinal, so a degraded turn is diagnosable from the log alone — the requirement
the work started from, now with a backup that exists to fail.

The behaviour is pinned by the resolver's own test file (the ladder, the naming forms, the walk, the
refusal), the capability API tests, and the endpoint tests for the paths that consume a chain. The
capability page's atlas doc and its help page are the reader-facing halves.

**Where to look for the truth, when this page and the code disagree:** the code wins, and the
resolver's module docstring states the ladder in the order it is applied.
