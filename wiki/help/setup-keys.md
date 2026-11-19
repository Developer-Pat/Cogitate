---
title: Setup — API Keys
category: setup-keys
subtopic: Setup
order: 3
confidence: high
created: 2026-08-04
tags: [domain/help]
---

# Setup — API Keys

Cloud providers need an API key. Keys are stored in the **.env file**
(the app's single secrets store, gitignored + file-permission
protected) — the Keys tab writes it for you.

## Sources

| Badge | Meaning |
|---|---|
| **Env (.env)** | Key is in the .env file — what the Keys tab writes |
| **Stored (DB)** | Legacy: an old DB-encrypted value exists; clear it to go fully .env |
| **None** | No key — local Ollama needs none |

## Actions

- **Set Key** — store a key for a provider (writes .env, applies
  immediately, no restart)
- **Rotate** — replace an existing key
- **Clear** — remove the key from .env (provider falls back to none)

## Provider quirks

- **groq** — may return `403 Access denied` behind a VPN; disable the
  VPN and retry. See Provider Reference & Quirks.
- **ollama_cloud** — Bearer key from https://ollama.com/settings/keys;
  free tier works without top-up.
