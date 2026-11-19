---
title: Configuration Surface
type: atlas-devnote
category: configuration
order: 1
confidence: medium
updated: 2026-11-18
tags: [type/dev-notes, domain/configuration]
---

# Configuration Surface

## Overview

Application settings are declared in `Settings`
(backend/app/core/config.py) — a pydantic BaseSettings model loaded
from environment variables + `.env`. **The .env file is the sole
secrets store** (2026-08-04 decision): provider API keys live there,
never in the main DB.

## Setting groups

- **App identity**: app_name, app_version, debug, environment,
  host, port
- **Databases**: database_url, documents_database_url, db_echo
- **CORS**: cors_origins (list — quoted JSON in .env), credentials,
  methods, headers
- **Default LLM**: `default_llm_provider` / `default_llm_model` — both **empty, and read by
  nothing**. Which service answers a request is a capability's answer (`capabilities.<KEY>`) or the
  provider row that serves the model; a field here would be a second home for that decision.
- **Provider keys**: openai/anthropic/openrouter/deepseek/groq/
  ollama_cloud_api_key, tavily_api_key
- **Encryption**: cogitate_encryption_key (Fernet — required; the
  service raises rather than silently generating random keys)
- **Sync/uploads**: default_sync_interval_hours, max_upload_size,
  allowed_image_types, profile_images_dir
- **Logging/cache**: log_level, log_file, cache_ttl_seconds

There is no address setting, and no embedding-model setting either. `ollama_base_url` was a setting
until it was retired: an address the app dials is a **decision**, so the row carries it and
`provider_endpoints.resolve_endpoint` resolves it — a settings field would be the second home for one
address, and the local embedding server's issue page is the record of that ruling
(`wiki/issues/resolved/embedded-service-literals/local-embedding-server.md`). A provider **type's** own endpoint is the other half, and it
lives in ONE registry (`domain/providers/provider_endpoints.py`): a row's `base_url` always wins, the
registry answers for a row that declares none, and `resolve_endpoint` **logs** that omission so a
configuration gap cannot pass for a chosen address. The model that produces embeddings is the same class of
decision, so it lives in the **`embeddings` capability**, which names the row AND the model and
derives the vector width from the model (`domain/providers/embeddings.py`,
`wiki/issues/resolved/embedded-service-literals/embedding-model-and-dims.md`). A fresh install ships that capability EMPTY: the seed
carries structure, and a value — a model name — is a setup offer the user accepts, declines or
replaces. What is genuinely this config's own stays here: `embedding_batch_size` and `doc_index_path`.

## The startup work toggles

Two switches decide whether the application does system work at boot and whether
anything consumes it. Both default **off**:

| setting | default | controls |
|---|---|---|
| `STARTUP_SWEEP_ENABLED` | `false` | the boot-time system-audit sweep |
| `EXA_BACKGROUND_PROCESSING_ENABLED` | `false` | the workspace drain |

They are **coupled**: with the drain off, the sweep is held rather than
scheduled. The behaviour, the coupling, and why you would use either are
documented once, in
[[dev-notes/lifecycle/background-work|Background Work]] — this surface keeps only
the names and the defaults.

### Launcher overrides

`cogitate.sh` starts the backend with two environment overrides for development:

- `INBOX_PROCESSOR_INTERVAL_SECONDS=20` — the drain's period (the code default is 900)
- `SYSTEM_SWEEP_DELAY_SECONDS=15` — the sweep's delay after boot (the code default is 60)

## The generated example file, and the rule that keeps it true

`.env.example` at the repository root is **generated, never hand-edited**. It is built from `Settings` itself by
`scripts/dev/generate_env_example.py`, so the file that a newcomer copies cannot disagree with the model that
reads it:

| rule | why |
|---|---|
| **the env name is the field name, upper-cased**, with no prefix (`max_upload_size` → `MAX_UPLOAD_SIZE`) | pydantic-settings' default; a prefix would be a second naming convention |
| **a default derived from the project root is written commented out** (`DATABASE_URL`, `DOCUMENTS_DATABASE_URL`, `PROFILE_IMAGES_DIR`, `LOG_FILE`) | a machine path must never ship, and an empty value would break the URL parse |
| **a secret gets an empty assignment** (`*_KEY`, `*_TOKEN`, `*_SECRET`) | `.env` is the only store; a default secret in a shipped file is a leak with a nice name |
| **every other default is written out** | every field has one, and the app runs with no `.env` at all — the file exists to be tuned, not to be required |
| **a key read outside `Settings` is listed by hand in `REGISTERED`** | walking the model cannot see `os.getenv`; each entry carries the reader's path so the list stays checkable |

`--check` fails when the file and the settings disagree, and it runs in the **pre-commit hook** and in
`scripts/testing/verify_flat_tree.sh`, beside the script catalog. Two consequences worth knowing: a hand edit to
`.env.example` is rejected, and **a new `Settings` field fails the gate until the file is regenerated** — which
is the point, because a field added and forgotten is exactly how the file drifted before.

**Adding a key, in order:** declare the field on `Settings` with a default (and a docstring comment where the
name is not self-explanatory); if it is read with `os.getenv` instead, add it to `REGISTERED` with its reader;
then `python3 scripts/dev/generate_env_example.py`. Do not edit the file by hand.

**Where the values are read from.** `Settings` loads `BASE_DIR / ".env"` — the **project root**, by path, not
`".env"` relative to the process cwd. That matters because `cogitate.sh` changes into `backend/` before uvicorn:
a cwd-relative `.env` names a file this repository does not have, and configuration used to arrive anyway only
because litellm calls `load_dotenv()` at import and that walks up to the root file. The anchored path keeps the
store identical to the one `EnvKeyStore` writes and the one the installer tells you to create, and it no longer
depends on import order. A `backend/.env` is **not** read; `backend/.env.example` is a pointer stub kept only
for older instructions.

## Key facts

- `.env` is gitignored; values load at startup via pydantic.
- Keys are editable at runtime through the Keys tab (Provider
  Dashboard), which writes .env atomically + updates the cached
  settings instance (no restart needed) — see EnvKeyStore.
- Shell gotcha: `source .env` pollutes the env (CORS_ORIGINS loses
  its quotes → pydantic JSON-decode failure). Parse .env in Python
  instead.
