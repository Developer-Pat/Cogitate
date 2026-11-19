---
title: RAG (System Expertise)
type: atlas-index
path: wiki/dev-notes/system-expertise/rag
category: system-expertise
order: 1
confidence: medium
updated: 2026-10-12
tags: [type/index, domain/system-expertise, domain/rag]
---

# RAG — the retrieval leg

The retrieval half of [[dev-notes/system-expertise/System Expertise Index|System Expertise]]: the wiki
index and everything that keeps it answering. **It answers *"where in the corpus is the passage about
this?"* by similarity** — the topic map below is its nearest neighbour, answering *"which page is about
this?"* without embedding anything.

Both are DERIVED from `wiki/`. The corpus is the source; a stale index is a stale answer, which is why
[[dev-notes/system-expertise/System Expertise Index|the topic]] says the wiki wins when they disagree.

## Inventory

- [[dev-notes/system-expertise/rag/rag-system|RAG System]] — the index, the ingest, the embedding
  service, and what the health surface reports.
- [[dev-notes/system-expertise/rag/doc-index|Doc-Index Maintenance]] — the topic map over the same
  corpus: `data/.doc_index.json`, regenerated after an ingest.
