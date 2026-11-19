---
title: Memory Profiles
type: atlas-api
path: wiki/atlas/api/routers/memory-profiles.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/memory-profiles, status/active]
---

# Memory Profiles — API

## Purpose

Per-agent memory settings profiles.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/memory-profiles` | List Profiles |
| `POST` | `/api/v1/memory-profiles` | Create Profile |
| `DELETE` | `/api/v1/memory-profiles/{profile_id}` | Delete Profile |
| `GET` | `/api/v1/memory-profiles/{profile_id}` | Get Profile |
| `PUT` | `/api/v1/memory-profiles/{profile_id}` | Update Profile |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/cognitive|Cognitive]]
