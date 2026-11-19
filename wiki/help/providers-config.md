---
title: Provider Configuration
category: providers-config
subtopic: Provider Setup
order: 1
confidence: high
created: 2026-08-03
tags: [domain/help]
---

# Add / Edit Provider

Use this form to add a new provider or edit an existing one.

## Fields

- **Provider Name** * — unique identifier (locked when editing; it is
  the provider's identity).
- **Display Name** — human-friendly label shown in the UI.
- **Provider Type** — the integration type (openrouter, ollama, deepseek,
  groq, ollama_cloud, openai, anthropic...). Locked when editing.
- **Base URL** — API endpoint. Pre-filled per type; change only if the
  provider requires a custom endpoint.
- **API Key** — for cloud providers. On edit: if a key is already stored
  the hint says so — leave blank to keep it, or type a new one to
  replace it. Keys are encrypted at rest (DB) or read from .env.
- **Active** — whether the provider is enabled.
- **Priority** — order used for provider fallback chains (lower = first).

## Tips

- Ollama (local) needs no API key and uses http://localhost:11434.
- Ollama Cloud uses https://ollama.com with a Bearer key from
  https://ollama.com/settings/keys.
- After saving, use **Test** on the dashboard to verify connectivity.
