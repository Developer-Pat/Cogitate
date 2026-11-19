---
title: Chat System
type: atlas-entity
path: wiki/entities/chat-system.md
confidence: medium
updated: 2026-08-05
tags: [type/entity, domain/entities]
---

# Chat System

## Overview

Chat is SSE-streamed: the frontend posts to /chat/stream and renders
events as they arrive. Two distinct paths (important):

- **generate_stream** (`POST /chat/stream`) — user chat: SSE
  streaming, session + message persistence, tool execution, trace
  capture.
- **chat_delegate** (`POST /chat/delegate`) — agent-to-agent,
  READ-ONLY: no session/message creation; reads agent config, calls
  the LLM, returns the result (see
  [[dev-notes/agents/multi-agent-chat]]).

## Backend surface (chat/router.py)

- `POST /stream` — the main streaming chat endpoint
- `POST /delegate` — agent-to-agent delegation
- `GET /sessions/{session_id}` — session messages
- `POST /completions` — non-streaming completion
- Attachments + titles have their own routers
  (chat_attachments_router, chat_title_router)

## Frontend flow

1. AgentInteraction page receives the message.
2. useChatStreaming hook initializes the stream; StreamingService
   creates messages + callback chain updates the store.
3. SSE events render incrementally; cognitive traces surface via
   cognitive_sse.py + the CognitiveTraceViewer.

## Streaming details

- SSE format: text/event-stream with Cache-Control no-cache.
- Tool calls tracked via tool_call_tracker.py; traces via
  cognitive_sse.py (see [[dev-notes/tracing/tracing-architecture]]).
- Errors surface as SSE error events — never silent truncation.

## SSE event schema

The full event list + payloads live in
[[dev-notes/tracing/tracing-architecture|Tracing Architecture]]
(cognitive SSE events: context_built, executor_started/progress/
completed, memory_updated, response_formatted, trace_complete).
Chat stream errors surface as SSE error events — never silent.

## Frontend store shape

Chat state: `useChatStreaming` (stream lifecycle) + `streamStore`
(zustand — chunks, status, error) + `useSystemMacrosStore`
(`macroSetsStore.ts`) for macro/topic state (surface-scoped F/A
selections — the legacy `chatMacrosStore` / `topicStore` are
deleted). Server state via TanStack Query. See
[[atlas/ui/stores/Stores Index|Stores]].
