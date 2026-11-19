---
title: Configuration Policies
type: atlas-devnote
category: configuration
order: 2
confidence: stub
updated: 2026-08-05
tags: [type/dev-notes, domain/configuration]
---

# Configuration Policies

## Principles

- **.env is the single source for secrets** — provider keys never
  enter the main DB (api_key_encrypted retired from new writes).
- **DB is source of truth for curated data** — config seeds
  (frontend/src/config/curatedModels.ts) are fallback only and must
  match.
- **Migrations are fresh-DB-safe** — never edit historical
  migrations; extend forward.

## Full policy list

1. **Secrets in .env only** — provider keys via EnvKeyStore
   (atomic .env rewrites, 0600); the API reports key presence only.
2. **DB = source of truth for curated data** — curated_models /
   tool registry / agent definitions; frontend seeds are fallback
   and must match.
3. **Migrations fresh-DB-safe** — never edit historical
   migrations; extend forward. Hand-write migrations (autogenerate
   is unsafe here — models-metadata drift).
4. **Default-provider resolution** — is_default + is_active row;
   bootstrap initializes Ollama on first run.
5. **As-is documentation** — docs describe the current system;
   no removal history (the old backlog is archived locally).
6. **CORS configurable** — CORS_ORIGINS in .env; never `source
   .env` in the shell (breaks the JSON parse — read it in Python). expand with the full policy list from
> the old CONFIGURATION_POLICY doc (rewrite-first: validate each
> policy against current code before inclusion). Default-provider
> resolution policy lives in configuration-surface or its own stub.
