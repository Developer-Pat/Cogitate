---
title: Cognitive Pipeline
category: cognitive-pipeline
subtopic: Overview
order: 1
confidence: high
updated: 2026-11-27
created: 2026-07-27
tags: [domain/help]
---

# Cognitive Pipeline

The cognitive pipeline is the message processing system that handles how agents think, reason, and respond.

## Pipeline Stages

1. **Context Builder** — Assembles conversation history and relevant context
2. **Executor** — Routes to the LLM with tool access
3. **Memory Manager** — Stores/retrieves facts and conversation turns
4. **Response Formatter** — Formats the output

## Cognitive Profiles

Profiles define how an agent processes messages using a **part code** system: `{context}-{executor}-{format}-{memory}`

### Part Code Reference

| Code | Context | Executor | Format | Memory |
|------|---------|----------|--------|--------|
| d | default | default | default | in-memory |
| m | minimal | fast | direct_yield | none |
| a | augmented | hybrid | structured | — |
| s | skill_aware | structured | — | kv_store (sqlite) |

### Available Profiles

| Profile | Part Code | Use Case |
|---------|-----------|----------|
| conversational | d-d-d-d | General chat |
| quick-response | m-f-y-n | Simple Q&A |
| research-std | a-h-s-d | One-shot research |
| balanced-chat | d-h-d-d | Two-pass reasoning |
| code-gen | m-h-d-n | Code generation |
| research-pro | s-h-d-k | Deep research with persistent memory |
| system-admin | s-h-d-k | System management with persistent memory |

### Choosing a Profile
- **conversational** — default for most agents, good all-rounder
- **research-pro / system-admin** — when you need the agent to remember facts across sessions (SQLite-backed)
- **quick-response** — stateless, fast responses, no tool use
- **code-gen** — optimized for code output, no memory overhead

## Conduit Routing

The conduit decides how to process each message (SHALLOW by
default):

- **SHALLOW (default)** — the tool loop's result IS the answer;
  no second pass. Tool-using turns route here — the streaming
  tool loop already runs until the model writes its final text.
- **HYBRID** — only when the agent's profile uses the hybrid
  executor AND the turn asks for depth (a deep-keyword query like
  analyze/compare/why) or the first pass was cut at the output
  budget. Answer length is not a trigger. The deep pass REPLACES
  the first pass — it never appends.

## Memory Profiles

- **default** — In-memory sliding window (50 turns)
- **kv_store** — SQLite-backed persistent memory, per-agent DBs for deep agents
- **noop** — No memory at all

## Tips
- Hybrid executor enables tool use + multi-turn reasoning
- Per-agent memory requires kv_store profile + deep agent configuration
- Sessions are isolated per agent switch (no bleed between agents)

## See Also
- [[cognitive-profiles]] — Full profile catalogue
- [[diagrams/agent-pipeline-flow]] — Visual pipeline diagram
