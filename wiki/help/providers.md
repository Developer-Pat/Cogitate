---
title: Provider Management
category: providers
subtopic: Overview
order: 1
confidence: high
created: 2026-07-27
tags: [domain/help]
---

# Provider Management

Configure the AI providers that power your agents.

## Supported Providers
- **deepseek** — DeepSeek models (v4-flash, v4-pro, etc.)
- **openrouter** — Multi-model gateway (300+ models)
- **ollama** — Local LLM hosting (no API key)
- **ollama_cloud** — Hosted Ollama (OpenAI-compatible API, Bearer key)
- **groq** — Fast inference (LPU); see quirks — VPN/geo-blocked
- **See also**: [Provider Reference & Quirks](providers-reference.md) — per-provider setup gotchas
- **openai / anthropic** — Native cloud APIs

## Provider Dashboard
- **Curated** — manage the human-owned curated model list (verified flags).
  This is the tab the page OPENS on.
- **Overview** — providers, default model, per-provider actions
- **Usage** — tokens, cost, requests, response times
- **Health** — per-provider connectivity checks
- **Keys** — provider API keys (set, rotate, clear)

## Tips
- Each agent selects its own provider and model — the default is just
  the starting point.
- Model IDs must match what the provider actually serves; the curated
  list is verified against live catalogs (see Curated tab help).
- Cloud providers need an API key (DB or .env); Ollama (local) does not.
- Use the ? help buttons on each tab for task-specific guidance.
