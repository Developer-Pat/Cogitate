---
title: Software Patterns
type: atlas-reference
path: wiki/references/software-patterns.md
confidence: high
updated: 2026-08-16
tags: [type/reference, domain/architecture]
---

# Software Patterns

The design patterns the Cogitate codebase uses, named so a
developer can recognize the shape and know where the pieces live.
Each pattern below describes what it does, why the codebase uses
it, and the concrete instances to look at.

## The ABC → Registry → Factory pattern

The house style for pluggable components: an abstract base class
(ABC) defines the contract, a registry collects the concrete
implementations, and a factory returns the right one. Adding a new
implementation means writing a class that satisfies the ABC and
registering it — no call sites change.

**Instances:**

- [[atlas/services/agents|The repository seam]] —
  `AgentRepository` (ABC) → `DiskAgentRepository` + the
  `get_agent_repository()` factory. The fork boundary: a DB
  implementation plugs in behind the same contract.
- `backend/app/services/cognitive_pipeline/registry.py` — the
  generic registry for pluggable pipeline components.
- `backend/app/workflows/distribution/distributors.py` — the
  distributor set (the builtin factory).

## The lazy singleton pattern

A class with a single shared instance, created on first use via a
`get_instance()` classmethod. Used for expensive, stateless-ish
resources that should exist once.

**Instances:**

- `backend/app/domain/tools/registry.py` — `ToolRegistry.get_instance()`
- `backend/app/domain/tools/builtin/code_vector_store.py` +
  `doc_vector_store.py` — the RAG vector stores

## The service-layer facade

Routers stay thin: an endpoint injects a domain service (via
`Depends(get_*_service)`) and delegates. The service owns the
business logic; the router owns HTTP concerns (status codes,
errors). The API layer is the facade over the domain layer.

**Instances:**

- The [[atlas/api/routers/agents|agents router]] → `AgentService`
  → the repository seam (the same shape across the domain
  routers)

## The white-pages / yellow-pages registry

The two-part agent lookup: a **registry** (unique name → agent —
the white pages) for addressing, and a **selection surface**
(ARM resource cards, filtered by capability — the yellow pages)
for choosing. One resolves, one selects.

**Instances:**

- [[atlas/api/routers/agent-registry|Agent Registry]] —
  `resolve_agent` (strict, white pages)
- [[atlas/api/routers/agents|Agent select]] — `select_agents`
  (the yellow pages / ARM cards)

## The pipeline

A fixed sequence of stages, each pluggable behind a strategy
interface. The cognitive pipeline runs
`context_builder → executor → memory_manager → response_formatter`;
each stage's implementation is chosen by the agent's cognitive
profile.

**Instances:**

- `backend/app/services/cognitive_pipeline/` — the pipeline + the
  strategy registries
- [[atlas/ui/architecture/cognitive-pipeline|cognitive-pipeline
  architecture]]

## Not a pattern

If a module doesn't fit one of these shapes, that's honest — it's
a plain module, and that's fine. Naming a pattern where there is
none is worse than leaving it unnamed.
