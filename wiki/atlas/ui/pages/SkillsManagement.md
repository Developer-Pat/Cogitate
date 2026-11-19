---
title: SkillsManagement
type: atlas-page
path: frontend/src/pages/SkillsManagement.tsx
confidence: high
updated: 2026-10-07
tags: [type/page, domain/atlas-ui]
---

# SkillsManagement

**Component**: `frontend/src/pages/SkillsManagement.tsx`
**Route**: `/skills` (protected, `requiresAuth: true`, icon `sparkles`, breadcrumb `Skills Management`)
— registered in `frontend/src/config/routes.ts`; the sidebar's **Assets** section in `App.tsx` (nav
label "Skills").

## Purpose

The image-management model applied to the skill library: browse (name, description, category, tags,
validity), the curated flag, the in-use view (which agents hold which skill), and a body preview.

**Read-only.** Upload, import, export and delete are deliberately absent — a skill is a directory with
a `SKILL.md` inside, whose zip semantics differ from an image's, so the writes arrive on their own
terms rather than by analogy.

**Two kinds of skill, one list:** curated ones ship with the app (`skills/`), agent-local ones live
with an agent. Both are visible and both preview.

## The table

| column | what it shows |
|---|---|
| **Skill** | the name, and the description clamped to two lines |
| **Category** | the `curated` badge (tooltip: ships with the app) or a ghost `agent` badge, above the category text |
| **Tags** | the first four, then a `+N` overflow chip |
| **Status** | `valid`, or `invalid` with its validation errors in the badge's tooltip |
| **Used By** | the agents holding it, or `unused` |
| **Actions** | **Preview** / **Hide** |

Filters: a free-text search over name, description, tags and category, and a curated select
(`All` / `Curated (ships with app)` / `Agent-local`). The `{total} total` beside them is the
**server's** count — it does not move with the filters, so a filtered view cannot be mistaken for the
library's size.

## Two loads, one render

`skillAssetService.listSkills()` → `GET /api/v1/skills` and `listSkills.listInUse()` → `GET
/api/v1/skills/in-use`, in parallel. The list response carries the **`SKILL.md` body for every
skill** — curated via the loader, agent-local read from the file — so the preview needs no second
fetch and agent-local skills preview like any other. The body is truncated at 2000 characters with a
marker.

The used-by map is built from the in-use assignments (`skill → agents`, entries with no agents
dropped), and the lookup tries the name **with and without a `.skill` suffix**, because the asset list
and the in-use view do not spell it the same way.

## Empty states are different, on purpose

- `No skills found.` — the library itself is empty (no skills at all);
- `No skills match the search.` — skills exist and the filter excluded them.

## State management

Local `useState` for the list, the total, the assignments, the search, the curated filter and the
single `expanded` row (one preview at a time). The whole page sits inside an `ErrorBoundary`, and
load failures raise a toast (`Skills` / `Failed to load skills`).

## Related pages

- [[atlas/ui/pages/ImageManagement|ImageManagement]] — the model this page applies to skills
- [[atlas/ui/pages/AgentProfiles|AgentProfiles]] — the agents the in-use view names
- [[atlas/ui/pages/ToolManagement|ToolManagement]] — the sibling asset surface
- [[atlas/api/routers/skills|Skills API]]
