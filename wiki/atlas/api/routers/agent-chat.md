---
title: Agent Chat
type: atlas-api
path: wiki/atlas/api/routers/agent-chat.md
category: api-atlas
order: 7
confidence: medium
updated: 2026-09-15
tags: [type/api, domain/agent-chat, status/active]
---

# Agent Chat — API

> Router: `backend/app/api/v1/agent_chat/router.py`.
> Status: **ACTIVE** — agent-to-agent chat (the
> `chat_delegate`-style inter-agent communication).

## Purpose

Agent-to-agent conversation: the primary channel is a **WebSocket**
(`/api/v1/agent-chat/ws`) for live agent chat (SSE-style message
streams, UI state bridge). HTTP surface: **presets** CRUD +
export/import (named agent-chat configurations), plus a UI-state
WebSocket.

## Endpoints (HTTP)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/agent-chat/presets` | List presets |
| `GET` | `/agent-chat/presets/{preset_id}` | Get one |
| `POST` | `/agent-chat/presets` | Create |
| `PUT` | `/agent-chat/presets/{preset_id}` | Update |
| `DELETE` | `/agent-chat/presets/{preset_id}` | Delete |
| `GET` | `/agent-chat/presets/export/all` | Export all |
| `POST` | `/agent-chat/presets/import` | Import presets |
| `POST` | `/agent-chat/ui-navigate` | Move the user's view to a route — body `{route, replace}`; broadcasts `navigation_request` to every connected UI-socket client |

### `/agent-chat/ui-navigate` — the navigation channel

The one endpoint through which a **backend or an external agent moves the
frontend**. It returns immediately; the navigation happens asynchronously on the
client, so the response confirms the broadcast, not the move.

This is an HTTP surface rather than a registry tool **by necessity**: the
external agent (Exa) runs as its own process with its own tool list — the client
spawns it with `mcpServers: []` — so Cogitate's tool registry is unreachable by
it. Endpoints are how host capability reaches that agent.

See [[dev-notes/frontend/app-navigation-channels|Navigating the app]] for the
three channels a destination can open through.

## WebSockets

- `/api/v1/agent-chat/ws` — agent chat stream (messages, events)
- `/api/v1/agent-chat/ws/ui` — UI state bridge (frontend sync)

## Auth

HTTP endpoints require a session; the agent-chat WS authenticates
on connect.

## Status

**ACTIVE** — the agent chat surface (chat_delegate path in
`chat/router.py` also drives agent-to-agent messages).

## Related

- [[atlas/api/routers/chat|Chat]] — user chat (/stream, /delegate)
- [[atlas/api/routers/agent-registry|Agent Registry]]
- [[dev-notes/agents/multi-agent-chat|Multi-Agent Chat (dev-notes)]]
