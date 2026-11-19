---
title: Message Map
type: atlas-messaging
path: wiki/atlas/messaging/Message map.md
updated: 2026-08-25
confidence: high
tags: [type/atlas, domain/messaging]
---

# Message Map

> **THE WIRES** (2026-08-25, the user's doctrine: "messaging
> centered applications can be brittle — broken links fail
> silently; there are no physical wires to inspect; a signal
> either fires or it doesn't"). This map documents the messaging
> infrastructure so the wires CAN be inspected. If a signal
> should have fired and didn't — start here.

## The infrastructure

- **The bus** (backend `app/domain/messaging/`): an in-memory
  topic bus + a bounded ring buffer. The `publish` tool
  (validated namespaces) fires `topic:payload` to every
  subscriber; the ring keeps the recent events (Phase F — a late
  subscriber replays the ring before the live stream).
- **The SSE stream** (`/api/v1/messaging/stream`): ONE frontend
  connection, ONE union of topics (the `messagingFeed` registers
  the consumers' topic groups). Auto-reconnect with backoff; the
  dynamic topics (e.g. `workflow:<uuid>:started`) are whitelisted.
- **The frontend eventBus** (`services/eventBus`): the in-page
  dispatch — the SSE payloads land here; the hooks subscribe by
  pattern.
- **The ring replay**: on the SSE (re)connect, the backend sends
  the recent buffered events first — the late subscriber catches
  up (why a message "appears after a refresh").

## The topics' catalog

The pattern: `<domain>:<id>:<event>` with the explicit `event`
field in the payload (the discriminator — never guessed from the
shape).

| The topic | The publishers (the backend) | The subscribers (the frontend) | The payload |
|---|---|---|---|
| `notify:*` | the system reports + the toasts (the sweep, the inbox processor, the messaging's publish) | the `useNotifyBridge` -> the notificationStore (the toaster) + the messageStore (the message center!) | the toasts' content + the source (`exa`/`app`) |
| `workflow:*` + `batch:*` | the workflow engine | the `useRunEstimator` + the `useTracePanel` | the workflow statuses |
| `agent:*` | the agents' router (created/updated/deleted!) | the `useAgentSync` -> the hub store (the removal/refresh!) | `{agent_id, agent_name, event}` |
| `session:*` | the sessions' router (created/updated/deleted + the bulk + the clear!) | the `useSessionSync` -> the hub store (the removed/renamed/refreshed!) | `{session_id, title?, event}` |
| `collection:*` | the collections' router | the `useCollectionSync` -> the Collections pages' reloads | `{collection_id, name?, event}` |
| `team:*` | the teams' router (+ the members!) | the `useTeamSync` -> the Teams page's reload | `{team_id, name?, event}` |
| `macro:*` + `meta-topic:*` | the macros' router (the sets + the topics!) | the `useMacroSync` -> the macro store's reload | `{id, name?, event}` |
| `tool:*` + `tool-category:*` | the tools' router | the `useDomainSync('tool')` -> the ToolManagement's reload | `{id, name?, event}` |
| `agent-list:*` | the agent_lists' router | the `useDomainSync('agent-list')` -> the Collections page | `{id, event}` |
| `agent-registry:*` | the agent_registry's router | the `useDomainSync('agent-registry')` -> the AgentProfiles | `{id, event}` |
| `agent-package:*` | the agent_packages' router | the `useDomainSync('agent-package')` -> the AgentProfiles + the PackageTab | `{id, name?, event}` |
| `tool-permission:*` | the tool_permissions' router | the `useDomainSync('tool-permission')` -> the AgentProfiles | `{id, event}` |
| `workflow-list:*` | the workflow_lists' router | the `useDomainSync('workflow-list')` -> the Collections page | `{id, event}` |
| `debug:*` / `diagnostic:*` / `log:*` / `provider:*` / `runtime-config:*` / `setting:*` | the Phase-7 routers (2026-08-25) | **THE GAP — no frontend consumers yet** (the system-internal pages; the announces are the wire, the consumption's the TODO) | `{id, event}` |
| `chat:<session>:<event>` | the chat's events (the messages' lifecycle) | the chat's live surfaces | the chat payloads |

## The wire-flows (the end-to-end chains)

### The session rename (the canonical chain)
The PUT `/api/v1/sessions/{id}` → the router's `_announce("updated", {session_id, title, event})` → the bus → the SSE stream (the `session:*` union) → the `useSessionSync` → the hub store's `renameSessionById` → **every open tab's list updates**. If the rename shows in the mutating tab but not the others: the announce's try/except swallowed it (check the backend log for `❌ session:updated publish failed`) or the topic's missing from the feed union.

### The message-center toast
The sweep's report → the inbox processor judges → the `notify:` publish (the `from: "exa"`) → the SSE → the `useNotifyBridge`'s seen-check (the queue + the tombstones!) → the notificationStore's choke point (the toast + the messageStore's row!) → the bell badge + the dashboard card + the /messages page.

### The agent delete
The DELETE `/api/v1/agents/{id}` → `agent:{id}:deleted` → the `useAgentSync`'s event-switch → the hub store's filtered `setAgents` → the agents' lists everywhere.

## The honesty rules

- **The dead wire check**: a topic in the catalog with NO subscriber listed = the wire's dead (the Phase-7 six today!). The map makes it visible; the sweep's the enforcement.
- **The best-effort announces**: every publish's in a try/except — the sync's a convenience; the refresh is the fallback. The failure LOGS (the `❌ ... publish failed` lines) — the loud-failure rule.
- **The explicit event field**: the discriminator's mandatory — the deleted vs the updated must never be guessed from the payload's shape.

## The related

- The dev-note: the cross-window sync's pattern (wiki/dev-notes/agents/cross-window-sync.md)
- The roadmap: local/cross-window-sync/01-roadmap.md
