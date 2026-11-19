---
title: Agent Provisioning Guidelines
type: dev-note
path: wiki/dev-notes/agents/agent-provisioning-guidelines.md
created: 2026-08-25
status: draft
tags: [type/dev-note, domain/agent-provisioning]
---

# Agent Provisioning Guidelines

> THE HOW-TO (2026-08-25): how to pick the right driver for an
> agent. Not a what's-what of models — a decision procedure. This
> note is the source for the future agent-provisioning skill (the
> study: local/agent-provisioning/01-study.md).

## The core idea

Right-sizing, not max-sizing. The "most massive LLM for every
task" is waste (the cost + the latency + the flakiness). Every
agent level has an appropriate driver band; the bands anchor on
the ECI (the Epoch Capabilities Index — the emerging standard);
the star catalog gives the pickable models per band.

## The decision flow (the how-to)

1. **Classify the agent's level** (below) — what kind of task is
   this really?
2. **Read the band for that level** — the driver requirement.
3. **Pick a model from the star catalog** at that band (or higher
   — the bands are "at least").
4. **Record the choice** on the agent's card (the llm_spec) —
   the matcher can then warn when a driver drops below the task's
   band.

## The agent levels (the task side)

| The level | What it is | The exemplars | The band |
|---|---|---|---|
| **Pseudo** | A single LLM call in a wrapper (no real tooling) | the wrapper agents (TBD) | 1 |
| **Shallow** | One purpose, light tooling, test-oriented | tag-layer-sweeper, Ox Alpha Tester | 1-2 |
| **Mixed** | The tool-loop with a personality (the chat surface) | Bob (the chatbot) | 2-3 |
| **Deep** | The research/planning class (multi-step, long horizons) | the research agents (TBD) | 3-4 |
| **Exa** | The external agent (the ACP brain — hermes/openclaw) | the Exa agent | 4 |

THE EXEMPLARS: the draft's the proposal — the user's call on
which real agents are the exemplary per level.

## The bands (the ECI spine)

The bands are COARSE ECI ranges — the fine-grained scores never
enter the UI; the bands + the catalogs do.

| The band | The ECI range | The character |
|---|---|---|
| 1 | < 50 | the token-level workhorses (the classification, the extraction) |
| 2 | 50 - 90 | the batch-slow (the summarize, the transform) |
| 3 | 90 - 130 | the tool-loop (the research, the consult) |
| 4 | 130+ | the deep reasoning (the planning, the design) |

THE ECI's the ruler; the bands' refresh is a sweep task (the
anchors drift).

## The star catalog (the model side — the pickable)

THE SURVEY (2026-08-25, OpenRouter — the convenient source; the
Hugging Face cards confirm the specs). The bands are "at least" —
anything higher in the band also qualifies.

| The band | The choice models (the OpenRouter ids + the local names) |
|---|---|
| 1 | meta-llama/llama-3.2-3b-instruct · the local llama3.2 · granite4:3b · qwen3:latest |
| 2 | mistralai/ministral-8b-2512 · meta-llama/llama-3.1-8b-instruct · microsoft/phi-4 · the local ministral-3:8b |
| 3 | openai/gpt-oss-20b (the tested!) · openai/gpt-oss-120b · qwen/qwen3-30b-a3b-thinking-2507 |
| 4 | anthropic/claude-opus-5 · openai/gpt-5.6-sol · google/gemini-3.7-flash · deepseek/deepseek-v3.2 · openai/gpt-5.5-pro |

## The rules (the hard-won)

- The bands are "at least" — a band-3 task can run on a band-4
  driver; the reverse needs the justification.
- The local models' bands come from OUR probe battery (the ECI has
  no scores for the obscure locals) — the probes place them on
  the same scale.
- The pseudo/shallow agents are the RIGHT-SIZING wins — the
  massive brain is waste there, and the scale makes the smaller
  choice rational.

## The future

This note feeds the agent-provisioning skill (the study's outline:
the intake -> the decompose -> the proposal). The skill will teach
Exa to walk the flow above when it creates agents.

---

## Footnote

The bands anchor on the Epoch Capabilities Index (ECI — the
two-anchor scale: Claude 3.5 Sonnet = 130, GPT-5 = 150, the IRT
framework). The star catalog was surveyed from OpenRouter
(2026-08-25); the local models' specs from the Ollama library;
the Hugging Face model cards confirm the published details. The
local models' band placement comes from our probe battery (the
ECI has no scores for the obscure locals).
