---
title: Provider Dashboard Overview
category: providers-overview
subtopic: Provider Management
order: 1
confidence: high
created: 2026-08-03
tags: [domain/help]
---

# Provider Dashboard — Overview

The Overview tab lists your configured providers and everything you can do to
each one.

## Provider Cards

Each configured provider shows: name, type, base URL, and status (Active).

- **Edit** — change display name, base URL, or API key. If a key is
  already stored, the field shows a hint; leave blank to keep it.
- **Health** — run the live check and read its report in a dialog (below).
- **Models** — open the model browser for that provider (live discovery
  with search/filter).
- **Sync Settings** — configure automatic model-list synchronization
  (how often the cached catalog refreshes).

## The Health check

**Health** asks the provider itself, right now: the request goes to the
provider's own base URL with its stored key (or the `.env` fallback) and reads
its model list. The dialog reports:

- **Connected** — the provider answered; the message names it and the dialog
  shows the **latency** in milliseconds and how many **models** it serves.
- **Not configured** — no API key for that provider yet. Fix it under Edit or in
  the Keys tab.
- **Unreachable** / **Failed** — the request did not complete; the message says
  what came back, and it is the provider's answer, not a guess.

**Check again** re-runs it in place. A check that fails at chat time will usually
fail here too — this is the fastest way to tell a bad key from a bad model name.

Ollama Cloud needs an API key like any cloud provider; without one the check
reports it as not configured.

## Tips

- **See [Provider Reference & Quirks](providers-reference.md)** for
  per-provider setup gotchas (e.g. Groq's VPN restriction).
- A provider needs a working API key (DB or .env) before it can serve
  models. Ollama (local) needs no key.
- The default model shows in agent setup as the starting point; each
  agent can override it.
- Use the **Curated** tab to manage the human-owned model list that agent
  setup offers — separate from the full catalog here.
