---
title: Provider Reference & Quirks
category: providers-reference
subtopic: Provider Management
order: 2
confidence: high
updated: 2026-11-18
created: 2026-08-03
tags: [domain/help]
---

# Provider Reference & Quirks

Each provider has its own setup quirks. This page collects what we know
so you don't have to rediscover it.

## Quick reference

| Provider | Type | Key needed? | Base URL / API | Quirks |
|---|---|---|---|---|
| **ollama** | local | No | `http://localhost:11434` (native `/api`) | Must be running locally; models must be pulled first |
| **openrouter** | cloud | Yes | `https://openrouter.ai/api/v1` | Huge catalog (300+); many free models; `:free` suffix |
| **deepseek** | cloud | Yes | `https://api.deepseek.com` | v4-flash/v4-pro families; cheap |
| **groq** | cloud | Yes | `https://api.groq.com/openai/v1` | **VPN/geo-blocked** — see below; very fast LPU inference |
| **ollama_cloud** | cloud | Yes (Bearer) | `https://ollama.com/v1` (OpenAI-compatible) + `/api/tags` | Free tier works without top-up; model list only via `/api/tags` |
| **openai / anthropic** | cloud | Yes | native | Standard |

## Quirks by provider

### groq — VPN / network restriction (important)
- Groq **blocks connections from many VPNs and cloud-hosted IPs** with
  `HTTP 403: Access denied. Please check your network settings.`
- The key itself is fine — the request never reaches the account layer.
- **If you see the 403**: disable your VPN / use a residential network
  and retry. Measured on one machine: same key, same network — 403 with
  the VPN on, 200 with it off (15 models, 180ms).
- Other providers (OpenRouter, DeepSeek, Ollama Cloud) are NOT blocked
  the same way — a Groq-only 403 is the signature of this quirk.
- Groq models: many are free; `llama-3.3-70b-versatile` is a solid
  general pick.

### ollama (local)
- No API key — the provider is the local daemon. If the Test button
  fails, check `ollama serve` is running.
- Curated models may exist that are **not yet pulled locally** — they
  show as curated but `verified=false` until you `ollama pull` them.

### ollama_cloud
- Uses a **Bearer key** from https://ollama.com/settings/keys.
- OpenAI-compatible at `/v1`, but model *discovery* only works via the
  native `/api/tags` endpoint (the browse path handles this).
- Free tier works without topping up (e.g. `gpt-oss:20b`).
- The base URL redirects (`/v1/models` → 307); the app follows it.

### openrouter
- Broadest catalog; curated picks often use the `:free` suffix for
  zero-cost options.
- Model IDs are namespaced (`nvidia/nemotron-3-super-120b-a12b:free`).

## Key storage note
Provider API keys live either in the **DB (encrypted at rest, via the
Keys tab)** or in the **.env file (gitignored)**. The Keys tab shows
which source each provider uses. A DB-stored key takes precedence over
the .env key.
