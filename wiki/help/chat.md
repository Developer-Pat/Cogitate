---
title: Chat & Agent Interaction
category: chat
subtopic: Overview
order: 1
confidence: high
created: 2026-07-27
updated: 2026-11-18
tags: [domain/help]
---

# Chat & Agent Interaction

The chat page is the primary interface for talking to agents. It's a
three-part layout: agent selector (top-left), the conversation, and a
collapsible session sidebar on the right.

## Before you can type

The input box is **disabled until you pick an agent AND a session**.
The placeholder tells you which is missing:

- **"Select an agent to start chatting..."** — pick an agent from the
  selector (top-left — it shows the agent's avatar, next to the
  **"Select agent team"** list selector). The agent's configured model,
  provider, and enabled tools apply to the chat.

  The selector's badges say what you are about to chat with. **Hover the
  provider badge** (e.g. `openrouter`) for the provider **and the model**
  that agent is configured with. Beside it, a **green check** means the
  agent is available and a **red cross** means it is not — hover either
  for the same in words.
- **"Select or create a session to start chatting..."** — open the
  right sidebar and create or pick a session. Sessions belong to the
  agent you're talking to; switching agents means a different session
  (no message bleed between agents).

## Sending messages

- Type in the input, press Enter (or the send button) to send.
- A **session must already exist and be selected** — sending does not
  auto-create one.
- While the agent is responding, the input shows a **Stop** control —
  click it to halt the stream mid-response.
- You can attach files to a message (10 MB max, images/text types).
  Attachments are synced into the conversation stream.

## The session sidebar (right)

The panel has **two tabs**: **Sessions** (the session list) and
**History** (the prompts you have sent — see below).

- **New session** — starts a fresh conversation with the current agent.
  The session is created locally and synced to the backend on the
  first message.
- **Rename** — set a custom title by hand.
- **Generate title** — derive a title from the conversation content
  (the title capability's resolved provider — see
  [[dev-notes/api/title-capability|the title capability]]).
- **Delete** — removes the session and its messages.
- **Import** — bring in a session from a file.

## Model selection

The selected agent determines the model by default. If the page shows
a model override control, you can pick a different model for the
current chat without changing the agent's profile.

## The Ask-Exa box (the header, right)

The **Exa** button at the right end of the header opens a small box
that takes a prompt and answers it — or takes you somewhere. It is
not only a chat: it understands a few short commands.

- `nav logs` — opens a page. Phrases and typos are fine, so
  `nav the logs page` and `nav worfklows` both land. Some pages answer
  to more than one name: `nav tests` finds the Testing Dashboard and
  `nav logging` finds Logs.
- `nav list` (or `nav pages`) — shows every destination the app has,
  as links. **Nothing opens until you pick one.**
- `search triggers` — lists every page and wiki note matching the
  words. **Nothing opens until you pick one.**
- `info workflows` — opens the wiki's best page about a topic.
- `dev architecture` — the same, in the developer notes.
- `atlas settings page` — the same, in the UI atlas.

Anything that is not one of those words is sent to Exa as a question,
and the answer streams into the box.

- `exa <question>` — the same thing, said explicitly. Use it when your
  question happens to START with one of the words above: `exa search is
  broken on the tools page` asks Exa, where the bare sentence would be
  taken as a search for "is broken on the tools page".
- `exa` on its own opens the Exa Agent page.

### When it takes you somewhere

Two different things can move the page under you, and they are not the
same:

- **Exa answers a question and the answer is a place.** The box opens
  that page for you. The marker Exa uses to ask is stripped before you
  read the answer — you see the answer, not the plumbing.
- **Exa takes you there while working.** When you hand Exa a job, it
  can open the page the job concerns without being asked, so you can
  watch. Nothing appears in the box for this: the page simply moves.

A destination that does not exist is **never** opened — the box tells
you it could not find it and offers what it knows. That is deliberate:
a wrong jump is worse than no jump.

- **Ctrl+K** (Cmd+K on a Mac) opens the box from anywhere. The mouse
  works too: opening it lists the **destinations you actually use**,
  most-used first, one click away. **Clear** empties that list, and
  **All** shows the rest of it.
- **Full page** opens the Exa Agent page, where Exa's conversations
  live, with their own session panel and ACP command set — see the
  [Exa Agent](/wiki/help/exa-agent) help page. Its connection, permission tier,
  and time-limit settings live on the Exa Config page (its own help).
- `nav` and `list` keep working when the backend is down — the pages
  come from the app itself. The wiki half of a `list` needs the backend
  and comes back empty, and `search`/`find` search nothing but the wiki,
  so they need it too.

Do not confuse it with the **Ask Exa** buttons on some pages (Workflow
Templates, Macros, a workflow's run page, and Setup): those hand that
page's job to Exa with the matching skill, and Exa drafts the artifact
there and shows its work for you to verify.

*Connectivity notices come from the app itself and appear when the
backend drops.*

## The chat input — the macro keyboard + the send column

The input's controls live in two groups:

**The macro keyboard row** (left) — the keys + their selectors:
- **F1–F5** — insert the selected topic's macro text into your message.
- **M1–M5** — the topic keys (switch the mapped set driving F1–F5).
- **The F selector** — the small icon after the M keys (the tooltip:
  "Select F-Key Macros"); its flyout picks the meta-topic driving the
  F/M keys. Select = the new topic immediately (no refresh button —
  the keyboard auto-syncs with the server).
- **A1–A5** — the ACTION-key bank (see the [Macros](/wiki/help/macros) page's
  A-keys section): flyouts fed by the A-key source meta-topic.
- **The A selector** — the small icon beside the A keys (the tooltip:
  "Select A-Key Macros"); its flyout picks the action-key source.
  Agent chat and Exa each keep their OWN F-topic and A-source.
- On the **Exa page**, the ACP controls (the commands reference + ⚡
  ACP + History) sit right after the A selector in the same row.

**The send column** (right) — Send on top, and beneath it:
- **Collapse long responses** — collapses every response fold except
  the last one (click again to expand them all).
- **Layout controls** — the layout flyout (toggle the session sidebar
  / the navigation).

The Messages bell (with the unread count) and the **Ask-Exa** button
live in the page header — not in the input row. The Ask-Exa button is
the right-most control there.

## Hidden controls & gestures

Several controls are deliberately tucked away to keep the page
clean. Everything below is discoverable by **hovering** (tooltips
name every icon) — the ones new users most often miss:

### The session sidebar (right)

The panel's **toolbar buttons are icon-only** — hover for the
tooltip. Left to right:

- **New** (the pill button) — a fresh session with the current agent.
- **Session actions** (the ⋮ icon, only with a current session) —
  the dropdown: **Edit Title** (by hand), **Rename (AI)**
  (derived from the conversation), **Export**, **Import**, and
  **Close**.
- **Deselect** (the circle-with-a-slash icon) — drops the current
  selection so you can work with no session open. It is **dimmed
  while a message is streaming**, and while nothing is selected.
- **Reload** (the circular-arrow icon) — re-fetches the sessions
  from the database.
- **Expand** (the chevron) — see below.
- **Bulk delete mode** (the trash icon) — toggles the selection
  checkboxes; select rows, then delete them together.
- **Delete confirmation** (the shield icon, at the far right) —
  toggles the two-click delete confirm (OFF by default — rows
  delete on one click).

### History — your sent prompts

The **History** tab lists the prompts you have sent, **alphabetically**
and **without repeats** — a prompt you have already sent is not added a
second time, so it stays a set of distinct prompts rather than a log.
Each row shows the prompt's first characters; hover any row for the
**full prompt** (very long ones are cut off, with a note telling you so).

Every row carries three buttons: **Copy** it to the clipboard, **send it
back to the message box** — which *fills the input* and leaves it for you
to edit, and never sends by itself — and **remove it from this list**.
The removal takes only that row; the conversation is untouched.

- **The list is per-browser-tab and lasts as long as the tab does.**
  It survives a refresh, and it is gone when you close the tab. It is
  a record of what you *asked*, so it keeps prompts from sessions you
  have since deleted.
- **Clear history** (the footer) — empties the list. **The
  conversation is not touched** — only this list.
- **Expand** (the chevron, top-right) — **reveals the panel's
  hidden tools**: the search box, **Sort by** (Most Recent /
  Oldest First / Alphabetical), the per-agent filter (agent chat
  only), and the session count. **The sort control is hidden here
  by default** — open the chevron to reorder the list.

**Per session row** (the icons appear on hover):

- **The sparkle** — *rename from the conversation*: the title is
  derived from the session's messages (one click = one rename).
- **The ⋮** — the row menu: **Edit name** (a hand-typed title),
  **Copy name** (the title to the clipboard), **Delete**.

### The conversation

- **Hover a message** — the footer icons appear: **Copy** (the
  text), **Copy info** (the metadata — model, tokens, timings), and
  the **speak cluster**: **Play** on a silent bubble
  (click = read aloud; if another bubble is speaking, the click
  switches the voice to this one); the bubble being read shows
  **Pause** / **Resume** + **Stop** instead (never a play while
  playing). The auto-read (Exa, when the Speech page's toggle is
  on) attaches to its bubble with the same controls — a voice is
  never unstoppable.
- **Thinking / Tools folds** — assistant messages with reasoning or
  tool activity fold behind the collapsible headers; click to
  expand. **Responses over 600 chars fold behind "Report (N
  chars)"** — collapsed by default to keep the thread readable.

### The input row

- **The F and A topic selectors are icon-only** — they sit beside
  the macro keys. Hover: the tooltip is a *state readout* ("F
  topic: <name> — click to change"); click: the flyout lists the
  meta-topics. **The macro keys themselves (F1–F5, M1–M5, A1–A5)
  preview their content on hover** and insert it on click.
- **Collapse long responses** + **Layout controls** sit under the
  Send button. The Layout control is a **flyout that opens
  upward**: *Toggle sessions panel* and *Toggle navigation* live
  inside it, not as visible buttons.
- On the **Exa page**, the **⚡ ACP** dropdown (the agent's slash
  commands), **History** (re-send a past prompt), and the command
  reference are in the same row — see the
  [Exa Agent](/wiki/help/exa-agent) help page.

## Related

- [Sessions](/wiki/help/sessions) — managing conversations
- [Agent Profiles](/wiki/help/agent-profiles) — configuring agents, models, and tools
- [Exa Agent](/wiki/help/exa-agent) — Exa's page, commands, and permissions
