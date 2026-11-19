---
title: Multi-Agent Chat & Delegation
type: atlas-devnote
category: agents
order: 2
confidence: medium
updated: 2026-08-05
tags: [type/dev-notes, domain/agents]
---

# Multi-Agent Chat & Delegation

## Two chat paths (important)

- **generate_stream** (chat/router.py) — user-facing chat: SSE
  streaming, session + message persistence, tool execution.
- **chat_delegate** (chat/router.py, `POST /chat/delegate`) —
  agent-to-agent: READ-ONLY, NO session/message creation. Reads agent
  info, tools, and provider config from the DB, calls the LLM, and
  returns the result. Used for cross-agent calls.

## Delegation semantics

- No session artifacts — the delegate endpoint is a stateless call.
- Uses the target agent's own provider/model config.
- Fallback chains (openrouter → deepseek → ollama) apply per-agent
  when `fallback_enabled` is set (default off — see
  `LiteLLMExecutor._call_with_fallback`).

## Pipeline / conduit interplay

- **Pipeline execution** = the current agent's deep pass
  (context → executor → memory → response) — always runs.
- **Delegation** = explicit handoff via chat_delegate (agent-to-
  agent) — the conduit never auto-delegates (SHALLOW default;
  HYBRID only for genuinely insufficient first passes — short
  content or deep-keyword queries; user picks). See
  [[entities/conduit-routing|Conduit Routing]].
- The multi-agent graph (workflows) + delegation chain run under
  dispatch; the cognitive pipeline is per-agent.

## SSE event schema

The full generate_stream event list + payloads:
[[dev-notes/tracing/tracing-architecture|Tracing Architecture]]
(cognitive SSE events + tool_output + error events).

## The response UX (2026-08-24)

- **THE THINKING FOLD** — the reasoning tokens stream SEPARATELY
  (`delta.reasoning`, content='') and ride the message metadata; the
  bubble renders a collapsible "Thinking" fold (collapsed by default,
  the click toggles) with the clean answer in the bubble. The
  reasoning survives the reload via the `chat_messages.metadata`
  column (the `meta` attr — "metadata" is reserved in the SQLAlchemy
  Declarative API).
- **The model-markdown normalizer** — some models emit `<br>`/`•`
  instead of markdown; the display translates them (the <br> → the
  paragraph break, • → the bullet). The root-cause conduct lives in
  the basic-search skill (format in proper markdown, never HTML).
- **The pipeline indicator settle** — the done event guarantees
  isActive=false (the trace-complete event can miss on the stream
  tail; the spinner would spin forever).
- **The sentence-boundary spacing** — the reasoning streams
  newline-less; the fold spaces the sentence endings for readability.

## The empty-completion chain (generate_stream)

- **The reasoning budget** — the thinking-first model families
  (deepseek-v4, ox-alpha, r1/-r variants) stream reasoning BEFORE
  the answer. A small `max_tokens` (the 512/1024/4096 executor
  caps) is consumed ENTIRELY by the thinking phase → the stream
  ends with `finish_reason=length`, zero content, zero tool calls
  (the empty completion — deterministic: 1026 chunks at the 1024
  cap). The chat route floors the budget for detected reasoning
  models (`effective_max_tokens`, 16k) AFTER the executor-strategy
  caps; non-reasoning models pass through untouched. Detection is
  name-pattern based (`is_reasoning_model`) — a cheap floor, not a
  curated list.
- **The retry** — an empty completion is retried ONCE transparently
  (nothing user-visible was streamed yet).
- **The visible fallback** — when the retry is also empty, the
  router warns ("The tool-path fell back — answering without
  tools") and calls the LLM again NON-streamed with `tools=None`.
  The fallback FORCES `stream=False`: it inherits the request
  kwargs (the api_base/key ride along), and an inherited
  `stream=True` would return a CustomStreamWrapper — reading
  `.choices` on it crashes the fallback into a generic apology.
- **The empty-message guard** — an assistant message with zero
  content is never persisted (the finalization guard refuses).

## The Exa chat (2026-08-25)

- **THE THINKING FOLD** — the external-agent bridge forwards the
  ACP thought chunks (`{type: 'thought'}` from agent_thought_chunk);
  the Exa hook accumulates them into the message metadata
  ('reasoning') — the SAME Thinking fold component as the main chat
  renders them. (The live session; the reload persistence is a
  possible-improvement.)
- **THE QUICK CONSULT (Ask Exa) — REMOVED (2026-09-03)** — the
  chat-bubble consult button is GONE and the
  macro-reload button beside it is gone too;
  `ConsultComposer.tsx` survives in the tree but no page mounts it
  anymore. The Exa consult path now lives on the Exa page (the ACP
  trio on the keyboard row).
- **THE FLICKER FIX** — the tool_call chip update used to REPLACE
  the message content with '' (the bubble blanked on every tool
  call); the metadata-only update (the content-optional) preserves
  the streamed text.
