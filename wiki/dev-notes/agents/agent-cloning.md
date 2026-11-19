---
title: Agent Cloning — the process and the learnings
type: atlas-devnote
category: agents
order: 11
confidence: high
updated: 2026-09-10
tags: [type/devnote, domain/agents]
---

# Agent Cloning

Cloning makes a **new agent from an existing one**. The tools copy the
*character*; the user supplies the *identity*. The walkthrough lives in
the help pages ([[help/cloning-an-agent|Cloning an Agent]]); this note is
the machinery plus what this arc taught.

## The process, in one glance

**Save as Template** (Agent Profiles → an agent → Save as Template), then
**Apply** it (Agent Templates). The clone is created complete.

| the tools do | the user does |
|---|---|
| the workspace folder + a derived `agent.json` | the soul's wording (Agent Profiles → Behaviors) |
| the **soul** (the template's system prompt → `persona.md`) | the name (unique — the pool addresses by name) |
| the **skills**, seeded from the shared `skills/` library | the face (the image picker) |
| the **workspace files** (the beat sheets) | the beat — **co-authored in chat**, not hand-edited |
| the **kits** (the tool surface), attached | the agent's own facts (it stores them itself) |
| a **fresh face** from the pool — never the original's | the kit check + the cognitive profile |
| an **empty state** — `{"facts": {}, "sources": []}` | |

## The hard line: character vs instance

- **The character clones** — the lens, the craft, the voice, the tool
  surface. That is what a template is for.
- **The instance never clones** — `state.json` holds what the agent has
  *learned*: its location, its sources, its watches. Copying those would
  assert facts the clone never learned. It starts empty and fills them in
  as you talk.
- **The face is not carried either.** A clone wearing the original's face
  is confusing in exactly the way a clone should not be; it picks its own
  from the curated pool (`assets/agent-images/`, served at
  `/static/<name>.png`).
- **The beat sits between them** — see the open question at the end.

Renaming is safe and keeps the disk identity: `workspace_key` never
changes ("renames don't move files"), so the folder, state, beats and
skills stay put; only `agents.name` and `agent.json` change. A rename
does **not** touch the soul — see the persona note below.

## The learning this arc is really about: two readers that disagree

Every significant bug in this arc had one shape: **two parts of the system
read the same fact from different places, and disagreed.** Five faces,
found in a single day, all of them silent:

| the fact | reader A | reader B | what the user saw |
|---|---|---|---|
| the write schema | `AgentCreate` (inherits the base) | `AgentUpdate` (re-declares by hand) | ten columns silently dropped on PUT — an assigned image never stuck |
| the image URL | the DB row | the edit form | the dev origin baked into the value and written back; the avatar showed on one page and not another |
| the agent list | `ProfileService` | `AgentService`'s private cache | the profile page was right, the chat was stale |
| the tool surface | visibility reads the **kits** | the execution gate read **`agent_tools`** | tools offered, then refused; the model replied empty and the session looked dead |
| the write params | `_op_write(path, content)` | the tool's declared schema (no `content`) | a write reported SUCCESS and changed nothing |

The fixes were all the same move: **one home, and everyone reads it.**
Not a third invalidation path, not a reconciler — delete the second copy
or point the second reader at the first.

Two corollaries worth keeping:

- **A silent no-op is worse than a loud refusal.** A write with no content
  reported success. A stop that leaves orphans reports success. Both cost
  more than an error would have.
- **A capability that is visible but ungated-in-reverse is a trap.**
  Offering a tool and refusing it teaches the model to lie — it promised
  an edit it could not make.

## Five layers deep: what unblocked an agent that could not write

For the record, because each layer hid the next:

1. **The permission gate ignored the kits** — the agent's kits grant the
   tools, but the gate read the legacy `agent_tools` table (empty for a
   fresh agent). Fixed: the gate consults the kit.
2. **`file-write` was a keyed capability** — it demanded a grant in
   `agent_tool_grants` (Bob had one; a new agent has none). **Made GRAS**:
   every file tool is sandboxed to the agent's own folder, so the sandbox
   is the scope. An explicit `agent_tools` row with `is_enabled=0` still
   excludes it per agent.
3. **The `write` operation declared no `content` parameter** — the model
   saw a write with no way to pass text and guessed `source` (the copy
   input). Fixed: `content` is declared.
4. **An empty write succeeded** — it wrote nothing and reported success.
   Fixed: it refuses, and says which parameter to use.
5. **`FileManagerTool` lacked `needs_workspace`** — so the execution
   service never injected the agent's folder as `base_path`, and every
   operation failed with *"base_path is required in config"*. Reads looked
   fine because `file-info` has the flag. Fixed: the flag.

Verified end to end: asked in chat, the agent wrote `news-beats/…md`, and
the subjects line changed on disk.

## The launcher leaves orphans

`./cogitate.sh stop` kills the supervisor but not its children. The vite
tree re-parents to PID 1, **keeps port 5173 bound**, and keeps serving the
OLD bundle — so a `start` cannot take the port and every frontend fix
silently stops reaching the browser while the app looks healthy. Found by
chasing a fix that "did not work": the browser was running weeks-old code.
Fix proposed: stop the process *group*, and verify the ports are actually
free — loudly.

## The resource-locator gap

The backend has `Paths`, a locator whose own docstring says it was created
for exactly this bug class. The frontend has no equivalent: `new URL()`
appears once (for query params) and `import.meta.env.BASE_URL` zero times.
Three incidents (the `//api/...` protocol-relative URL, the baked origin,
a raw `${base}${path}` stream URL) all came from string-concatenating
URLs. One `resolveUrl()` helper built on `new URL()`, plus a lint, would
close it.

## What comes with a clone — OPEN

A template carries a *character*, so a cloned reporter arrives with news
prose, a Middle East beat and news-flavoured skills. Right for another
reporter; wrong for anything else, and silently so. What should seed and
what should be born blank is undecided — four options are captured in
`local/agent-cloning/study.md`. Revisit when a second kind of agent
appears.

Related: the soul embeds instance facts (Bob's persona says "Your locus is
Omaha, Nebraska"). The soul should describe the character and point at
`state.json`.

## The personas are the user's

Personas (the system prompt, on the profiles page's Behaviors section —
the user calls it the **soul**) are never edited by tooling: a name change
does not rewrite prose, because a rename cannot know whether "Bob" in that
text is the agent or a person it reports on. Skills grow; the soul stands
until its owner rewrites it.
