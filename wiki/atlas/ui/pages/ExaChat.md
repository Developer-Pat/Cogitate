---
title: ExaChat
type: atlas-page
path: frontend/src/pages/ExaChat.tsx
category: pages
order: 12
confidence: high
updated: 2026-09-12
tags: [type/ui, domain/external-agent]
---

# ExaChat — the Exa Agent page

The system agent's chat surface (`frontend/src/pages/ExaChat.tsx`,
route `/exa`). The Exa Agent is an external ACP agent operated
through its own first-class channel — no agent-chat bridge.

## The header

- The **Exa face** — the config's image setting (the Exa Config
  page).
- The **status dot + line** — `connected` (green) / `offline`
  (red); the line reads `working…` while the agent processes.
- The **sessions-panel toggle** (the list icon) — the collapsible
  right sidebar (2026-09-04, the Exa-panel B build).
- The **message-button** — opens the Message Center in a new tab
  (the tab-services' navigation service).
- **Reset** (pill, two-click confirm) — the new-chat rotation:
  `/new` to the runtime + a fresh DB session.
- **Help** — the wiki help `exa-agent` context.

## The socket + the auto-reconnect

The page's WebSocket (the external-agent channel) **auto-reconnects**
with the exponential backoff (1s → 30s cap) — a backend hiccup no
longer strands the page offline until the reload; the ring catch-up
+ the bubble-persistence make the recovery whole. The reconnect
attempts appear in the backend log as fresh `WebSocket client
connected` lines.

## The Report fold

The assistant responses **over 600 chars** fold behind a
**"Report (N chars)"** `<details>` — the same native fold as the
Thinking/Tools; collapsed by default, the click expands the full
markdown. The fold appears when the stream completes (the live text
stays visible while streaming); the short chat stays flat.

## The Speak affordance

Each assistant response carries a **Speak** button in its footer —
the browser's speechSynthesis reads the answer aloud (the ONE
`ttsService` wrapper; one voice at a time — a new Speak cancels the
current; the button toggles to Stop while reading). The click IS the
autoplay gesture, so the manual path always works.

## The conversation

The page reopens onto the last Exa session (the localStorage-
remembered session id), loads its messages, and streams the
agent's replies through the page's own WebSocket
(`/api/v1/external-agent/ws` — the ACP-direct channel). Messages
persist through the sessions' messages endpoint (the `source='exa'`
sessions — separate from the agent surface since the 2026-09-04
source-split). The page's OWN session state rides
`exa-chat-bubbles` (localStorage) — a reload restores the
conversation; the last-writer wins across tabs.

Two collapsible folds render per assistant message — the answer
is never pushed off-screen:

- **Thinking** — the chain-of-thought (`thought` events, the
  ACP adapter's `agent_thought_chunk`), accumulated into the
  message's reasoning metadata.
- **Tools (N)** — the tool-call titles (`tool_call` events),
  with the live count.


## The input (2026-09-03 — the shared macro keyboard + the ACP trio)

The Exa page renders the same `ChatInterface` input as the agent
chat — the surface derives from `agentId === 'exa'`, so the Exa
page keeps its OWN F-topic + A-source selections (the `:exa`-
suffixed localStorage keys). The layout:

- **The macro keyboard row** — F1-F5 / M1-M5 / the F selector /
  A1-A5 (the action-key bank) / the A selector.
- **The ACP trio AFTER the A selector** — the commands-doc button
  (opens the `/wiki/dev-notes/exa-commands` reference in a new
  tab), **⚡ ACP** (the Hermes slash-commands — `/help`, `/skills`,
  `/config`, `/status`, `/memory`, `/sessions`; the click sends
  the command via the ws), and **History** (the session's past
  prompts; the click re-sends). They arrive via ChatInterface's
  `afterAKeys` slot and ride the A-UNIT — never orphaned onto
  their own line.
- **No Attach** — attachment requires a `sessionId`, which the Exa
  page never passes (the lower row holds no attach control here).
- **The send column** — Send on top; **Collapse long responses** +
  **Layout controls** under it. The Layout flyout's session-panel
  item is wired to the page's sessions sidebar (2026-09-04).
- The **stop** (ws-cancel halt) appears in the send column only
  while streaming.

## The timer pickup

The page hears the bus's `timer:*` events and surfaces a
**confirmable hand-off** — a banner above the input with Send /
Discard (never auto-fired; the user's own next prompt supersedes
it).

## The Force Kill

A slim footer under the input: **Force Kill** (two-click confirm)
sends the process-group SIGKILL — for when the gentle Stop
failed; never disabled by the busy state.

## The sessions panel (2026-09-04 — the Exa-panel B build)

The collapsible right sidebar (`w-80` <-> `w-0`, same as the agent
page) hosts the SHARED `SessionManager` widget with
`variant='exa'` — no agent filter, no settings tab, the New button
creates the exa session directly. The page's list is its OWN state
(`exaSessions`, loaded `source='exa'` on open + session change) —
no hub-store involvement. Select = load the session's messages
into the view (the busy flag clears — the view-change supersedes
an in-flight turn). Delete + rename + smart-rename (the
conversation-derived title POST) all wire to `SessionService`.

The ws effect binds ONCE (2026-09-04, the review pass):
`persistMessage` reads the session id from a REF, so switching
sessions no longer closes + reconnects the socket.

## Related

- [[AgentIntegration]] — the Exa Config page (the agent's
  settings).
