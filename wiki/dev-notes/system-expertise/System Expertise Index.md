---
title: System Expertise
type: atlas-index
category: system-expertise
order: 1
confidence: high
updated: 2026-10-12
tags: [type/index, domain/system-expertise]
---

# System Expertise

**What this is.** Everything the app knows about ITSELF, in three surfaces that answer three different
kinds of question. Together they are what a system agent — Exa, or one of the app's own agents — reads
before it acts, and the whole point is that the answers come from the running system rather than from
anyone's memory of it.

**The pattern, in the user's words:** *"the wiki/RAG/graph three-legged pattern"* — and the working
definition of expertise is **knowledge + tools + the verify-discipline**
(a local backlog note). Knowledge alone is a library; the tools are what make it actionable, and
the verify step is what keeps a claim from being mistaken for a fact.

## The three legs

| leg | the question it answers | its home | the tool / route that serves it |
|---|---|---|---|
| **the wiki** | *what is written down about this?* | `wiki/` — the tracked markdown corpus | it IS the corpus; the surfaces below index it |
| **RAG** | *where in the corpus is the passage about this?* | the vector index, `data/system_docs_vector.db` | `search-knowledge` · `GET /api/v1/rag/search` |
| **the graph** | *how is this connected to that?* | `backend/app/domain/graph/` — two providers | `graph-query` · `GET /api/v1/knowledge/graph` |

**The wiki is the only source of truth among them.** RAG and the graph are DERIVED: the vector index
is rebuilt from the corpus, and the graph is walked from the live database and the corpus's own links.
So they can be stale — the index's currency is a policy decision (nothing auto-reingests), and a graph
edge is only as true as the schema and links it was read from. When a derived leg disagrees with the
corpus, the corpus wins.

**Each leg answers a different KIND of question, and using the wrong one is how a wrong answer gets
built.** A passage lookup (RAG) does not tell you what fires a workflow; a topology walk (the graph)
does not quote anything. The pages under this topic say which is which.

## Pages

- [[dev-notes/system-expertise/rag/RAG Index|RAG]] — the retrieval leg: the wiki index, the ingest, the
  embedding service, and what `/rag/status` reports.
- [[dev-notes/system-expertise/knowledge-graph|The knowledge graph]] — the topology leg: the derived FK
  walk, the wiki link graph, and what the two providers are each good for.

## Who reads it

- **Exa** (the system agent) over HTTP: the same two capabilities are exposed as routes
  (`/api/v1/rag/search`, `/api/v1/knowledge/graph`) because a tool registered in the internal registry
  is unreachable from its Hermes session.
- **The app's own agents** through the tool registry — one capability, two consumers. The provisioning
  script that assigns them is `scripts/core/provision_expertise_tools.py`: `graph-query`,
  `search-knowledge`, `verify-backend-health`, `verify-trigger-config`, `set-trigger-schedule`, with
  `restart-backend` deliberately EXCLUDED (admin tier — the app's agents do not get raw restart power).

## The verify-discipline (the reason this is "expertise" and not "a search box")

An answer from either derived leg is a CLAIM until it is read back. The surfaces that make that
concrete:

- `verify-backend-health` / `verify-trigger-config` — read-back after an operation, so "done" means
  observed, not attempted;
- the verification store (`verification_evidence.db`) — the track record, including the runs where a
  claim did not survive its check;
- `wiki/dev-notes/external-agent/capabilities.md` — the system agent's own capability set and its known
  gaps, and `wiki/dev-notes/design/honesty-loop.md` — the loop this discipline belongs to.

## Related, and not this topic

- **`dev-notes/external-agent/`** — the Exa integration itself (its skills, its sandbox, its known
  issues). Exa CONSUMES this layer; it is not part of it.
- **`atlas/api/routers/rag.md`** — the API atlas page for the RAG routes. The graph's HTTP route
  (`/api/v1/knowledge/graph`) has no atlas page yet.
