---
title: Example — First-Run Readiness Check
type: atlas-example
category: workflows
order: 3
confidence: high
created: 2026-08-10
updated: 2026-08-10
tags: [type/example, domain/workflows]
---

# Example: First-Run Readiness Check (`readiness-check`)

> What it is: the "is my instance OK?" answer. On demand, it runs
> the full POST health suite — LLM connectivity, database access,
> API server, system config, tool tracker — plus provider keys,
> active agents, and curated models. One file, instant verdict.

## Why you'd use it

After setup, before launch, or when something feels off. It's the
first thing to run — and the TestingDashboard fires it for
immediate results.

## Real output

Live 2026-08-10:

```markdown
# First-Run Readiness — 2026-08-10T01:38:04Z

## Readiness Report

- POST health suite: 5 passed / 0 failed
- Providers: 5 configured
  - ollama (ollama) active=True key: n/a
  - openrouter (openrouter) active=True key: env
  - deepseek (deepseek) active=True key: env
  - groq (groq) active=True key: env
  - ollama_cloud (ollama_cloud) active=True key: env
- Agents active: 17 · Curated models: 38
```

## How to read it

- The POST suite line is the headline — 5/5 pass = healthy
- `key: env` — provider key is in `.env` (the secrets store)
- `key: MISSING` — a provider that needs configuring before it
  can make calls
- `key: n/a` — local provider (Ollama), no key needed

## Run it

`POST /api/v1/workflows/execute` with `template_id:
readiness-check` — or the TestingDashboard button.

## Related

- [[dev-notes/workflows/monitor-family|Monitor Workflow Family]]
