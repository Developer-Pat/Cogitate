---
title: Chat
type: atlas-api
path: wiki/atlas/api/routers/chat.md
category: api-atlas
order: 9
confidence: medium
updated: 2026-08-14
tags: [type/api, domain/chat, status/active]
---

# Chat — API

> Router: `backend/app/api/v1/chat/` — router + streaming +
> attachments_router + title_router.
> Status: **ACTIVE** — the user-facing chat surface.

## Purpose

User chat: **streaming** (`/chat/stream` — SSE token stream),
**delegate** (`/chat/delegate` — agent-to-agent handoff),
**completions** (non-streaming), **sessions**, **attachments**
(upload/list/get/download/delete per session), and **title
generation** (auto session titles + metrics).

## Endpoints

### Chat

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chat/stream` | SSE streaming chat (the main path) |
| `POST` | `/chat/delegate` | Delegate to another agent |
| `POST` | `/chat/completions` | Non-streaming completion |
| `GET` | `/chat/sessions/{session_id}` | Get session |

### Attachments (`attachments_router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chat/{session_id}/attachments/batch` | Upload batch |
| `GET` | `/chat/{session_id}/attachments/{attachment_id}` | Get |
| `GET` | `/chat/{session_id}/attachments/{attachment_id}/download` | Download |
| `DELETE` | `/chat/{session_id}/attachments/{attachment_id}` | Delete |

### Titles (`title_router.py`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/chat/generate-title` | Generate session title |
| `GET` | `/chat/title/metrics` | Title-gen metrics |
| `GET` | `/chat/title-service/status` | Title service health |

## Behavior notes

- **Ollama provider remap (2026-08-14)**: the DB stores provider
  `ollama` (base_url lookup), but LiteLLM's `ollama` provider is
  classified function-UNSUPPORTED (forces format=json, tools as
  prompt text — tool calls silently become JSON content in
  streaming). `litellm_route.litellm_model_string()` — the domain's ONE
  mapping — remaps the LiteLLM model string to `ollama_chat/...` (the
  tool-capable handler), applied in the stream path, the delegate path and
  the failover rebuild. See the Known Issues entry for the full
  investigation.

## Auth

All endpoints require an authenticated session. Attachments are
session-scoped.

## Status

**ACTIVE** — the primary user interface surface (Chat page).

## Related

- [[atlas/ui/components/features/agentInteraction/ChatInterface|ChatInterface]]
- [[atlas/api/routers/agent-chat|Agent Chat]] — agent-to-agent
- [[dev-notes/frontend/attachment-system|Attachment System (dev-notes)]]
