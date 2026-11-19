---
title: Tab Services
type: atlas-devnote
category: frontend
order: 6
confidence: high
tags: [type/dev-notes, domain/frontend, domain/external-agent]
---

# Tab Services

The frontend's cross-tab layer (`frontend/src/services/crossTab/`):
one BroadcastChannel harness + the navigation service (the simple
new-tab model).

## The harness — `crossTab.ts`

The singleton `BroadcastChannel('cogitate-tabs')` wrapper. One
channel, same-origin only, no server. The message-type: `notify`
(the registry/focus machinery and the session-context service were
removed by design — the session-context transport went with the
engage-flow deletion on 2026-09-04).

## The navigation service — `navigationService.ts`

The simple model (the design decision: the app is a SPA; the
browser's tabs are the navigation). `navigateTo(app)` opens the
destination via `window.open` — the current tab is never touched.
The destinations: exa `/exa`, messages `/messages`, sessions
`/sessions`, agent-chat `/agent-interaction`, wiki `/wiki`.

The consumers:
- The **Exa-button** (the AgentInteraction's header, the icon-
  button) — opens the Exa Agent page (a PLAIN open since 2026-09-04
  — no session-context hand-off; the engage-flow was deprecated as
  too clunky).
- The **message-buttons** (the AgentInteraction + the ExaChat
  headers) — open the Message Center.

## The rejected experiment (the record)

The smart-tab orchestration (the presence-registry, the heartbeat,
the cross-tab focus-switch) was built and removed: the broadcast
route-switch rewrote every tab's page, the browser's focus-policy
is best-effort, and the multi-tab ambiguity isn't worth the
maintenance. The record lives in `local/tab-services/01-study.md`.

## The removed session-context service (the record)

`sessionContextService.ts` (the inter-tab engage-context — the
agent-chat's active session published for the Exa side) was deleted
on 2026-09-04 with the engage-flow it fed: the agent-chat's Exa
button now just opens the Exa page, and the Exa page's
"Engaging from" banner + Diagnose button were removed root-and-
branch (the user's call — no context transfer needed).

## Related

- [[dev-notes/frontend/navigation-routing|Navigation & Routing]]
- [[dev-notes/external-agent/capabilities|Exa Capabilities]]
