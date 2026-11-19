---
title: Shallow-Agent Provisioning — the Workspace-First Partition
type: dev-note
path: wiki/dev-notes/agents/shallow-agent-provisioning.md
created: 2026-09-02
updated: 2026-09-10
status: current
tags: [type/dev-note, domain/agents]
---

# Shallow-Agent Provisioning — the Workspace-First Partition

> THE BUILD (2026-09-02, the user's call): an existing agent row is
> provisioned to the SHALLOW tier — a workspace folder of its own,
> personal state, and the WRITE tools to maintain that state itself.
> Bob is the first tenant. The partition: what the agent OWNS lives
> in its folder; what the SYSTEM controls stays in the DB.

## The partition principle (the data homes)

Three tiers, three homes — nothing drifts, nothing drops:

1. **Registry + access control → the DB** (`agents` row + grants +
   kit perms). Name/provider/model/active, kit membership, tool
   grants, tool links. SERVER-side truth, never agent-writable:
   grants in a folder the agent's tools can write would be
   self-escalation. The delete/archive flows are DB-driven.
2. **What IS the agent → its workspace** (`agents/<key>/`):
   - `persona.md` — the persona text (the row keeps a SYNCED
     fallback for folder-less agents + export/import)
   - `state.json` — facts + sources (the per-agent state store).
     Scaffolded FRESH as `{"facts": {}, "sources": []}` — both keys
     present, both empty; an instance is never carried in from a
     template
   - `skills/` — the agent's skill sheets. Scaffold SEEDS the row's
     named skills from the shared repo library `skills/`; an existing
     file is never overwritten ("skills grow")
   - `news-beats/` — the agent's beat sheets (`<name>.md`); added by
     the 2026-09-10 News Team arc (see [[dev-notes/agents/beats|Beats]])
   - `assignments/` — the agent's NOTEBOOKS, one JSON file per piece of work it opened
     (`<id>.json`): the goal, its status, the notes it wrote and the sources it has
     already fetched. It is the one store that survives a TURN — a follow-up re-opens the
     assignment instead of re-gathering it — and the current one is DERIVED (the most
     recently updated open one), never a stored pointer. See "the notebook" below.
   - `agent.json` — the derived REGISTRY manifest (no persona copy;
     it is a manifest, not a content store)
3. **Secrets → server-side only, OUTSIDE the workspace.** Anything
   in `agents/<key>/` is agent-readable (file-manager is sandboxed
   there) — an LLM-readable secret is a leakable secret. Future
   agent keys go in a vault the agent's tools cannot reach (the
   `.env` pattern for provider keys). The whole `agents/*/` tree is
   git-excluded (`agents/*/` in .gitignore).

## The tools an agent uses to maintain itself

`update-sources` / `update-state` (builtin, keyed, needs_workspace):
the execution service injects the agent's OWN folder as base_path;
writes land in state.json, never outside. Verified read-backs
(what WAS written). update-state has set AND remove (2026-09-02 —
facts can be deleted, not just tombstoned).

`update-beat` (builtin, keyed, needs_workspace — 2026-09-10, the News
Team arc) is the third: it edits the agent's own beat sheet
(`news-beats/<name>.md`) and returns the verified read-back. Same
workspace-grant mechanism as the state tools; see
[[dev-notes/agents/beats|Beats]].

### The notebook (2026-10-13, the research-run arc)

Four more workspace tools, one store: **`open-assignment`, `add-note`, `read-assignment`,
`close-assignment`** (`app/domain/tools/builtin/assignment_handler.py` over
`app/domain/agents/assignments.py`). An assignment is one piece of work — *"the leading
economic headline for Europe"* — and its notebook holds the goal, the agent's own notes
and the sources it fetched, so **what a run gathered survives the turn**. Opening the same
goal again RESUMES the same notebook; a bare note lands on the current assignment (the most
recently updated OPEN one, derived from the folder rather than pointed at by a second file).

Why it exists, measured: over ~7 weeks of logs the news runs made **989 fetches / 26.9 M
characters — 91 URLs more than once** (one weather page 18×) — with nothing surviving the
turn, while `update-state` was called **6 times in 120 turns**. So the notebook is written
by TOOLS the agent calls and read back into the prompt, not left to the model's discipline:
`build_assignments_block` (the open assignments, what each holds, and **which sources are
already gathered** — the line that stops a re-fetch) rides `prepare_chat_context` beside the
YOUR-STATE block.

Two rules the code enforces, both copied from the stores above because each was paid for
once: a notebook that cannot be parsed is a LOUD refusal (`AssignmentUnreadable`) rather than
an empty read that would arm the next write to erase it, and an id is validated strictly —
it arrives from a model and becomes a FILENAME inside the agent's folder.

**The grant, not the tier, is what reaches a kitted agent.** `file-write` / `file-read` are
GRAS, so an unkitted agent gets the notebook by default — but a kit IS the surface, so a
kitted agent (Bob and Lois own `Workspace` + `Online Search`) sees a tool only once it is
granted to one of its kits. The four slugs are granted to `Workspace` (`read` level, beside
`update-state`).

**The notebook fills itself.** The four tools are the agent's way to keep a record; they are
not what makes the record exist. The first live run had all four on the surface and used
none of them (four fetches, 127,854 characters, nothing written — the same shape as
`update-state`'s 6 calls in 120 turns), so the fetch records itself: the tool loop calls
`router._capture_gathered(context, tool_results)` after each round, which reads the fetch
facts out of the result payload (`assignments.fetch_facts` — a URL plus a body, never a
search) and writes them through `assignments.capture_fetch`. The assignment is opened from
**the turn's request** (`ChatContext.turn_goal`, the user's message), so the same request
resumes the same notebook across calls and turns. The capture never raises and never blocks:
a broken notebook is logged and the turn carries on.

**And a fresh re-fetch is answered from the notebook, not the web.** A record alone did not
change the spend: three live runs of one request fetched the same three URLs EVERY time
(117,352 characters, the whole turn's cost), the third of them 11 minutes after the second,
and the run's own note said "fetched FRESH headlines". Naming the sources was not enough — the
prompt never said WHEN they were taken, so for a news beat re-fetching was a defensible
judgement. Two changes followed:

- **the digest carries each source's age** (`assets… (11 min ago)`) and names the escape hatch,
  so a caller judges freshness instead of guessing at it;
- **`jina_reader` consults the notebook before it pulls** (`needs_workspace` for the agent's
  folder → `assignments.recent_fetch(url, within_minutes=FRESH_FETCH_MINUTES)`, 30 minutes by
  default). A hit returns the stored record **plus the notes that hold what was learned from
  it** — provenance and the finding — and says how to override. It is a DEFAULT, not a refusal:
  `refresh=true` fetches anyway, and a notebook that cannot be read is skipped in silence,
  because a lookup failure means "just fetch it". A served answer carries `cached: true` and no
  `content`/`chars`, so the capture cannot mistake it for a second fetch.

**A fetched page is capped, and a page with nothing in it is refused.** Both were measured
before either was built: 989 fetches, median 15,058 characters, p90 62,411, max 463,980 — and
the fat ones are navigation and furniture around a short list of headlines (one front page,
60,950 characters, is by itself ~15,000 tokens, the app's whole declared input budget). So:

- **the cap** (`DEFAULT_MAX_CHARS = 24,000`, raisable per tool config) keeps the HEAD and the
  TAIL and puts a notice in the middle naming the true size and what to do about it ("fetch a
  narrower URL — the article itself"), because an unannounced truncation is the kind of silent
  lie this codebase keeps paying for. The true size still rides `content_length`, so the
  notebook records 60,950 and not 24,000;
- **the verdict** refuses a body that carries nothing **before it is billed**: the reader's own
  `Title:/URL Source:/Markdown Content:` preamble does not count as content (measuring it was
  how a 142-character 1×1 tracking pixel passed the old 50-character "empty" test), and a page
  that says it has nothing (`page unavailable` — 137,930 characters, fetched, carried and
  re-billed by the turn that followed) is refused whatever its size. `error_type:
  "UnusableContent"`, no content returned, and the capture records no source.

## The skills partition

- The shared library lives in the repo `skills/` dir — both house
  conventions are supported: directory-style
  (`<category>/<name>/SKILL.md`) and flat (`{name}.skill.md`).
- The agent's own `agents/<key>/skills/` — SEEDED at scaffold time
  from the shared library (`workspace.py::_seed_skills` copies each
  name in the row's `skills` list in), then grown by the agent.
  A file already present is left alone.
- `skill-reader` reads BOTH (needs_workspace=True; the agent's
  folder joins the scan roots). The deep pipeline's context_builder
  already did the per-agent override; the tool surface now matches.

## The context read path (folder-first)

`prepare_chat_context` builds the persona through
`persona.read_persona(agent)`: the workspace `persona.md` wins; the
row's system_prompt is the fallback. `AgentService.update` syncs a
system_prompt change to BOTH (no drift). Provision/scaffold writes
persona.md from the row.

Two more blocks join the system prompt from the same folder, both silent when the store has
nothing to say: **YOUR STORED STATE** (`agent_state.build_state_block` — facts + curated
sources) and **YOUR ASSIGNMENTS** (`assignments.build_assignments_block` — the open
notebooks, what each holds, the sources already gathered). Both read the store the tools
write; neither keeps a copy.

## The beat has its own home (2026-09-10 — supersedes the single-home rule)

The 2026-09-02 rule — "the beat IS the sources list in state.json" —
is SUPERSEDED. A beat is now a sheet at
`agents/<key>/news-beats/<name>.md`: the purpose, the interests
(Subjects / People / Places) and a `## Sources` list, plain markdown,
edited by `update-beat` in chat. Outlet names are bullets in the sheet
— not entries in `state.json` and not persona prose. Prose that names
outlets still drifts; the sheet is the one home. See
[[dev-notes/agents/beats|Beats]] and
[[dev-notes/agents/agent-cloning|Agent Cloning]].

(Code-side: `backend/app/domain/agents/persona.py`'s module docstring
still repeats the old single-home rule — it should point at the beat
sheets.)

## Code touchpoints

- `backend/app/domain/agents/workspace.py` — scaffold/provision
  (agent.json + persona.md + skills/)
- `backend/app/domain/agents/repository.py` — `provision_workspace`
- `backend/app/domain/agents/agent_state.py` — the state store +
  `build_state_block` (the prompt's YOUR STORED STATE)
- `backend/app/domain/agents/agent_beats.py` — the beat store
  (news-beats/<name>.md; surgical line edits, no serializer)
- `backend/app/domain/agents/persona.py` — read_persona/write_persona
- `backend/app/domain/tools/builtin/agent_state_handler.py` —
  update-sources / update-state (keyed, needs_workspace)
- `backend/app/domain/tools/builtin/agent_beat_handler.py` —
  update-beat (keyed, needs_workspace, verified read-back)
- `backend/app/domain/tools/builtin/skill_reader_handler.py` —
  SkillReaderTool (generic + personal roots)
- `backend/app/api/v1/chat/context.py` — the folder-first read

## The inventory rule (nothing dropped)

Any migration of agent content between homes runs the inventory
check first: every outlet in the sources store, every non-beat
persona sentence must survive. The tests pin it
(tests/unit/test_shallow_agent_provisioning.py).
