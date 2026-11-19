---
title: Cognitive Profiles
type: atlas-api
path: wiki/atlas/api/routers/cognitive-profiles.md
category: api-atlas
order: 10
confidence: medium
updated: 2026-08-07
tags: [type/api, domain/cognitive-profiles, status/active]
---

# Cognitive Profiles — API

## Purpose

Pipeline behavior profiles (memory depth, summarization, retrieval).

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/cognitive-profiles` | List Profiles |
| `POST` | `/api/v1/cognitive-profiles` | Create Profile |
| `DELETE` | `/api/v1/cognitive-profiles/{profile_id}` | Delete Profile |
| `GET` | `/api/v1/cognitive-profiles/{profile_id}` | Get Profile |
| `PUT` | `/api/v1/cognitive-profiles/{profile_id}` | Update Profile |


## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/api/routers/cognitive|Cognitive]]
