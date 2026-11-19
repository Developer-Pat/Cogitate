---
title: Services — Cognitive
type: atlas-api
path: wiki/atlas/services/cognitive.md
category: api-atlas
order: 6
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/services, status/active]
---

# Cognitive Services

The cognitive domain owns the pipeline behind agent behavior:
profiles (configuration), memory (facts/state), and vectors
(recall).

## Services

| Service | Responsibility |
|---------|---------------|
| CognitiveProfileService | Pipeline behavior profiles (memory depth, summarization, retrieval) |
| MemoryProfileService | Per-agent memory settings |
| MemoryManager (base + impls) | Agent fact/memory storage (see memory-isolation bugs in todo) |
| Vector stores | `DocVectorStore` + `CodeVectorStore` (sqlite-vec) for RAG + code recall |
| CognitivePipeline | The pipeline runner (profiles → memory → vectors → response) |

## Dependencies (mermaid)

```mermaid
flowchart LR
    API[Cognitive API routers] --> Prof[CognitiveProfileService]
    API --> MemP[MemoryProfileService]
    API --> Vec[Vector Stores]
    Vec --> DB[(sqlite-vec DBs)]
    Pipeline[CognitivePipeline] --> Prof
    Pipeline --> Mem[MemoryManager]
    Pipeline --> Vec
    Pipeline --> PComp[ProviderCompletionService]
```

## Status

**ACTIVE** — the memory/recall backbone. Memory isolation bugs
(facts key, session bleed) tracked in todo.

## Related

- [[atlas/api/routers/cognitive|Cognitive API]]
- [[dev-notes/agents/cognitive-hub|Cognitive Hub]]
