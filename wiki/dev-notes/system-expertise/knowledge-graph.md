---
title: The knowledge graph
type: atlas-devnote
category: system-expertise
order: 2
confidence: high
updated: 2026-10-12
tags: [type/dev-notes, domain/system-expertise]
---

# The knowledge graph

**The topology leg of [[dev-notes/system-expertise/System Expertise Index|System Expertise]]**: *how is
this connected to that?* It answers with a walk, not with a passage — the question it exists for is the
one RAG cannot hear (`what fires this workflow?`, `what else references this agent?`).

**Measured 2026-10-12 on the live install:** 825 nodes / 1926 edges combined — **189 / 966** from the
derived leg and **636 / 960** from the wiki leg. The figures move with the data: they are a reading of
the system at a moment, not a property of it.

## The seam

`backend/app/domain/graph/` holds the contract, and it is the house pattern — an ABC, the
implementations, and a facade that composes them:

```
GraphProvider (ABC)          get_entity · get_neighbors · get_topology
├── DerivedGraphProvider     the live database's own structure
└── WikiGraphProvider        the corpus's pages and links
GraphService([providers])    one surface over both
```

`GraphService` fans a query across its providers and merges the edges. **SQLite today, a real graph
store behind the interface when the fork earns it** — the seam is the point, and the industrial version
swaps the implementation without moving the callers.

## The derived leg — the schema IS a graph

`DerivedGraphProvider` walks **declared foreign keys on demand**: it reads `pragma_foreign_key_list`,
so the walk is a VIEW of the live database rather than a copy of it. A node kind comes from a table map
(`agent`, `collection`, `composition`, `macro`, `provider`, `session`, `tool`, `trigger`, `workflow` —
measured).

**The semantic-edge layer is the part worth knowing about.** The declared FKs miss the most important
relationships, because some of the app's real connections are not foreign keys at all:
`workflow_triggers` declares no FK, so a declared-only walk loses `trigger → workflow` — the edge that
answers *"what fires this?"*. The semantic layer walks those implicit relationships explicitly and
labels them (`fires`). Its own comment says why: *a declared-only walk misses triggers→templates*.

Measured on the live install: `agent-hello` → **3 edges** (all `fires`).

## The wiki leg of the graph — the corpus's own links

`WikiGraphProvider` builds the **knowledge graph of the docs**: every page is a node (id = its path,
carrying its title and category) and its **hard wikilinks** are edges. Wikilinks resolve by the same
rule the atlas validator and the viewer use — exact path → title → directory index — so the graph agrees
with what a reader clicking the link would get.

That makes it the fast way to answer *"what points at this page?"* — including the pages whose
frontmatter `category` groups them but which no index lists.

## How it is reached

| surface | what it serves |
|---|---|
| **`graph-query`** (the tool registry) | the neighbours/edges of an entity, plus an honest `not_found` |
| **`GET /api/v1/knowledge/graph?entity=…`** | the same capability over HTTP, for Exa (a registry tool is unreachable from its Hermes session) |

**ONE capability, TWO consumers** — Exa and the app's own agents — which is the same shape as every
other leg of this topic. The HTTP route has **no atlas page yet**; the tool is assigned to the app's
agents by `scripts/core/provision_expertise_tools.py`.

## What it is NOT

- **Not a stored graph.** Nothing is materialized: the derived leg reads the DB at query time (always
  true, never stale — at the cost of a walk), and the wiki leg re-parses the corpus. A materialized
  table is a later option, not a current fact.
- **Not a semantic search.** It walks structural and link relationships; it does not know that two
  differently-named things are the same thing. That is the research frontier this page names rather
  than claims.
- **Not the memory system.** Per-agent memory and facts live elsewhere; this is the system's topology.
