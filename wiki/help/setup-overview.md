---
title: Setup Overview
category: setup-overview
subtopic: Setup
order: 1
confidence: high
created: 2026-08-04
tags: [domain/help]
---

# Setup — Overview

The Overview tab is the **doctor**: it shows a live checklist of what
Cogitate needs before you can chat.

## The checklist

| Item | What it means |
|---|---|
| **Local LLM running** | Ollama (local) powers session titles. Without it, titles are disabled. |
| **API keys** | Cloud providers (openrouter, deepseek, groq, ollama_cloud) need a key to serve models. |
| **Default model** | The provider + model used when nothing else is chosen. |
| **Starter agent** | A capability profile that powers your first chat. |

- ✅ = configured · ⚠️ = partially configured / warning · ⏳ = not done
- **Click any item to jump to its tab** — what's missing is what you
  do next.
- Keys live in the **.env file** (the app's single secrets store) —
  the API Keys tab writes there for you.
- Full management lives on the **Provider Dashboard**.
