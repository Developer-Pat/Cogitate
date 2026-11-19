---
title: Exa Commands (quick reference)
type: atlas-devnote
category: dev-notes
order: 99
confidence: high
created: 2026-08-30
updated: 2026-08-30
tags: [type/dev-notes, domain/dev-notes]
---

# Exa Commands (quick reference)

## Exa vs Hermes

- **Exa** is the Cogitate agent (the characters — the system agent
  with a face + a name) that you talk to on the Exa page.
- **Hermes** is the runtime Exa runs on — the ACP subprocess with
  its own private home (`.hermes/`), its own skills, sessions, and
  memory files.
- The **⚡ ACP** button sends Hermes slash commands. The dropdown
  is a curated subset; `/help` shows the agent's full list.
- A command typed in the chat input behaves the same as the
  dropdown's — both go through the same ws prompt path (and both
  respect the busy state — no sends while the agent works).

## The most important commands

| Command | What it does |
|---|---|
| `/help` | The full command list |
| `/new` | The agent-side fresh session (the context reset; the visible bubbles stay) |
| `/undo` | Take back the last exchange |
| `/usage` | The token meter — the session's input/output tokens + the provider's rate limits |
| `/memory` | The pending memory writes + the approval gate |
| `/memory pending` | The held memory writes awaiting your decision |
| `/memory approval off` | Open the gate (the agent saves without review) |
| `/model` · `/voice` · `/compress` | The session controls |
| `/sessions` · `/config` · `/status` | The meta-views |
| `/skills` | The installed skills |

## The three resets (what clears what)

| Action | The visible chat | The agent's context | The persistent memory |
|---|---|---|---|
| **Reset** (the header button) | Cleared (the bubbles + the storage) | Fresh (next ask creates a new session) | Untouched |
| `/new` (the command) | Stays | Fresh (Hermes starts a new session) | Untouched |
| `/memory` (the gate) | — | — | The WRITES are reviewed (the approve/reject) |

## The memory layers

- **The conversation** — the ACP session; cleared by **Reset** or `/new`.
- **The persistent memory** — `.hermes/memories/MEMORY.md` + `USER.md`;
  the durable facts injected into every turn; survives the resets.
  `/memory` manages the writes; the files can be trimmed directly.
  A typed-name **Reset memory** (the wipe) is on the discussion list.

## The connection gotchas

- The **ACP button dims** when Exa is offline (the ws reconnect) —
  a click in that window used to do nothing silently.
- The **ws can blip mid-turn**; a fresh turn (< 15s old) is left to
  the reconnect (the fresh-turn grace) — older turns halt (the
  runaway-protection).
