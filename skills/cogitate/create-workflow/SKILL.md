---
name: cogitate-create-workflow
description: "Create, review, and maintain workflows in Cogitate — the automated multi-step jobs (monitor → analyze → report, LLM chains, agent delegation). A workflow is a template (kind) instantiated with concrete parameters. Use when the user asks to build a new workflow, fix a workflow, or turn a repeated task into an automation."
version: 1.0.0
author: Cogitate Team
license: MIT
metadata:
  cogitate:
    tags: [workflows, templates, automation, creation, cogitate]
    related_skills: [cogitate-orientation, cogitate-create-agent]
---

# Cogitate Workflow Creation

The user works with the **Workflows** page (/workflow-templates —
configured instances; each is a template/kind with concrete
parameters) and **Templates** (/workflow-kinds — the canonical
process shapes) and **Automation** (/automation — triggers + run
history). You help them create and maintain workflows — automated
multi-step jobs that execute LLM steps, tool calls, and agent
delegation. Produce COMPLETE workflows with real steps, not empty
shells.

## The data model

- **Workflow** (the configured instance) — `name`, `description`, `category`
  (e.g. "monitoring", "office-work", "testing"), `version`
  (default "1.0.0"), `author` (default "user"), `tags` (string
  list), `workflow_type` ("simple" | "advanced"), `config`
  (free-form JSON holding the steps/params — planner+executor
  nodes, chain_steps, approval_required, test_mode, delay_seconds,
  etc.), `inputs` (declared execution inputs:
  `[{name, required}]`), `is_public`, `is_customizable`.
- **What lives in config** (from the seeded templates): simple
  workflows carry `{"test_mode": true}` or
  `{"chain_steps": [{prompt, ...}, ...]}`; advanced ones carry
  `{"approval_required": true}`. The LangGraph execution reads
  the config to build planner/executor/router nodes.
- **Workflows are CREATED, not just seeded**: the 33 seeds are
  examples — the write path (POST/PUT/DELETE + validate) has been
  live since 2026-08-14.

## The API (base: /api/v1/workflows)

| Purpose | Route |
|---|---|
| List templates | `GET /api/v1/workflows/templates?category=&tags=&limit=&offset=` |
| Get one template | `GET /api/v1/workflows/templates/{id}` |
| Create template | `POST /api/v1/workflows/templates` — `{name, description?, category?, version?, author?, tags?, workflow_type?, config?, is_public?, is_customizable?, inputs?}` |
| Update template | `PUT /api/v1/workflows/templates/{id}` — partial body |
| Delete template | `DELETE /api/v1/workflows/templates/{id}` |
| Validate before save | `POST /api/v1/workflows/templates/validate` — `{name, description?, steps?, config?}` → `{isValid, errors, warnings}` |
| Validate execution inputs | `POST /api/v1/workflows/templates/{id}/validate-execution` — body WRAPPED: `{inputs: {...}}` |
| Execute | `POST /api/v1/workflows/execute` — `{template_id, inputs}` |
| Execution status/history | `GET /api/v1/workflows/{workflow_id}/status` · `/{workflow_id}/history` |
| List executions | `GET /api/v1/workflows/executions?template_id=&trigger_id=&limit=` |
| Trigger list | `GET /api/v1/workflows/triggers` (schedules/webhooks) |
| Create trigger | `POST /api/v1/workflows/triggers` |

## How to create a good workflow

1. **Discover first**: `GET /api/v1/workflows/templates` + the
   seeded categories (monitoring, office-work, testing,
   multi-agent-testing...) — reuse a category; NEVER duplicate an
   existing template. Ask what the workflow should DO if vague.
2. **Name it for the job**: "Daily Briefing", "Context Indexer —
   Build Searchable File Index" — not "workflow 1".
3. **Write a real description**: what it does, end-to-end, in
   user language ("Monitors the RSS feed, summarizes new posts,
   and saves a report to Products").
4. **Put the work in config**: a workflow with `{}` config does
   NOTHING (the validator warns). For a simple chain, set
   `config.chain_steps` (each with a `prompt` — real instructions,
   referencing `{previous_result}` for chaining). For approval
   gates, `config.approval_required: true`. For test mode,
   `config.test_mode: true`. Declare `inputs` with `required`
   flags so execution validation works.
5. **Validate before saving**: `POST /templates/validate` — it
   catches missing names and empty shells. Then `POST
   /templates/{id}/validate-execution` with the wrapped body to
   confirm required inputs.
6. **Show your work**: after creating, show the template summary
   (name, category, workflow_type, config keys, declared inputs)
   so the user can verify before executing.

## Verification

- After creating, re-`GET` the template and confirm it round-trips
  (name, config, inputs present).
- If the user says a workflow "doesn't work", check the execution
  record (`GET /executions` — it distinguishes direct vs triggered
  runs via `input_data.trigger_id`), read the config, and check
  the inputs/trigger wiring before proposing edits.
- Executing a workflow requires an active agent with the right
  provider — confirm the referenced agent is healthy first.

## Boundary

Creating/updating/deleting templates and triggers (write
operations) requires fix-mode. In read-only mode, produce the
workflow as a proposal (name, description, config sketch, inputs)
and let the user apply it.
