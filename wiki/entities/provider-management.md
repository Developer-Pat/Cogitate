---
title: Provider Management
type: atlas-entity
path: wiki/entities/provider-management.md
confidence: medium
updated: 2026-08-05
tags: [type/entity, domain/entities]
---

# Provider Management

## Overview

Multi-provider LLM support: openrouter, deepseek, groq, ollama,
ollama_cloud, openai, anthropic. Keys in `.env` (single secrets
store — [[dev-notes/configuration/configuration-surface]]).

## Domain services (domain/providers/)

- **config_service.py** — ProviderConfigService + DefaultProviderService
  (default provider resolution, test_connection).
- **llm_factory.py** — get_llm_from_config dispatch →
  _create_{provider}_client per provider.
- **completion_service.py** — litellm-backed completions
  (to_litellm_kwargs maps ollama_cloud → openai/{model} +
  api_base https://ollama.com/v1).
- **discovery_service.py** — catalog sync per provider
  (discover_ollama_cloud_models etc.); cache via cache_service.
- **curated_models_service.py** — curated list (DB source of truth;
  verified flag).
- **usage_tracker.py** — usage logs + display normalization.
- **env_key_store.py** — .env writer (Keys tab).
- **browsers/clients**: openrouter, deepseek, ollama, ollama_cloud,
  groq clients for catalog browsing.

## UI

ProviderDashboard (5 tabs, Curated first and opening by default:
Curated/Overview/Usage/Health/Keys; the active tab is carried in the URL as `?tab=`),
ProviderModelsBrowser, ModelTable badges (verified), Setup
page. See [[dev-notes/configuration/adding-a-provider]] howto.

## Default-provider resolution chain

`DefaultProviderService` (providers/config_service.py):

1. **DB query**: `select(Provider).where(is_default, is_active)`
   — the default provider is the provider row flagged
   `is_default` + `is_active`.
2. Returns `ProviderConfig.from_model(provider)` (or None when
   unconfigured).
3. **Bootstrap**: `POST /providers/initialize-default` creates the
   default (Ollama) on first run; `GET /providers/default/ready`
   checks usability (key + models).

Consumers: workflows, title generation, chat, agents — all route
through this service (centralized).
