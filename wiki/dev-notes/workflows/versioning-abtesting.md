---
title: Workflow & Agent Versioning / A-B Testing
type: atlas-devnote
category: workflows
order: 5
confidence: medium
updated: 2026-08-05
tags: [type/dev-notes, domain/workflows]
---

# Workflow & Agent Versioning / A-B Testing

## Overview

- **agent_versioning/** (backend/app/workflows/agent_versioning/):
  registry.py + ab_testing.py + api/router.py — versioned agent
  definitions with A/B test routing between versions.
- **workflow templates**: templates/default_provider_tests.py +
  template_router.py — workflow template management.
- **ab_test_configs / ab_test_results** tables exist in the DB
  (schema-level support for experiment tracking).

## Version selection

`workflow_versions` table: versioned configs per template_id
(version, config JSON, changelog, is_active). The workflows API
exposes version CRUD + compare + activate/deactivate
(`/workflows/{template_id}/versions/*`). Active version = the one
marked `is_active`.

## A/B split

`ab_test_configs` (template_id, name, versions list, traffic_split
JSON — per-version weight %, metrics list, is_active). Flow:
start → assign (pick version per traffic split) → record result →
results/compare. **Status: dormant by decision** — the mechanism is built and un-expanded: the version table holds three
example rows and the results table roughly twenty-three thousand **synthetic** ones (`test-template`,
`exec-v2-8`), kept as test material rather than deleted. See
[[atlas/api/routers/ab-tests|A/B Tests API]].

## Template format

`workflow_templates` (id, name, category, version, author, tags,
workflow_type, config JSON, is_public, is_customizable, inputs).
