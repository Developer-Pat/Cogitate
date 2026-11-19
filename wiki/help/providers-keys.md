---
title: Provider API Keys
category: providers-keys
subtopic: Provider Keys
order: 1
confidence: high
created: 2026-08-03
tags: [domain/help]
---

# Provider API Keys

The Keys tab shows where each provider gets its API key and lets you
store, rotate, or clear keys — one place for all providers.

## Key sources

| Badge | Meaning |
|---|---|
| **Env (.env)** | Key comes from the `.env` file (gitignored) — the default for most providers |
| **Stored (DB)** | Key is encrypted at rest on the provider row (Fernet) and takes precedence over .env |
| **None** | No key — local providers (Ollama) need none |

## Actions

- **Set Key** — store a new key for a provider that currently uses
  .env or has none. It is encrypted at rest; after storing, the source
  badge flips to Stored (DB).
- **Rotate** — replace an existing stored key.
- **Clear** — remove the stored key; the provider falls back to .env
  if one is configured there. Local providers have no clear button
  (they need no key).

## Tips

- Keys are never shown back to you — the UI only shows their source.
  The Show/Hide toggle in the entry form lets you verify what you
  typed.
- Storing a key for a provider that currently uses .env makes the
  stored key take precedence. Clear it to go back to .env.
- The Ollama Cloud provider requires a Bearer key from
  https://ollama.com/settings/keys.
