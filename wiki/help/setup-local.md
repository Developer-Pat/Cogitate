---
title: Setup — Local LLM
category: setup-local
subtopic: Setup
order: 3
confidence: high
created: 2026-08-04
updated: 2026-11-21
tags: [domain/help]
---

# Setup — Local LLM (Ollama)

A model server on this machine can be the default instead of a cloud key. Nothing requires it — if
you have a key, skip this tab.

## Run it

```bash
# install
curl -fsSL https://ollama.com/install.sh | sh

# start the daemon
ollama serve

# pull a model
ollama pull llama3.2
```

## Point Cogitate at it

1. On the **Provider Dashboard**, add a provider of type `ollama` (the Add Provider form prefills
   the address).
2. Set it as the **default provider** and pick one of the models the server reports.

A local server needs **no key**: a loopback address is what makes the readiness check count it.

## Notes

- Curated models that are not pulled yet show as curated but unverified until `ollama pull`.
- The full Ollama story — including its cloud sibling, `ollama_cloud`, whose API root differs from
  the native one — is in **Provider Reference & Quirks**.

## Related

- [Setup — Default Model](/wiki/help/setup-model) — where the local server becomes the default
- [Provider Reference & Quirks](/wiki/help/providers-reference) — the Ollama family in full
