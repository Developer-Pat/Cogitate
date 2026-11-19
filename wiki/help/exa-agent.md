---
title: Exa Commands
category: exa-agent
subtopic: Commands
order: 1
confidence: high
created: 2026-08-30
updated: 2026-11-18
tags: [domain/help]
---

# Exa Commands

Exa is a **Hermes agent** running over the ACP protocol. The **⚡ ACP**
button (above the input) sends the agent a slash command — the same
commands the Hermes CLI understands. The dropdown is a curated
subset; type `/help` in the chat for the agent's full list.

## The Exa page

Exa lives on its own page (`/exa`). The **Exa button on the Agent
Chat page's header just opens it** — a plain navigation, no context
hand-off. The page is a normal chat surface with its
own session panel:

- The **list button** (header, next to the messages bell) toggles
  the **sessions sidebar** — Exa's conversations, separate from the
  agent chat's (each session is titled from its first message).
  The panel shares the agent page's widget — sort/search live
  behind its Expand chevron (see the [Chat](/wiki/help/chat) page's *Hidden
  controls*).
- **Reset** (header pill, two-click confirm) — the **New-chat
  rotation**: it tells Exa to start fresh (`/new` — the persistent
  memory survives) AND opens a new session in the panel.
- **New** (in the session panel) does the same thing.
- The **⚡ ACP** dropdown, **History** (re-send a past prompt), and
  the commands-doc button sit in the input row after the macro
  keys.

## The ACP commands

| Command | What it does |
|---|---|
| `/help` | The agent's full command list |
| `/new` | **New session** — clears the conversation context and starts fresh (the session-level reset; the persistent memory survives) |
| `/undo` | Removes the last exchange (take back a mistake) |
| `/status` | Session info — the agent's state |
| `/memory` | Reviews the **pending memory writes** — the memory saves held for your approval |
| `/memory pending` | Lists the held memory writes awaiting your decision |
| `/memory approval off` | Opens the memory-write approval gate (the agent saves without the review) |
| `/skills` | Lists the agent's installed skills |
| `/model` | Shows or changes the model |
| `/voice` | Toggles voice mode |
| `/compress` | Manually compresses the conversation context (when it gets long) |
| `/usage` | **Token meter** — the session's token usage (input/output + cache) and the provider's rate limits |
| `/sessions` | The session list |
| `/config` | Shows the configuration |

## The memory layers

- **The conversation** (the ACP session) — what was just said; cleared
  by the **Reset** button (header, two-click) or `/new`.
- **The persistent memory** — `.hermes/memories/MEMORY.md` + `USER.md`
  in Exa's private Hermes home; the durable facts injected into every
  turn; survives the New chat. The `/memory` command manages the
  writes; the files themselves can be trimmed directly.

## Hidden controls on the Exa page

- **Message hovers** — each response's footer buttons appear on
  hover: the **speak cluster** (Play — or Pause/Resume + Stop on
  the bubble being read; the auto-read rides its bubble with the
  same controls), **Copy**, **Copy info** (the metadata). Responses
  over 600 chars fold behind **"Report (N chars)"**; reasoning
  folds behind **Thinking**, tool calls behind **Tools (N)** — all
  click-to-expand.
- **The auto-read** reads finished replies aloud while the Speech
  page's **auto-voice toggle** is on (the page re-reads the toggle
  when you switch back to it — no reload needed).
- **Force Kill** — the slim footer line under the input (visible
  only while Exa is connected): a two-click process-group kill for
  when the gentle Stop failed.
- **The session rows** reveal their actions on hover (the sparkle =
  rename from the conversation; the ⋮ = edit name / copy name /
  delete).
- The **Layout control** (under the Send button) — a flyout that
  opens upward; its *Toggle sessions panel* item opens the session
  sidebar.

## Notes

- The commands run **in the chat** — the agent processes them and the
  result appears as a reply (no separate panel).
- The dropdown's a curated window; the agent has more (e.g. `/cron`,
  `/curator`, `/plugins`). `/help` shows everything.
