---
title: Skills
type: atlas-api
path: wiki/atlas/api/routers/skills.md
category: api-atlas
order: 19
confidence: high
updated: 2026-08-14
tags: [type/api, domain/skills, status/active]
---

# Skills — API

> Router: `backend/app/api/v1/skills_router.py`.
> Status: **ACTIVE** — the asset-management model applied to the
> skill library (2026-08-14).

## Purpose

Read-only management of skill assets: **browse** (the SkillLoader's
scan/parse/validate output with a curated flag), **search/filter**,
and the **in-use view** (which agents reference which skills).
Write ops (import/export/delete) are deliberately NOT in v1 —
skills are DIRECTORIES with SKILL.md inside (different zip
semantics than images); they arrive organically.

- **Curated** = ships with the repo (`./skills/<category>/<name>/SKILL.md`, loader-validated).
- **Agent-local** = lives in an agent dir (`agents/<name>/skills/*.skill.md` — the system-manager model).
- **In-use sources**: `file` (agent-dir skill file) + `derived` (skill name appears in the agent's system_prompt). Both shown, labeled — no mapping table invented.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/skills` | List skills — `curated` (all\|true\|false) + `q` (name/description/tags substring). Items: name, description, category, tags, version, author, related_skills, curated, valid, errors, warnings, path |
| `GET` | `/skills/in-use` | Skill → agents assignments with source labels (`file`/`derived`) |

## Auth

All endpoints require an authenticated session.

## Related

- [[atlas/api/routers/external-agent|External Agent]] — the consult skill-injection endpoint (`GET /external-agent/skills/{name}`)
- [[dev-notes/agents/consulting-agent|Consulting Agent (dev-notes)]] — the skill set
- [[atlas/api/routers/images|Images]] — the model this was patterned on
