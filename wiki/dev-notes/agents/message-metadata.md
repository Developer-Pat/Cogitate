---
title: Message Metadata
type: atlas-devnote
category: agents
order: 4
confidence: high
updated: 2026-08-07
tags: [type/dev-notes, domain/agents]
---

# Message Metadata

Structured metadata attached to chat messages (beyond text content),
stored in the `chat_messages` table.

## The schema (from `ChatMessage` model)

| Field | Type | Notes |
|-------|------|-------|
| `id` | int | PK |
| `session_id` | int | FK → chat_sessions.id (cascade delete, indexed) |
| `role` | str(20) | 'user' \| 'assistant' \| 'system' (indexed) |
| `content` | text | the message body |
| `token_count` | int? | tokens used (populated by the LLM path) |
| `model` | str(100)? | model that generated the message |
| `provider` | str(50)? | provider name (ollama, openai, deepseek...) |
| `total_time_ms` | float? | generation time in ms |
| `tokens_per_second` | float? | generation speed |
| `created_at` | datetime | server_default func.now(), indexed |

## Which features consume it

- **Usage/history pages** — provider/model/timing fields power the
  History + Usage dashboards
- **Health scan** — usage_logs (not chat_messages) is the health
  source; chat_messages metadata complements but is not the source
  of truth for provider health
- **Session view** — role + content are the conversation; the
  metadata fields ride along for stats

## Verification note

The old message-metadata-developer-guide-2026-03-19 is superseded —
this page is written from the current `ChatMessage` model
(backend/app/infrastructure/database/models.py).
