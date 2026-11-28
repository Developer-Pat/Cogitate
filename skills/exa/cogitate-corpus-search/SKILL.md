---
name: cogitate-corpus-search
description: "Use when a question is about what the Cogitate corpus SAYS — search the RAG index first (POST /rag/search), cite source › heading, then verify against the file."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, rag, retrieval, wiki, search]
---

# Cogitate Corpus Search

Cogitate keeps a **vector index over `wiki/`** — 623 documents, ~4 700 chunks, embedded with
`nomic-embed-text`. It is the fastest way to find *where the corpus discusses something*, and it is
the one leg that answers "which pages talk about this" without reading them all.

**Search it before you grep.** A file read tells you what one file says; the index tells you which
files are worth reading.

## The call

```bash
curl -s -X POST http://localhost:8000/api/v1/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "how turns are compacted", "top_k": 5}'
```

Response: `{"hits": [{"source": "wiki/help/cognitive-pipeline.md", "heading": "Conduit Routing",
"score": 0.897, "snippet": "…"}], "count": 5}` — `source` is relative to the repo root.

Use it when the question is conceptual or open ("how does X work", "what did we decide about X",
"where is the passage about X", "which pages cover X"). Phrase the query as the idea, not as a
keyword — similarity search rewards meaning.

## Then verify, and say which leg you used

The index is **derived** and can lag the files. So:

1. Search first.
2. Open the hits you intend to use (`read_file`) and check the claim still holds.
3. Cite as `path › heading`, and say whether the answer came **from the index** or **from the file**.
   If the two disagree, the FILE wins — the index is only as current as its last ingest.

## When NOT to search

- **Live state** — counts, "is it running", "what model" → the status routes
  (`/api/v1/rag/status`, `/api/v1/external-agent/status`, `/health`). The index cannot know them.
- **An exact symbol or line** — `grep` and `read_file` are precise; similarity is not.
- **A question about the index itself** — read `/api/v1/rag/status` and say the numbers.

## Health, if a search looks wrong

`GET /api/v1/rag/status` → `indexed_documents`, `total_chunks`, `embedding_model`, `index_width`,
`health_note`. If `health_note` is set, or `embedding_model` is null while chunks exist, the index is
mismatched with its configuration: report that, do not pretend the results are complete. A `POST
/api/v1/rag/ingest` with `{"mode": "heal"}` repairs documents whose chunk counts drifted.
