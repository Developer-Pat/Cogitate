---
title: Setup — API Keys
category: setup-keys
subtopic: Setup
order: 3
confidence: high
created: 2026-08-04
updated: 2026-11-20
tags: [domain/help]
---

# Setup — API Keys

A cloud provider needs a key before it can serve anything. Keys live in the project's **.env**, the
app's single secrets store (gitignored, and the app parses it in Python — never `source` it and never
print a value).

## The first row

This tab lists the providers **your install already has**, with the source of each key. A key needs a
provider to belong to, so when the install has **none** the tab offers **Add your first provider** — the
add form opens right here, its type picker fills the name and address in, and the key you paste in that
same form is stored with the row. Once a row exists, keys are managed per row with **Set Key**.

## Sources

| Badge | Meaning |
|---|---|
| **Env (.env)** | The key is in `.env` — what this tab writes |
| **Stored (DB)** | Legacy: an old DB-encrypted value still exists; clear it to go fully `.env` |
| **None** | No key. A local model server needs none. |

## Actions

- **Set Key** — store a key for a provider (writes `.env`, applies immediately, no restart)
- **Rotate** — replace an existing key
- **Clear** — remove it from `.env`; the provider falls back to none

## Provider quirks

- **groq** — may return `403 Access denied` behind a VPN; turn the VPN off and retry.
- **ollama_cloud** — a Bearer key from https://ollama.com/settings/keys; the free tier works without
  a top-up.

A key alone does not make the app answer: the next step is the **default model**. See
**Setup — Default Model**, and the **Installing Cogitate** topic for the whole path.

## Related

- [Setup — Default Model](/wiki/help/setup-model) — the next step
- [Setup — Overview](/wiki/help/setup-overview) — the verdict these steps move
- [Provider Reference & Quirks](/wiki/help/providers-reference) — per-provider behaviour
