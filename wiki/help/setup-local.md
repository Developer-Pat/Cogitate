---
title: Setup — Local LLM
category: setup-local
subtopic: Setup
order: 2
confidence: high
created: 2026-08-04
tags: [domain/help]
---

# Setup — Local LLM (Ollama)

Ollama serves local models and **powers automatic session titles**
(the title service defaults to `ollama/llama3.2`). If Ollama isn't
running, titles are disabled — chat still works with a cloud key.

## Install & run

```bash
# install
curl -fsSL https://ollama.com/install.sh | sh

# start the daemon
ollama serve

# pull a model (e.g. the one titles use)
ollama pull llama3.2
```

## Notes

- No API key needed — it's local.
- Curated models may exist that aren't pulled yet: they show as
  curated but unverified until you `ollama pull` them.
- See the **Provider Reference & Quirks** help for the full Ollama
  story.
