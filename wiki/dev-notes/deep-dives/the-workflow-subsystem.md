---
title: The Workflow Subsystem
type: dev-note
path: wiki/dev-notes/deep-dives/the-workflow-subsystem.md
confidence: verified
created: 2026-10-07
updated: 2026-10-07
tags: [type/dev-note, domain/deep-dives]
---

# The Workflow Subsystem — how a workflow is declared, cast, triggered and delivered

*A work account of the layer ABOVE the run. The companion page,
[[dev-notes/deep-dives/the-workflow-run|The Workflow Run]], is about one execution — its outcome, its
history, its traces. This one is about what has to be true before a run exists at all: a process
declared once, a cast that can be swapped, a trigger that can fire it unattended, and a product that
reaches somebody.*

---

## The problem

A workflow engine is easy to grow and hard to keep honest. This one grew the way they all do: the
*shape* of a process ended up encoded in several places at once, and each place could disagree with
the others.

Three of those places were visible from outside.

**The process was a ladder in the router.** Resolving a template to a graph was a chain of
name-by-name decisions written into the request path — so adding a process meant editing the router,
and the set of things the system could *do* was the set of names somebody had remembered to write
down there.

**The vocabulary was personas, not processes.** The names in the tree were `file-clerk` and
`boss-agent` — a job title and an organizational metaphor. A persona name is a poor name for a
reusable process: it says who, not what, and it cannot be reused for a second process that happens to
work the same way. It also invites a specific failure, and the system had one: a **fan-out engine**
filed under the boss's name, containing no boss.

**Capabilities were declared where they were not reusable.** Delivery of a run's output was written
into the node that produced it; the model a workflow's calls should use was a literal chain in code;
and the triggers that were supposed to fire monitors unattended existed as example rows on a demo
workflow — rows that had never been meant to be real.

The result was a system that could run a great many things and could not say what it could run. The
measurement that sized the work was simply the declared population: **36 templates** resolved through
one hardcoded ladder, with no declaration anywhere of what a *class* of workflow is, what it
produces, or what its failures mean.

The subsystem's own goal, in the wording the work settled on: **a kind earns its place by integrating
end-to-end** — execute → history → product → distribution → trigger. Not "a graph exists", but the
whole path from being declared to being delivered.

## The vocabulary, before it gets used

| term | what it is | who decides it |
|---|---|---|
| **kind** | the general process shape (*monitor*, *chain*, *file-processing*) — declared in code | the code (`kinds/registry.py`) |
| **template** | a configured INSTANCE of a kind: a kind id, a config JSON, inputs, a category | the user/database |
| **version** | a revision of a template's config | the workflows API |
| **run** | one execution of a template — the subject of the companion page | the frame |
| **catalog mirror** | the `workflow_kinds` table: rows for browsing and the UI. **Not** the source of truth for how a kind runs | a migration, kept in step with the registry |
| **builder key** | the name a kind uses to reach its graph builder | the kind declaration |
| **product type** | what a finished run delivers (`report`, `file`, `index`, `manifest`) — the producer→consumer contract | the kind declaration |
| **error contract** | the failure family a kind's nodes inherit | the kind declaration, resolved by the error taxonomy |
| **the cast** | the three roles a workflow is built from: **Boss** (the reasoning call), **Worker** (the transform call), **Orchestrator** (the deterministic glue) | the workflow's spec, per role |
| **spec** | a named role definition — a prompt, an ordered chain, sampling params. A *pseudo-agent*: stateless, tool-less, memory-less | the pseudo-agent catalog |
| **chain** | a role's ordered models: a **starter** first, then the **bench** | the spec |
| **`served_by`** | the provenance a call returns: which chain step actually answered | the invocation |
| **trigger** | what fires a workflow without a person: a webhook, a schedule, or a database event | the trigger row |
| **product** | the packaged output of a run (type, title, body, source, path) | the run's deliver node |
| **channel / distributor** | where a product goes, as a pluggable class (file, display, toast, agent) | the run's config, or the default set |

Four of those are the ones a reader collapses, and the code itself carries two more that mislead:

- **A kind is not a template.** The kind is the *process*; the template is a *configured instance*.
  One kind carries ten templates; another carries one.
- **The DB table is a mirror, not the source.** `workflow_kinds` holds a row per kind for browsing.
  The behaviour lives in the registry, and the mirror has to be kept in step — which is exactly the
  sort of arrangement that must state which side wins. The code states it.
- **An agent is not a spec.** An agent has a workspace, tools and memory; a *pseudo-agent spec* has a
  prompt and a chain. Workflow nodes that need one LLM call use a spec, so they never stand up an
  agent to do a single transform.
- **`boss_agent_nodes` contains no boss.** The file is the generic fan-out engine (discover, dispatch,
  merge); the *role* called Boss is a different node (`boss_node`, running the `tag-boss` spec). The
  metaphor leaked into the machinery's name, and the machinery is reused by workflows that have no
  boss at all.

And two counts that disagree with themselves, worth knowing before trusting a comment:

- The kind registry's own header calls itself **"the canonical kind set (8)"**. The registry holds
  **ten** entries — the comment was accurate once and the set grew.
- The kind→factory map's comment lists `monitor`, `agent-task` and `multi-agent` among the kinds whose
  graphs are per-template. Two of those are right; **agent-task has been on the single-generic-graph
  path** since it was registered there instead of in the router's legacy table.

## The shape that was ruled

| the decision | why |
|---|---|
| **Kinds are code-defined; the DB is a catalog mirror** | a kind's behaviour is a graph builder and a typed input schema — code, reviewable and testable. The table exists so a UI can browse and a template can reference a kind by key |
| **Kinds are named for the PROCESS, never a persona** | the name has to survive reuse: *file-processing* describes what happens; *file-clerk* described who used to do it |
| **A kind declares its product and its error family** | the product type makes the producer→consumer contract explicit; the error family is what a kind's nodes inherit when they declare no grade of their own (see the companion page) |
| **Simple stays a kind** | the safe default and the beginner's template deserve a name rather than being a degenerate case of *chain* |
| **Resolution is a ladder, and each step is visible** | a legacy per-template graph first, then the kind's graph, then the plain default — so a template that resolves to nothing is a *statement*, not a crash |
| **The chains are data** | a role's starter and bench live in a catalog, not in the node that calls them |
| **All-failed RAISES, and provenance is returned** | a chain that silently gives up cannot be audited; one that returns *which step answered* can |
| **Trigger rows ship disabled** | a fresh installation runs nothing its owner did not opt into — the same rule as the run-retention windows |
| **Delivery is a layer (ABC → registry → factory)** | a new destination is a new class, never an edit inside the node that produced the product |

## What the parts are

### The kind system — ten declared processes

The registry holds **ten** kinds, each declaring a graph builder, a product type, typed inputs and an
error family:

| kind | builder | product | error family |
|---|---|---|---|
| `monitor` | monitor graph | report | llm |
| `chain` | advanced workflow | report | llm |
| `multi-agent` | multi-agent graph | report | llm |
| `agent-task` | the generic agent graph | report | llm |
| `tag-survey` | tag-survey graph | **manifest** | llm |
| `file-processing` | file-clerk graph | **file** | default |
| `context-indexing` | context-indexer graph | **index** | default |
| `batch-orchestration` | boss-agent graph | report | default |
| `system-audit` | system-audit graph | report | default |
| `simple` | simple graph | report | default |

**Eight of the ten resolve through one generic graph factory** — the kind names a module and a
factory, and the factory builds the graph for any template of that kind. The other two are the ones
whose graph genuinely varies *per template*: the monitor's three source variants, and multi-agent's
per-config chains. That split is the honest boundary: a kind gets a single graph when one graph can
serve every instance of it.

The declared population that follows from it: **36 templates** — ten agent-task, eight multi-agent,
seven chain, three monitor, three simple, and one each of batch-orchestration, context-indexing,
file-processing, system-audit and tag-survey. The catalog mirror in the database holds exactly the ten
kind rows the registry declares.

### Templates and versions

A template is the instance: a kind id, a config JSON, declared inputs, a category, tags. It is what a
user picks from a list and what a trigger points at. On top of it sits a versioning layer — a version
row per revision of a template's config, with CRUD, compare and activate endpoints
(`/api/v1/workflows/{template_id}/versions`, `/versions/active`, `/versions/compare`,
`/versions/{version}`) — and beside that an A/B layer (a traffic split across versions, with results).
Both halves are built and neither is in use: the version table holds three example rows written by a
seed script, and the A/B results table holds roughly twenty-three thousand **synthetic** rows (the
template is literally `test-template`, the executions `exec-v2-8` and friends) that are kept as test
material rather than deleted. That is a deliberate state, not an oversight, and it is worth knowing
before treating an empty results table — or a populated one — as a signal about real behaviour.

### The monitor family — the kind that proved the shape

The monitor is the flagship, and it earns the place by being the first workflow a user actually sees:
watch something on a cadence, analyse what changed, deliver a report. Three templates — an RSS digest
(hourly), a market tripwire (five-minute), and a readiness check (manual) — sharing one shape.

Four of its properties are the design, not the implementation:

- **Cross-run state lives in a FILE, not in the checkpoint.** Every trigger fire is a fresh thread, so
  LangGraph's per-thread checkpoint cannot hold "last seen" or "last price". The dedup state is a file
  in the monitor's own data directory that survives restarts. The page says outright: do not "fix"
  this back into the checkpointer.
- **A dead feed never fails the run.** Monitor nodes are *tolerant* by grade — resilience is the
  point. This is the family the node grades were shaped around, and it is why the grade vocabulary has
  a term for "the run is not marked".
- **Summarisation never blocks the digest.** The LLM step falls back to a plain-text digest, so the
  product exists whether or not a model is reachable.
- **Cadence is testability.** Hourly and five-minute triggers can be verified in a session — fire,
  watch the execution record, iterate. A weekly digest would be unverifiable for seven days, which is
  why no monitor ships weekly.

The family also contains the **system sweep**: an audit → verify → analyse → report workflow that
re-runs its own audit and compares, run as the periodic structural check on the instance itself.

### The cast — three roles, and a chain per role

Every fan-out workflow is built from three roles: a **Boss** (one reasoning call over the whole
picture), **Workers** (one transform call per unit, fanned out), and an **Orchestrator** (discovery,
batching, merging, counting — deterministic code). **The LLM lives at the edges**; everything between
them is code whose output is reproducible and whose cost is predictable.

Each role carries its own ordered chain, so the Boss can run on a stronger model than the Workers
without either changing. The contract is the interesting part: **first success wins; every attempt is
logged; a per-attempt timeout; all-failed raises; and the provenance (`served_by` plus the attempt
history) comes back with the answer.** That last clause is what makes a mixed run auditable — a caller
can prove which model answered rather than assuming the one it asked for.

The roles' chains are *data in a catalog*, and they are deliberately ordered by the economics of this
installation: a free route first, a local model second, the paid service last. The local step's model
step's model id is resolved **at call time**, not baked in at import — because the setting behind it
can change while the process runs, and a chain step frozen at import would keep pointing at whatever
the setting held when the module loaded. (Its one residue is recorded in the code: an empty setting
reaches the server as an empty model id, rather than asking the local server what it has loaded.)

The pattern is reusable beyond the roles: a **pseudo-agent spec** is a prompt plus a chain, and the
tag survey is its instance — a workflow that surveys a corpus by fanning out bounded, mechanical
worker calls and collecting their rows into a manifest, with a Boss call over the merged result.

### Triggers — three ways to start without a person

| type | what it is | schema |
|---|---|---|
| **webhook** | an inbound HTTP event starts a workflow | endpoint path, optional HMAC secret, allowed events, expected headers |
| **schedule** | a cron expression, with a timezone and an enabled flag | cron, timezone, enabled |
| **database** | a table-watcher event | the watcher’s own config |

A scheduler reads the schedule rows and registers jobs; one-shot timers are rebuilt from their
records at boot, so a timer that was pending when the process stopped resumes rather than vanishing.
The two monitor triggers are seeded — and both are seeded **disabled**: the seed writes
`enabled: false` in the config and the row is inactive, so nothing fires until a person turns one on.
That is the same opt-in rule the retention windows follow, applied to unattended work.

**And the flag is not single-valued, which is the hazard to know about.** A trigger row carries both
an `is_active` column and an `enabled` key inside its config JSON, and the two answer different halves
of one question: the column decides whether the row is *loaded at all* (the scheduler reads only
active rows), and the config key then decides whether that row's job is *scheduled or paused* — with a
default of **true** when the key is absent. So no single field answers "will this fire?", and the two
live rows disagree: one carries `enabled: false` with an inactive row, the other `enabled: true` with
an inactive row — both silent today, for different reasons, and a future row could read *active* while
its job was paused. Two fields for one question is how a switch stops meaning anything; it is the same
shape, in a different subsystem, as a tracing adapter reading one environment variable while its SDK
read another.

### Delivery — a product, and the channels that carry it

A finished run packages its output as a **product** (type, title, markdown body, source template,
path, metadata) and hands it to a set of **distributors**. The layer is the house pattern — an ABC, a
registry, one factory — so a new destination is a new class:

| channel | what it does |
|---|---|
| **file** | writes the product to the monitor data directory |
| **display** | appends it to an index the Products page reads |
| **toast** | queues an app-wide in-app notification |
| **agent** | hands it to an **addressed** agent — filed into that agent's inbox, or posted as a task in its chat session. An unknown name fails loudly (a dead-letter, not a hang) |

The default set is the first three; the agent channel is opt-in per run, because addressing an agent
is a decision about who should receive the work rather than a delivery detail.

## How we tested

- **The population, read from the running system.** The kind count, the template count by kind, and
  the catalog mirror's rows were read from the live database and the registry rather than counted from
  a document — which is how the mirror's agreement with the registry is a fact rather than a hope.
- **The seeding is idempotent by construction** — the monitor templates and their triggers can be
  seeded repeatedly, so a re-seed cannot duplicate a template or resurrect a trigger a person turned
  off.
- **Per-part suites**: the kind registry and its template binding, the trigger scheduler, the
  distribution layer (file write and path, never-raises, index ordering and cap, the factory shape,
  named/default/unknown selection, and that clearing products keeps the monitor's own state file), and
  the template CRUD that joins kinds.
- **Driving the running application**, which is where a green suite stops being enough: a monitor run
  end to end produced its file, its index entry, the API payload and the page, and the Clear action
  took the products back to zero while leaving the dedup state intact.
- **An audit of the documentation against the code**, because a claim nothing checks drifts. Reading
  the eight dev-notes pages beside the tree corrected the dispatch path (it described a write into a
  deleted mirror), a channel listed as parked that is built and registered, a test count that had
  nearly doubled, a per-item delete filed as future work that is live on both sides, two trigger
  cadences presented as running that ship disabled, and an index page that never listed one of its own
  pages.

## Lessons learned

- **A kind is a process, not a persona.** A job title cannot be reused by a second process that works
  the same way, and it invites machinery to be filed under a name that describes nothing in it.
- **A derived catalog must say which side is authoritative.** A table that mirrors code, with no stated
  winner, is a disagreement waiting for its first edit.
- **A count written in a comment drifts.** The registry calls itself a set of eight and holds ten; the
  factory map names three per-template kinds and two are. Measure the structure, not the prose beside it.
- **One engine, and the capture must not change it.** A debug capture and a release run execute the
  same graph; only what is recorded differs. Two engines would guarantee two behaviours.
- **Cross-run state belongs in a file, not in the per-run checkpoint** — a fresh thread per fire cannot
  carry it — and the corollary matters as much as the rule: once this is understood, do not "fix" it
  back.
- **A chain that swallows every failure cannot be audited.** All-failed raises, and the provenance
  comes back with the answer, so "which model served this?" is a recorded fact.
- **Resolve a setting at call time, not at import.** A module-level constant freezes whatever the
  setting held when the module loaded, which is invisible until someone changes it at runtime.
- **Ship unattended work disabled.** A trigger that starts firing because a row was seeded is a
  decision taken from the person who owns the machine.
- **Cadence is testability.** Choose a workflow's default schedule partly by whether a human can verify
  it inside one session.
- **A new destination is a class, not an edit.** The delivery layer exists so a channel can be added
  without reopening the node that produced the product.
- **A retired identity that nothing references is a finding, not a cleanup.** The survey that used to
  have an agent never needed one; deleting the husk was the *proof* of that, and the search for
  references was the evidence.
- **Two fields for one question is how a switch stops meaning anything.** A trigger's active column and
  its config's enabled key each gate a different half of "will this fire", so neither one alone is the
  answer — and the same shape appeared in the tracing adapter, where the app read one environment
  variable and its SDK read another. One question, one field.
- **A doc claim with nothing checking it drifts.** Five separate pages of this subsystem had drifted
  from the code, in five different directions, and none of them looked wrong on its own.

## Where it stands

- **The kinds** — `backend/app/domain/workflows/kinds/registry.py`: ten declared processes, their
  builders, product types, typed inputs and error families; `GET /api/v1/workflow-kinds` serves the
  catalog.
- **The templates** — `workflow_templates` (36 rows) with `kind_id`, the versioning endpoints under
  `/workflows/{template_id}/versions`, and the A/B layer dormant by decision.
- **The resolution** — `get_workflow_graph()` in `workflows/api/workflow_router.py`: legacy template
  graph → the kind's graph factory → the simple default.
- **The cast and the chains** — `backend/app/domain/pseudo_agents/` (the specs and their chains),
  with the role vocabulary in the Workflow Roles note.
- **The monitor family** — three templates, their graph and nodes, the dedup state file, the two
  seeded triggers (both disabled), and the products they deliver.
- **The triggers** — `workflows/triggers/` (the event router, the scheduler, the webhook handler) with
  the three config schemas declared under the workflows domain.
- **The delivery** — `workflows/distribution/`: the product dataclass, four distributors, the factory,
  and the products endpoints (`GET` the index, `DELETE` all, `DELETE` one).

### Checkable

```bash
# the declared population: the kinds, and the templates each carries
curl -s "http://localhost:8000/api/v1/workflow-kinds" | head -c 400
python3 - <<'EOF'
import sqlite3
con = sqlite3.connect("file:cogitate.db?mode=ro", uri=True)
print(con.execute("SELECT kind_id, COUNT(*) FROM workflow_templates GROUP BY kind_id ORDER BY 2 DESC").fetchall())
EOF

# the two monitor triggers: the row's active flag AND the config's enabled key, side by side
python3 - <<'EOF'
import sqlite3, json
con = sqlite3.connect("file:cogitate.db?mode=ro", uri=True)
for r in con.execute("SELECT id, is_active, config FROM workflow_triggers WHERE id LIKE 'monitor-%'"):
    print(r[0], "| row active =", r[1], "| config.enabled =", json.loads(r[2]).get("enabled", "<absent → defaults true>"))
EOF

# the delivery products, and the suites that pin each part
curl -s "http://localhost:8000/api/v1/workflows/products?limit=2" | head -c 300
uv run pytest backend/tests/workflows/test_distribution.py -q
uv run pytest backend/tests/unit/test_workflow_kinds.py backend/tests/unit/test_workflow_template_kinds.py -q

# the validator that keeps the section's pages honest
python3 scripts/core/check_atlas_validation.py
```
