---
name: cogitate-create-agent
description: "Create, review, and configure agents in Cogitate — providers, models, system prompts, tools, and execution modes. Use when the user asks to build a new agent, fix an agent's configuration, or set up an agent for a job."
version: 1.0.0
author: Cogitate Team
license: MIT
metadata:
  cogitate:
    tags: [agents, creation, configuration, providers, cogitate]
    related_skills: [cogitate-orientation, cogitate-create-workflow]
---

# Cogitate Agent Creation

The user works with the **Profiles** page (/agents). You help them
create and configure agents — the agent is the unit of LLM work in
Cogitate (chat, workflow steps, delegation). Produce COMPLETE,
correct agents (provider + model + a real system prompt), not
stubs.

## The data model

- **Agent** — `name`, `description`, `provider` (must be one of the
  configured providers), `model` (a model that provider serves),
  `system_prompt` (what the agent is FOR — end-user language, not
  jargon), `parameters` (temperature/max_tokens/top_p),
  `fallback_enabled` (opt-in, default False so failures surface),
  `execution_mode` ("llm" standard | "simulated" programmatic |
  "hybrid"), `is_active`.
- **ARM-ready descriptions (Phase E)**: write `description` +
  `system_prompt` so an orchestrator can select this agent later —
  name the ROLE (writer, researcher, coder) and DOMAIN (fiction,
  math, finance) plainly. The description is read by the user AND
  by the resource manager (Exa composing workflows); say what the
  agent is FOR in one clear sentence.
- **Tools** — a separate association: an agent only sees the tools
  ENABLED for it. `POST /api/v1/tools/agents/{agent_id}/tools`
  with `{tool_id, priority, config}`.
- **Providers** — `GET /api/v1/providers` lists the configured
  ones (Ollama, OpenAI, Anthropic, OpenRouter, Deepseek...). The
  provider's `base_url` matters for local (Ollama = localhost:11434)
  vs cloud. Check which providers have KEYS configured before
  recommending one (`GET /api/v1/managed` or the Setup page state).

## The API (base: /api/v1)

| Purpose | Route |
|---|---|
| List agents | `GET /api/v1/agents` |
| Get one agent | `GET /api/v1/agents/{agent_id}` |
| Create agent | `POST /api/v1/agents` — `{name, description?, provider, model, system_prompt?, is_active?, parameters?, fallback_enabled?, execution_mode?}` |
| Update agent | `PUT /api/v1/agents/{agent_id}` — partial body |
| Delete agent | `DELETE /api/v1/agents/{agent_id}` |
| List providers | `GET /api/v1/providers` |
| List tools | `GET /api/v1/tools` |
| List agent's tools | `GET /api/v1/tools/agents/{agent_id}/tools` |
| Enable tool for agent | `POST /api/v1/tools/agents/{agent_id}/tools` — `{tool_id, priority?, config?}` |
| List templates | `GET /api/v1/agents/templates` |
| Apply template | `POST /api/v1/agents/templates/{template_id}/apply` |
| Duplicate agent | `POST /api/v1/agents/{agent_id}/duplicate` |

## How to create a good agent

1. **Discover first**: `GET /api/v1/agents` (what exists — never
   duplicate) + `GET /api/v1/providers` (what's configured) +
   `GET /api/v1/tools` (what's available). Ask the user what the
   agent should DO if the request is vague.
2. **Provider + model must be real**: only use a provider that is
   configured, and a model that provider actually serves. For a
   local setup, Ollama (localhost:11434) is the zero-key option —
   check `GET /api/v1/providers` for its base_url. Cloud providers
   need keys; check the Setup page state before recommending one.
   When in doubt, mirror an existing working agent's provider/model
   choice (the Agents list shows each agent's provider).
3. **Write a real system prompt**: say what the agent IS and DOES in
   end-user language. Example: "You are a research assistant that
   reads documents, summarizes findings, and cites sources." Not
   "LLM agent for general use" — that's a stub.
4. **Enable the tools it needs**: after creating, list tools
   (`GET /api/v1/tools`) and enable the relevant ones (e.g. a file
   worker needs terminal/file tools). Show the user the resulting
   agent + tool set.
5. **Sensible defaults**: `parameters` default `{temperature: 0.7,
   max_tokens: 2000, top_p: 0.9}`; `fallback_enabled` False unless
   the user opts in (a broken provider must surface, not silently
   fall back); `execution_mode` "llm" unless the user asks for
   simulated/hybrid.
6. **Show your work**: after creating, show the agent summary
   (name, provider, model, enabled tools) so the user can verify.

## Verification

- After creating, re-`GET` the agent and confirm it round-trips
  (name, provider, model, system_prompt present).
- After enabling tools, `GET /api/v1/tools/agents/{agent_id}/tools`
  and confirm the tools are listed.
- If the user says an agent "doesn't work", check its provider is
  configured + has a key, the model name is valid for that
  provider, and its tools are enabled BEFORE proposing edits.

## Boundary

Creating/updating/deleting agents and enabling tools (write
operations) requires fix-mode. In read-only mode, produce the agent
as a proposal (name, provider, model, prompt, tools) and let the
user apply it.

- Use ROLE + DOMAIN **tags** (the curated vocabulary: writer,
  researcher, coder / fiction, math, software...) so the agent is
  selectable by the resource manager. Agents can also be grouped
  into **collectives** (collections) — user-facing organization.
