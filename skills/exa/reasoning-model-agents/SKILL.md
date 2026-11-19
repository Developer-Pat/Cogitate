---
name: reasoning-model-agents
description: "Configuring agents on REASONING models (the thinking-first families: ox-alpha, R-series, gpt-5 reasoning) — the budget + format traps and how to avoid them. Read BEFORE creating/configuring an agent whose model thinks before it answers. GENERIC — the families change, the failure modes don't."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, agents, reasoning, configuration, executors]
---

# Reasoning-Model Agents (the budget + format traps)

## What a reasoning model does differently

Thinking-first models (ox-alpha, deepseek R1, the -r variants,
gpt-5's reasoning mode) do NOT answer immediately. They stream /
compute a long THINKING phase first, then the answer. Measured
(2026-08-21, ox-alpha): a cron-parsing question needed ~28,000
chars of thinking before ~6,000 chars of answer.

## The two failure modes (both REAL, both hit in production)

1. **THE BUDGET TRAP (the empty reply).** A small max_tokens is
   consumed entirely by the thinking phase; the call finishes with
   finish_reason=length and ZERO content -> the 'no_content'
   toaster + empty reply. The old executor defaults (512 for the
   fast tier) ALL died this way. The greeting worked only because
   a trivial reply needs no thinking — the trap hides until a real
   question is asked.

2. **THE FORMAT TRAP (the silent stream).** The answer can arrive
   in delta.reasoning / delta.reasoning_content (streaming) or
   message.reasoning (non-streaming) instead of content. A
   content-only parser sees chunks but zero text.

## The rules when configuring an agent on a reasoning model

1. **Set max_tokens >= 16000** — explicitly, in the agent's
   parameters. The executors floor it automatically now
   (reasoning_support.py), but set it so the intent is recorded.
2. **Match the tier to the model.** Reasoning models are SLOW
   (ox-alpha took ~103s for a good cron answer). The
   quick-response/shallow tier exists for speed — putting a
   reasoning model there makes the tier a lie. Prefer: shallow =
   chatty model (fast); deep = reasoning model (thorough).
3. **The empty-reply diagnosis.** If a reasoning-model agent
   returns nothing, suspect the budget FIRST (raise max_tokens),
   then the format (is the provider surfacing the answer in a
   reasoning field?). Do not chase the prompt.
4. **The answer latency is the model, not a hang.** A reasoning
   model legitimately takes 30-120s on a hard question. Check the
   usage_log response_time_ms before declaring a freeze.

## The system support (already in place, 2026-08-21)

- `reasoning_support.py` — the shared helpers: is_reasoning_model
  (name-pattern), effective_max_tokens (the 16000 floor),
  extract_response_text (content + reasoning-field fallback).
- ALL executors (LiteLLM/Default/Fast/Hybrid) use the helper; the
  streaming SSE path reads delta.reasoning too.
- The name patterns are the cheap floor; OpenRouter's catalog
  `reasoning` metadata is the long-term signal.
