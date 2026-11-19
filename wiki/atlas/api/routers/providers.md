---
title: Providers
type: atlas-api
path: wiki/atlas/api/routers/providers.md
category: api-atlas
order: 1
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/providers, status/active]
---

# Providers — API

> Routers: `backend/app/api/v1/providers/` — 8 modules
> (router, completion_router, config_router, management_router,
> models_router, scheduler_router, usage_router).
> Status: **ACTIVE** — core facility, used by Setup page, Profile
> provider tab, model browsing, default-provider selection.

## Purpose

Manages LLM providers end-to-end: provider **configs** (API keys,
base URLs, models), **managed providers** (the built-in catalog:
openrouter, deepseek, ollama, ollama_cloud, groq), **model
discovery + caching** (browse live catalogs → `provider_model_cache`),
**completion routing** (the `/complete` chain: primary →
fallback chain), **usage tracking** (per-provider/per-model logs →
usage_logs), and **sync scheduling** (periodic model-cache refresh).

Backing services (`backend/app/domain/providers/`):
config_service, completion_service, curated_models_service,
model_browser_service, discovery_service, cache_service,
usage_tracker, scheduler, rate_limiter, llm_factory,
env_key_store, per-provider clients/browsers (openrouter,
deepseek, ollama, ollama_cloud, groq).

## Endpoints

### Config (`config_router` — `/api/v1/providers/config`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/config` | List provider configs |
| `POST` | `/config` | Create provider config |
| `GET` | `/config/{provider_id}` | Get one config |
| `PUT` | `/config/{provider_id}` | Update config (base URL, models, fallback prefs) |
| `DELETE` | `/config/{provider_id}` | Delete config |
| `GET` | `/config/{provider_id}/api-key` | Key status (has key?) — never returns the key |
| `POST` | `/config/{provider_id}/api-key` | Set API key (env-backed via EnvKeyStore) |
| `POST` | `/config/{provider_id}/test` | Test connectivity |
| `POST` | `/config/{provider_id}/sync` | Sync models into cache |

### Managed providers (`management_router` — `/api/v1/providers/managed`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/managed` | List the built-in provider catalog |
| `POST` | `/managed` | Create a managed provider |
| `GET` | `/managed/keys` | Key presence for all providers |
| `GET` | `/managed/{provider_id}` | Get managed provider |
| `PUT` | `/managed/{provider_id}` | Update managed provider |
| `DELETE` | `/managed/{provider_id}` | Delete managed provider |
| `GET` | `/managed/{provider_id}/api-key` | Key status |
| `PUT` | `/managed/{provider_id}/key` | Set key (env-backed) |
| `DELETE` | `/managed/{provider_id}/key` | Clear key |
| `GET` | `/managed/{provider_id}/models` | Models from discovery (live/cache) |
| `POST` | `/managed/{provider_id}/models/refresh` | Force refresh |
| `GET` | `/managed/{provider_id}/models/cache-status` | Cache age/coverage |
| `POST` | `/managed/{provider_id}/test` | Test connectivity |

### Default + health (`management_router` + `completion_router`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/default` | Current default provider |
| `PUT` | `/default` | Set default provider |
| `GET` | `/default/ready` | Is the default usable? (key + models) |
| `POST` | `/initialize-default` | Bootstrap default on first run |
| `GET` | `/health` | Provider health summary (agents) |
| `POST` | `/health/reset` | Reset health flags |
| `GET` | `/quota` | Quota status |
| `POST` | `/rate-limit/reset` | Reset rate-limit state |
| `POST` | `/complete` | Completion with fallback chain (chat + agents use this) |

### Models (`models_router` — `/api/v1/providers/{provider_id}/models`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/{provider_id}/models/browse` | Browse live catalog (paginated) |
| `GET` | `/{provider_id}/models/capabilities` | Filter capabilities |
| `GET` | `/{provider_id}/models/{model_id}` | Model details |
| `GET` | `/ollama/models` | Local Ollama models |
| `GET` | `/ollama/models/{model_name}` | One Ollama model |

### Usage (`usage_router` — `/api/v1/providers/usage`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/usage` | Usage summary |
| `GET` | `/usage/by-provider` | Grouped by provider |
| `GET` | `/usage/by-model` | Grouped by model |
| `GET` | `/usage/cost-breakdown` | Cost view |
| `GET` | `/usage/trend` | Time series |
| `POST` | `/usage/{provider_id}/reset` | Reset usage for a provider |

### Sync schedule (`scheduler_router` — `/api/v1/providers/sync-schedule`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/sync-schedule/{provider_id}` | Current schedule |
| `POST` | `/sync-schedule/{provider_id}` | Set schedule |
| `DELETE` | `/sync-schedule/{provider_id}` | Disable |
| `POST` | `/sync-schedule/{provider_id}/run` | Run sync now |
| `GET` | `/sync-schedule/status/{provider_id}` | Sync status |

### Provider CRUD (`router` — `/api/v1/providers`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/{provider_id}` | Get provider details |
| `POST` | `/{provider_id}/test` | Test connectivity |

## Auth

All endpoints require an authenticated session (no public routes).
API keys never leave the server: they live in `.env` (EnvKeyStore)
and the API only reports key *presence*, never the value.

## Status

**ACTIVE** — core infrastructure. The `/complete` endpoint is the
backbone of chat + agent execution; the Setup page, Profile
provider tab, and model browser all consume this API.

## Related

- [[atlas/ui/components/features/providers/Providers Index|Providers UI components]]
- [[atlas/api/routers/curated-models|Curated Models]] — the human-curated model list
- [[atlas/api/routers/health|Health]] — health endpoints
- [[dev-notes/configuration/adding-a-provider|Adding a Provider (dev-notes)]]
