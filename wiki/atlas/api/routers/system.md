---
title: System
type: atlas-api
path: wiki/atlas/api/routers/system.md
category: api-atlas
order: 10
confidence: high
updated: 2026-09-17
tags: [type/api, domain/system, status/active]
---

# System — API

## Purpose

System info, metrics, status + diagnostics (run/resolve).

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
| `GET` | `/api/v1/system/diagnostics` | List Diagnostics |
| `GET` | `/api/v1/system/diagnostics/metrics` | Get Diagnostics Metrics |
| `DELETE` | `/api/v1/system/diagnostics/resolved` | Delete Resolved Diagnostics |
| `POST` | `/api/v1/system/diagnostics/run` | Run All Diagnostics |
| `DELETE` | `/api/v1/system/diagnostics/{diagnostic_id}` | Delete Diagnostic |
| `POST` | `/api/v1/system/diagnostics/{diagnostic_id}/resolve` | Resolve Diagnostic |
| `POST` | `/api/v1/system/diagnostics/{diagnostic_id}/run` | Run Single Diagnostic |
| `GET` | `/api/v1/system/info` | Get System Info |
| `GET` | `/api/v1/system/metrics` | Get System Metrics |
| `GET` | `/api/v1/system/mode` | **Which frontend build is being served** — and what else it could serve. Read from the launcher's record, never guessed; `mode` is `null` when the app was not started by the launcher (which claims nothing rather than assuming development) |
| `POST` | `/api/v1/system/mode` | **Switch the frontend between the two builds.** The app REQUESTS; the launcher ACTS (`cogitate.sh mode <mode>`, detached — a switch to production builds first and can take over a minute) |
| `GET` | `/api/v1/system/audit/consistency` | The consistency audit (read-only — dangling references) |
| `POST` | `/api/v1/system/audit/scrub-orphans` | The guarded orphan scrub (dry-run default + typed confirm + backup + re-audit) |
| `GET` | `/api/v1/system/status` | Get System Status |


### The frontend mode

`development` and `production` are the frontend's two builds, served on the **same
port**. The app's state is origin-scoped — the auth token, the persisted stores and
the cross-tab channel all live on the origin — so a second port would sign the user
out and sever tab coordination. The switch therefore cycles one server in place.

**The mode has ONE writer.** The launcher persists it in `.pids/frontend.mode`, and
`GET /mode` only reads that file, so the record cannot disagree with what is
running. It is written **before** the new server binds — which is why the response
carries a `note` saying so: the endpoint cannot tell a client that the server is
back, and a client waiting on a switch must probe the frontend itself.

**`POST` semantics:**

- `confirm` must be `true`, otherwise **400** — `confirm must be true.` This is a
  plain confirm, **not** the typed-name gate reserved for irreversible deletes: a
  mode switch is recoverable and reversible.
- The short forms the launcher accepts work here too — **`dev`** and **`prod`** are
  normalised. Anything else is **400**: `Unknown mode '…'. Expected one of:
  development, production.`
- **503** when the launcher cannot be found, **500** when invoking it fails. Both
  say **nothing has changed**.
- **The connection does NOT drop**, unlike `shutdown` / `restart`. Only the
  frontend cycles; the backend stays up to answer, and the response is a plain
  `{"accepted": true, "action": "mode", …}`.
- The launcher is invoked **detached** — a switch to production builds first, which
  can run past a minute, so the request never waits on it.

## Status

**ACTIVE** — core facility, in use.

## Related

- [[atlas/ui/pages/RagIndex|RAG Index page]]
- [[atlas/api/routers/debug|Debug]]
