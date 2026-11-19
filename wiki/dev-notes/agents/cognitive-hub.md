---
title: Cognitive Hub
type: atlas-devnote
category: agents
order: 3
confidence: stub
updated: 2026-08-05
tags: [type/dev-notes, domain/agents]
---

# Cognitive Hub

Frontend↔backend coordination layer: boot initialization, state
hydration, provider-health polling.

## Current shape

- **Frontend**: `CognitiveHubProvider` (plain React component, NOT a
  context provider — the Zustand store is the source of truth).
  Mounts once at app root, hydrates persisted state, polls provider
  health. See frontend/src/providers/CognitiveHubProvider.tsx.
- **Backend**: hub-related endpoints in the chat/agent APIs + the UI
  State Bridge (useUIStateBridge hook pushes UI state to the backend
  and handles incoming navigation requests).

## Hub state store shape

`cognitiveHubStore` (zustand) holds hub UI state; `useUIStateBridge`
(frontend/src/hooks/useUIStateBridge.ts) is the WebSocket bridge:

- Connects/disconnects the UI-state WebSocket
- Pushes UI state changes (route, sidebar, theme, active
  agent/session)
- Handles incoming **navigation requests** (programmatic nav from
  the backend)
- Exposes `{ isConnected, latestState }`

## Bridge details

WebSocket client: `services/uiStateBridge.ts`. The backend agent
can request frontend navigation via the bridge; the frontend
mirrors its state outward. Connection status is visible
(`isConnected`).tes and the UI Atlas is undecided.
