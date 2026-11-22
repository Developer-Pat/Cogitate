---
title: Provider API Keys
category: providers-keys
subtopic: Provider Keys
order: 1
confidence: high
created: 2026-08-03
updated: 2026-11-22
tags: [domain/help]
---

# Provider API Keys

A cloud provider needs a key before it can serve anything. Two doors write the SAME store — **Setup → API
Keys** (`/setup?tab=keys`) for the install's first key, and a **provider row's Edit form** on Cloud Providers
for any provider afterwards — and both write the project's `.env`, the app's single secrets store.

## Key sources

| Badge | Meaning |
|---|---|
| **Env (.env)** | The key is in `.env` — what both doors write |
| **Stored (DB)** | Legacy: an older DB-encrypted value still exists and still answers; clear it to go fully `.env` |
| **None** | No key. A local model server needs none. |

## Actions

- **Set Key** — store a key for a provider. It writes `.env` and applies immediately: no restart.
- **Rotate** — replace an existing key.
- **Clear** — remove the key from `.env` (a legacy DB value is what Clear removes first); the provider
  then falls back to none. Local providers have no clear button — they need no key.

## Tips

- Keys are never shown back to you — the UI shows their source only. The Show/Hide toggle in the entry
  form lets you verify what you typed.
- **groq** may return `403 Access denied` behind a VPN; turn the VPN off and retry.
- **ollama_cloud** needs a Bearer key from https://ollama.com/settings/keys; the free tier works without
  a top-up.

## Related

- [Setup — API Keys](/wiki/help/setup-keys) — the setup step that uses this store first
- [Default Provider](/wiki/help/providers-default) — the model a key makes usable
- [Provider Reference & Quirks](/wiki/help/providers-reference) — per-provider behaviour
