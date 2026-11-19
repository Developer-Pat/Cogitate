---
title: Agent Profiles
category: agents
subtopic: Overview
order: 1
confidence: high
created: 2026-07-27
updated: 2026-11-18
tags: [domain/help]
---

# Agent Profiles

Agent profiles let you configure how each agent behaves — its provider, model, cognitive profile, and tools.

**Agent names are unique** — the pool addresses agents by name, so you can't create two agents with the same name. Pick a distinct name, or update the existing agent.

**Workflow recipients** — a workflow product can be handed to an agent by NAME (its inbox, or as a chat task). The name must be an existing agent (the pool addresses by name); an unknown name fails the delivery.

## Basic Info
- **Profile Name \*** — Agent display name
- **Description** — Brief agent description
- **Profile Image** — the agent's picture. **Upload** a PNG, JPEG, or
  WebP file (5 MB max), or **Browse store** to pick one of the images
  that ship with the app (the same pool the Images page shows).

## Provider Settings
- **Provider** — LLM provider (deepseek, openrouter, ollama)
- **Model** — Specific model for this agent (must match provider's cached models)

## Cognitive Tab
- **Cognitive Profile** — Select from the table-based picker showing part codes
  - conversational (d-d-d-d) — general chat
  - quick-response (m-f-y-n) — fast, stateless
  - research-std (a-h-s-d) — structured research
  - balanced-chat (d-h-d-d) — hybrid reasoning
  - code-gen (m-h-d-n) — code generation
  - research-pro (s-h-d-k) — deep research with persistent memory
  - system-admin (s-h-d-k) — system management with persistent memory
- **Memory** — Per-agent SQLite database for deep agents (research-pro, system-admin)

## Tools
- Link tools from the tool registry to enable agent capabilities
- Each agent can have its own set of enabled tools

## Behavior — the system prompt

The **Behavior** tab is the agent's *soul*: the prose it believes about
itself.

- **System Prompt Template** — optionally start from a saved template
  (the dropdown reads *— Choose a template (optional) —*). Picking one
  drops its text into the prompt below.
- **System Prompt** — the editor. This text is stored with the profile
  and written to the agent's workspace (`persona.md`); it is what the
  agent reads as its own character.
- **Enable Memory** — marked *(Coming Soon)*; not yet wired.

## Advanced

The **Advanced** tab holds the sampling knobs — **Temperature**,
**Top P** — and **Max Tokens**: the longest answer this agent may produce.
The field's bound is the ceiling the server serves, and the line under it
shows what the agent **declares** next to what a turn would actually **send**,
with the reason they differ (a thinking driver floors the number; nothing
else raises it). Below that, **Last turn carried** shows what the agent's
most recent turn really sent — an observation, not a prediction, and it
appears only once a turn has run.

An agent that declares nothing runs on the resolver's fallback; the row in
the list shows `declared → sent · reason` for every agent at a glance. Leave
the sampling knobs at their defaults unless you have a reason to change them.

## Collections

The **Collections** tab is where the agent's tool surface lives:

- **Toolkits** — the toolkits the agent **owns**. Use **Attach toolkit**
  or the ✕ to detach; the agent's tool surface is the **union** of all
  its toolkits. With no toolkit owned, the agent keeps the default tool
  surface.
- **Collections** — the collections the agent has been added to — a
  membership, separate from toolkit ownership. See
  [[help/tools|Tool Management]].

## The agent lifecycle — archived & restored

Deleting an agent is a **two-tier** action, and the tiers are
deliberately different:

- **Deactivate (Archive)** — the default. The agent's workspace is
  moved to the archive and the profile leaves the active pool.
  **This is recoverable.** The profile appears under **Archived
  profiles** (the sidebar of the Agent Profiles page) with its
  archive date + folder. Use **Restore** to bring it back — the
  workspace moves back and the profile returns to the pool.
- **Delete permanently** — the irreversible scrub. The agent row,
  its sessions, usage history, workspace, and memory are all
  removed from the system. **Nothing can restore it** — the UI
  asks you to type the agent's exact name to confirm.

**Where to find archived agents** — the **Archived profiles**
section at the bottom of the profile list sidebar (always
visible, with the count). Each archived agent has two buttons:
**Restore** (recoverable) and **Delete permanently** (typed-name
confirmation required).

## Rename & Reset Memory

- **Rename** — edit the Profile Name and save. The agent's
  workspace, history, and memory keep their place (renames never
  move files); a duplicate name is rejected.
- **Reset Memory** — the button beside Delete Profile clears the
  agent's learned memory + chat sessions. The agent ITSELF stays
  (identity, skills, workspace untouched) — the deep agent
  restarts fresh. Confirmed before it runs.

## Save as Template & the profile list

- **Save as Template** — stores the agent's *character* (its system
  prompt, skills, tool surface, and workspace files) as a template on
  the **Agent Templates** page. Cloning from it is the
  [[help/cloning-an-agent|Cloning an Agent]] checklist.
- **Filter by Team** — the profile list sidebar narrows the list to one
  agent team (the dropdown reads `🌐 All Agents (N)` for everyone).
- **Duplicate** (the row action) — copies the profile and opens the
  copy for editing.
- **Archived profiles** — the collapsible section at the bottom of the
  sidebar (see the lifecycle above).

## Import / Export
- **Export** — Download agent configuration as JSON
- **Import** — Create an agent from a previously exported JSON file

## Tips
- Save profile changes before switching agents
- The profile selector shows part codes for quick comparison
- Each agent gets its own `cognitive_memory.db` when using kv_store memory

## See Also
- [[cognitive-pipeline]] — Part codes and profiles explained

## The Package tab

The profile's Package tab shows the agent's package — the
blueprint it was provisioned from (the toolkit, the skillset, the
advisory LLM spec). The packages table lists what's available;
click a row for the full contents. **Adopt this package** copies
the package's kit, skills, and llm_spec into the agent's own
fields (the agent owns the copies; the package stays the
blueprint). The confirm shows the current vs the new before
anything changes.
