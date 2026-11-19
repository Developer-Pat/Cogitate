---
name: cogitate-agent-management
description: "The agent lifecycle playbook — create, verify, reassign, remove, restore. Read when the user asks to add/remove an agent, assign or change an agent's model/provider, or cycle agents through the pool. Names are unique; agents are characters; the llama row wants the full gguf path; team-join is required for chat visibility; verify by chat-testing on the assigned model."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, agents, lifecycle, configuration]
---

# Agent Management (the lifecycle playbook)

The agent pool's lifecycle procedures. Derived from the 2026-09-09
exercise (create → verify → reassign → remove → restore, all
verified live).

## The naming + character conventions

- **Names are unique.** The pool addresses agents by name — the API
  rejects a duplicate create. Choose a distinct name.
- **Agents are characters**: a name + a face (profile image) + a
  STORED persona (the system prompt writes persona.md in the
  agent's workspace folder). Follow the Bob pattern: a clear
  role/character, not a bare label.
- The shared rules stay SHARED — no name-gated logic in rules.

## Create

- POST /agents requires {name, provider, model} (+ optional
  description, system_prompt, image).
- **Model strings are provider-specific**: the llama (local)
  provider uses the FULL gguf path (e.g.
  <llama-model-dir>/<model>.gguf — no short alias);
  ollama uses short names (e.g. codellama:latest); the cloud
  providers use their catalog ids.
- Defaults arrive sane (temperature 0.7, max_tokens 2000, top_p
  0.9, delegation on) — no need to set them unless the role needs
  different values.
- The create form's model prefill is provider-sticky (a known gap):
  after switching the provider, REWRITE the model field — the old
  provider's model string does not clear.

## Verify (claimed → verified)

- ALWAYS chat-test the new agent on its assigned model before
  declaring it working: POST /api/v1/chat/stream {agent_id,
  message, stream: false} and confirm a real reply.
- The local llama daemon decodes slowly (~1 t/s class): use
  minimal probe prompts ("Reply with exactly: <agent> online").
- The chat surface is TEAM-SCOPED: a teamless agent exists but is
  not selectable in the agent-interaction page. To chat via the
  UI, the agent must join a team first (or verify via the API).

## Reassign

- PUT /agents/{id} {provider, model} changes the assignment.
- The API currently validates NOTHING about the model string — a
  nonexistent model or a keyless provider is accepted silently and
  fails at chat time. Verify the model exists (browse the
  provider's models) and the provider is configured BEFORE
  assigning.

## Remove + restore

- DELETE /agents/{id} = soft-delete + archive: the row keeps
  deleted_at + archived_path (agents/.archived/<name>-<ts>); the
  response lists the bill of materials (linked sessions, grants,
  collections). Archived agents stay visible under "Archived
  profiles".
- POST /agents/{id}/restore = clean recovery (row back to active,
  deleted_at cleared).
- Removing an agent is part of the normal cycle — create, use,
  remove, recreate as needed.

## Pitfalls

- The stale-reference class: an agent assigned a model its provider
  no longer serves (or a keyless provider) looks fine on the card
  and fails at runtime. Always verify the provider is live + the
  model exists.
- Trusting the create response without a chat test.
- Forgetting the team-join and declaring the agent unusable.
- Using the previous provider's model string after a provider
  switch.
