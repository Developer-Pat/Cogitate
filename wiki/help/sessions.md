---
title: Sessions
category: sessions
subtopic: Overview
order: 1
confidence: high
created: 2026-07-27
updated: 2026-11-18
tags: [domain/help]
---

# Sessions

Sessions track conversation history between you and an agent. Each
session belongs to one agent — switching agents in chat creates a
separate session, so conversations never bleed across agents.

## The Sessions page

The page lists all sessions with filters and bulk actions:

- **Search** — filter by title text.
- **Sort** — by date (asc/desc) or title.
- **Date range** — All / Today / Last 7 days.
- **Agent filter** — narrow to specific agents.
- **Unnamed only** — show only sessions that haven't been titled
  (handy when you want to batch-title or clean up).

## Session actions

- **Open** — resume a session; the full message history reloads from
  the backend.
- **Edit name** — set a custom title by hand.
- **Rename from the conversation** — the system derives a title from
  the session's actual conversation (reads the messages, not just
  the first prompt — so a session that starts with "hello" still
  gets a meaningful name). The model used follows the title
  preference on [[help/local-services|Local Services]] (one click =
  one rename; the button locks while a rename runs).
- **Delete** — removes the session and its messages. Bulk delete runs
  through the selection checkboxes: the bar offers **All** and **None**
  for the selection, and **Delete N** removes the N selected — the count
  rides on the button, which stays disabled until something is ticked.

## How sessions behave

- A session is **created lazily** in chat — it syncs to the backend
  when the first message is sent.
- Sessions persist across restarts (stored in the database, not
  localStorage).
- Sessions and their messages survive agent reconfiguration — they're
  keyed to the agent, not the model.

## The side session panels (in chat)

Both chat pages — Agent Chat and Exa — have a collapsible **session
sidebar** on the right (the Exa page's opens via the list button in
its header, or the input's Layout control). They share the same
widget, scoped to their own conversations (agent sessions vs exa
sessions — never mixed):

- **Sorting, search, and the agent filter are hidden behind the
  panel's Expand chevron** (top-right) — click it to reveal the
  tools.
- Rows reveal their actions **on hover** — the sparkle (rename from
  the conversation) and the ⋮ menu (edit name, copy name, delete).
- The panel toolbar's icon buttons (bulk delete, reload, delete
  confirmation, session actions) are tooltip-named — see the
  [Chat & Agent Interaction](/wiki/help/chat) page's *Hidden controls* section.

## Related

- [Chat & Agent Interaction](/wiki/help/chat) — where sessions are created and used
- [Agent Profiles](/wiki/help/agent-profiles) — the agents sessions belong to
- [Exa Agent](/wiki/help/exa-agent) — Exa's page and its session panel
