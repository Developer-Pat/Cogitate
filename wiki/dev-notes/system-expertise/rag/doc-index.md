---
title: Doc-Index Maintenance
type: atlas-devnote
category: rag
order: 2
confidence: medium
updated: 2026-10-12
tags: [type/dev-notes, domain/rag]
---

# Doc-Index Maintenance

The **topic map** over the same corpus RAG embeds: a small JSON the `doc-index` tool reads, regenerated
after an ingest. It answers *"which page is about this?"* by token match, where RAG answers *"where is
the passage?"* by similarity — the two are complements, and both are derived from `wiki/`.

**The memory graph is NOT part of this page** — it is its own leg of
[[dev-notes/system-expertise/System Expertise Index|System Expertise]]:
[[dev-notes/system-expertise/knowledge-graph|The knowledge graph]].

## Current shape

- `doc_index.py` (`tools/builtin/`) — the tool: loads the JSON, tokenizes a query, searches topics.
- `doc_vector_store.py::_rebuild_doc_index_json(db_path, project_root)` — regenerates the JSON from the
  vector index after an ingest.

## The file

`data/.doc_index.json`, and its shape is `{version, topics}` where `topics` is keyed by the source page
path and each entry carries a description plus `subtopics` (`name → {description, paths[]}`)::

```
{"version": 1,
 "topics": {"Dev Notes.md": {"title": "Dev Notes.Md",
                             "description": "Documentation for Dev Notes.md.",
                             "subtopics": {"Dev Notes": {"description": "...",
                                                         "paths": ["wiki/dev-notes/Dev Notes.md"]}}}}}
```

30 topics at the last regeneration. A missing or corrupt file is reported as an error string rather than
raised — the tool answers "the index is not there", not a traceback.

## How it works

| step | what happens |
|---|---|
| load | `_load_index_from_file()` reads `data/.doc_index.json` |
| order | `_sort_topics()` + `_update_topic_description()` normalise what the tool serves |
| search | `_tokenize()` → `_search_index()` (token-based, no embeddings) |
| rebuild | `_rebuild_doc_index_json()` after an ingest — the file is REPLACED, never edited in place |

## Where it sits

The doc index is a convenience layer for the tools; **the vector index is the retrieval path**
(`search-knowledge`, `/api/v1/rag/search`). `doc-index` is the cheap lookup — no server, no model, no
embedding call — and it is exactly as current as the last ingest.
