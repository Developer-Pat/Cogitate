---
title: Cognitive Profiles
confidence: high
created: 2026-07-27
tags: []
---

# Cognitive Profiles

## Overview

Cognitive profiles define how an agent processes messages — context building, execution strategy, memory, and output format.

## Part Code System

Each profile has a part code: `{context}-{executor}-{format}-{memory}`

| Code | Context | Executor | Format | Memory |
|------|---------|----------|--------|--------|
| d | default | default | default | in-memory |
| m | minimal | fast | direct_yield | none |
| a | augmented | hybrid | structured | — |
| s | skill_aware | structured | — | kv_store (sqlite) |

## Profile Catalogue

| Name | Code | Context | Executor | Memory | Persistence |
|------|------|---------|----------|--------|-------------|
| conversational | d-d-d-d | default | default | in-memory | memory |
| quick-response | m-f-y-n | minimal | fast | none | none |
| research-std | a-h-s-d | augmented | hybrid | in-memory | memory |
| balanced-chat | d-h-d-d | default | hybrid | in-memory | memory |
| code-gen | m-h-d-n | minimal | hybrid | none | none |
| research-pro | s-h-d-k | skill_aware | hybrid | kv_store | sqlite |
| system-admin | s-h-d-k | skill_aware | hybrid | kv_store | sqlite |

## Naming Convention

Profiles describe **capabilities**, not agent roles.
- `research-pro` not `deep-researcher`
- `system-admin` not `system-manager`
- `balanced-chat` not `balanced-assistant`

## Related

- [[agent-orchestration]]
