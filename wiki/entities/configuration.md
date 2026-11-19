---
title: Configuration
type: atlas-entity
path: wiki/entities/configuration.md
confidence: medium
updated: 2026-08-05
tags: [type/entity, domain/entities]
---

# Configuration

## Overview

Settings in backend/app/core/config.py (pydantic BaseSettings from
env + `.env`). `.env` is the sole secrets store (keys never in the
main DB — api_key_encrypted retired).

## Setting groups

App identity, databases, CORS, default LLM provider/model, provider
keys (openai/anthropic/openrouter/deepseek/groq/ollama_cloud),
encryption (cogitate_encryption_key — required, raises if absent),
sync/uploads, logging/cache.

## Facts

- CORS_ORIGINS is a quoted JSON list in .env — `source .env` breaks
  it; parse in Python.
- Keys editable at runtime via Keys tab (EnvKeyStore — atomic write
  + in-memory settings update, no restart).
- Title service: TITLE_LLM_PROVIDER defaults to local Ollama.

See [[dev-notes/configuration/configuration-surface]] and
[[dev-notes/configuration/policies]].
