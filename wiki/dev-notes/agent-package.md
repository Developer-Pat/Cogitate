---
title: The Agent Package
type: atlas-devnote
path: wiki/dev-notes/agent-package.md
category: dev-notes
order: 2
confidence: high
updated: 2026-08-24
tags: [type/dev-notes, domain/agents, domain/tools]
---

# The Agent Package

> The canned, reusable agent blueprint (2026-08-24) — toolkit +
> skillset + the LLM capability contract, as ADVISORY definitional
> metadata. A provisioner (Exa) reads a package and creates an
> agent quickly. The design + roadmap: `local/agent-package/`.

## The terms

| Term | Meaning | Where it lives |
|---|---|---|
| **Toolkit** | The tool surface the agent OWNS | `agents.kit_id` → a tool-typed collection → its granted tools |
| **Skillset** | The skills the agent OWNS | `agents.skills` |
| **Agent Package** | toolkit + skillset + llm_spec | `agent_packages` (the blueprint) + the agent's OWNED copies |
| **llm_spec** | The capability CONTRACT the LLM must satisfy | `agents.llm_spec` (owned) + the package's spec |

**THE OWNERSHIP RULE (the user's correction)**: the agent OWNS its
toolkit, skillset, and llm_spec. The package is the BLUEPRINT —
`agents.package_id` records provenance (lineage), nothing more. The
package never owns the agent; later package edits (even a delete)
don't mutate provisioned agents.

## The shape (back to front)

```
agent_packages (the blueprint)
  id, name, description
  kit_id        -> a tool-typed collection (the toolkit ref)
  skills        -> the skillset (JSON)
  llm_spec      -> {kind, thinking, location, min_context}

agents (the instance — OWNS everything)
  kit_id, skills, llm_spec   <- the OWNED copies (taken at adopt)
  package_id                 <- provenance (nullable)

curated_models (the registry — the matcher's axes)
  thinking: none|low|medium|high
  location: local|cloud
```

## The rules (hard-won)

1. **The toolkit policy**: an agent owning a kit gets ONLY the
   kit's granted tools — the GRAS default is SUPPRESSED. An EMPTY
   kit = ZERO tools (the shallow-bot fix: nothing to hallucinate).
2. **Ownership**: adopt COPIES the package's fields into the
   agent's OWN columns — never a live read. The package delete
   does NOT strip the agent (tested).
3. **Substitution is a PROPOSAL, never automatic**: the matcher
   (`POST /curated-models/match`) returns candidates (free-first)
   for an llm_spec; an HONEST EMPTY when nothing matches. The user
   (or Exa, asking) confirms.
4. **The provision flow**: read the package → the wizard answers
   what the package doesn't (location) → create the agent with
   the owned copies + the provenance + a matched model → REPORT
   the outcome (never silent).
5. **The llm_spec vocabulary is ENFORCED** (pydantic Literals):
   kind (chat/workflow), thinking (none/low/medium/high),
   location (local/cloud/any), min_context — bad values → 422.

## The API surface

- `POST/GET/PUT/DELETE /api/v1/agent-packages` — the blueprint CRUD
- `POST /api/v1/agent-packages/{id}/provision` — create an agent
  from a package (the consumer path)
- `POST /api/v1/agents/{id}/adopt-package` — copy a package into
  an agent's OWN fields
- `POST /api/v1/curated-models/match` — the substitution matcher

## The seed

- `shallow-agent` — the policy the user described: a new shallow
  agent gets a shallow package. Its kit ("Shallow Agent Kit") is
  an EMPTY tool-typed collection → per the toolkit policy, an
  owner gets ZERO tools. The seed is idempotent (startup-safe).

## The live verification (2026-08-24)

- Bob (agent 19) adopted the shallow-agent package → his chat
  surface dropped to `Sending LLM request with 0 tools: []`.
- Wanda (agent 54) provisioned from the package in one call:
  matcher-picked local model + kit/skills/spec copied.

## The test traps (recorded)

- The ASGITransport API tests MUST use the conftest `client`
  fixture (its dependency_overrides route the DB to the test
  engine) — a local client fixture silently hits the real DB.
- The matcher tests need SEEDED curated models — an empty registry
  answers 0, which is a FALSE honest-empty.
- The kit models (collections etc.) use client-assigned string
  UUID ids — tests must set them.
