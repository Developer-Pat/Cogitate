---
title: Skills Management
category: skills
subtopic: Overview
order: 1
confidence: high
created: 2026-08-14
updated: 2026-11-18
tags: [type/help, domain/skills]
---

# Skills Management

The **Skills** page (Assets → Skills) shows every skill in the app
and which agents use them.

## What you see

- **Skill** — the skill's name and what it does.
- **Category** — `curated` skills ship with the app (the built-in
  Cogitate skills); `agent` skills live with a specific agent
  (e.g. system-manager's administration skills).
- **Tags** — the skill's topic tags.
- **Status** — `valid` means the skill file passes validation;
  `invalid` means its frontmatter or structure has a problem.
- **Used By** — which agents have this skill (agent-local skills
  show their owner; curated skills show `unused` until an agent
  is given them).
- **Preview** — expand any skill to read its full SKILL.md body
  (what the skill actually instructs an agent to do).

## Seeding — how agents get skills

When an agent is created (or cloned from a template), the skills named
on its profile are **copied** from the shared curated library into the
agent's own `skills/` folder. It is a copy, not a link: the agent can
grow or edit its skill without touching the library. A skill this
install does not ship is logged and skipped — never fatal.

One of the curated skills is **`beat-sheets`**: it teaches a news agent
to read and edit the beat sheets in its workspace (its named sweeps).
See [[help/cloning-an-agent|Cloning an Agent]] for what a clone
inherits.

## Filtering

- **Search** — by name, description, or tag.
- **Curated / Agent-local** — the dropdown filters to skills that
  ship with the app vs skills that live with an agent.

## Why it matters

Curated skills are the built-in knowledge Exa (and other agents)
draw on when you hand them a job — the Skills page is the map of
what they know how to do. If a skill shows `invalid`, that skill
won't load properly for agents.
