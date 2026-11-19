---
name: verify-backend-health
description: "Check the Cogitate backend's health — the VERIFIED state, not a guess. Use when asked if the backend is up, or after any restart/change."
version: 1.0.0
author: Cogitate Team
tags: [cogitate, health, verify, backend]
---

# Verify Backend Health

Report the backend's ACTUAL state, never an assumption.

## The check

`GET http://localhost:8000/api/v1/health` — expect
`{"status": "healthy"}`. The comprehensive check is
`/api/v1/health/comprehensive` (includes the path-resolution
audit).

The tool `verify-backend-health` does this for you; call it
before claiming the backend is up or down.

## Interpretation

- HTTP 200 + `healthy` → the backend is UP (verified).
- Connection refused/timeout → the backend is DOWN (verified —
  report the error, don't guess why).
- After a restart: verify BEFORE reporting success. A restart
  that leaves the port hung is NOT a success (the 2026-08-18
  lesson: 'restarted' was claimed, the system was broken).

## Common pitfalls

- Reporting "the backend is up" from the process list — the
  process can exist while the port hangs. The health CHECK is
  the truth.
- Trusting a restart without a health read-back.
