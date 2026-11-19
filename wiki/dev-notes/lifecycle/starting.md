---
title: Starting the App
type: atlas-devnote
category: lifecycle
order: 2
confidence: high
updated: 2026-09-17
tags: [type/dev-notes, domain/lifecycle]
---

# Starting the App — the launcher, the ports, and the two builds

**`./cogitate.sh start`** starts both halves. `stop`, `restart`, `status`, `logs` and
`mode` alongside it. This page covers **what it binds, which build it serves, and how to
change both**; the boot sequence itself is [[dev-notes/lifecycle/startup|Startup]].

## The default ports

| Half | Port | URL |
|---|---|---|
| Backend (uvicorn) | **8000** | http://localhost:8000 |
| Frontend (vite dev server) | **5173** | http://localhost:5173 |

Both are also **the defaults baked into the code**, so a bare `npx vite` or a
direct `uvicorn` outside the launcher lands on the same numbers.

## Running on different ports

```bash
COGITATE_BACKEND_PORT=8100 COGITATE_FRONTEND_PORT=5273 ./cogitate.sh start
```

That is the whole interface. The launcher **exports both**, and everything
downstream derives from them:

```
cogitate.sh                     the ONE place the ports are decided
  ├── uvicorn --port $BACKEND_PORT          the bind
  ├── health checks + the stop path         derived from the same vars
  └── exported to the child processes
        ├── vite.config.ts reads them  -> server.port + the /api proxy target
        ├── backend reads them         -> CORS allows the configured origin
        └── the supervisor reads COGITATE_FRONTEND_MODE -> which build it serves
```

**Nothing else may hardcode a port.** If you find a literal `8000` or `5173`
outside the two defaults, it is a bug of the kind this page exists to prevent.

## Why it is wired this way

**The frontend never learns the backend's port, by design.** `apiClient` uses
`window.location.origin`, and vite **proxies** `/api` and `/static` to the
backend. So the browser always talks to whatever origin served it, and the dev
server forwards. Change the ports and the browser needs no change at all.

**The two failure modes were silent, which is why both are derived rather than
typed:**

- **A stale proxy target** — vite proxying to `:8000` while the backend listens on
  `:8100` produces connection errors that read like a backend crash.
- **A CORS rejection** — a browser on `:5273` refused by a backend that only
  allows `:5173` looks like a network fault, not a policy.

`Settings._with_configured_frontend_port` **adds** the configured origin to the
CORS list; it never replaces the defaults, so a browser on the house port keeps
working while another port is in play. (The list already carried `5174` — a second
port was anticipated before this was wired.)

## The two frontend modes

The frontend half has **two builds — `development` and `production`** — chosen by the
launcher:

```bash
./cogitate.sh mode production    # build first, then swap the server
./cogitate.sh mode development   # swap back; no build
./cogitate.sh mode               # report the mode and change nothing
```

**Development is for working on the frontend** — unbundled, unminified, with hot reload.
**Production is for using the app the way a user would** — the built bundle. The two are
behaviourally identical; the difference is cost. On the same prompt, blocked main-thread
time is **3480 ms in development against 233 ms in production**, and long tasks fall from
**41 to 2**, on a *longer* answer doing *more* updates. The gap is dev-only overhead:
`jsxDEV`, StrictMode's double render, and an unbundled module graph.

**The switch keeps the SAME port, deliberately.** The auth token, the persisted stores and
the cross-tab channel are all origin-scoped, so a second port would sign the user out and
sever tab coordination. It is **frontend only** — the backend is never cycled — and a
switch **to** production builds first and swaps the server only if that build succeeds, so
a failed build leaves the running app exactly as it was.

**The supervisor carries the mode.** `scripts/dev/vite-supervisor.sh` reads
`COGITATE_FRONTEND_MODE` and runs `npx vite` or `npm run serve:production` accordingly; an
unknown mode fails loudly rather than defaulting to one. Note its clean-exit rule: **only a
clean exit ends the restart loop, so a killed child RESTARTS.** A mode switch therefore
stops the supervisor's process group rather than killing the vite process, which the
supervisor would dutifully undo.

**Which build is serving?** The dashboard's **build-mode badge** — `DEV` or `PROD` — and it
reports the *build*, not the host, because Vite bakes the flag in at build time; a scratch
server and a deployed one both read `PROD` and both are right. Programmatically, the served
entry module is `/src/main.tsx` in development and `/assets/index.<hash>.js` in production.
**That entry module is also how a client detects a completed switch** — the mode record is
written *before* the new server binds, so a client polling the record would reload straight
back into the old build.

**In production an edit is invisible until the bundle is rebuilt** — HMR does not apply.
Before concluding that a change "didn't take", check the badge: that is what makes a stale
bundle distinguishable from a broken one.

The mode is recorded in `.pids/frontend.mode`, written by the **launcher only**. One
writer, so the record cannot disagree with what is running. `GET /api/v1/system/mode` reads
it; `POST` requests a switch — contract in [[atlas/api/routers/system|System — API]].

## Verify (run this — the section's rule)

```bash
# the configured ports are the ones actually listening, and nothing else is:
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/health   # 200
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5173                # 200

# the proxy works (the browser's path to the backend):
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5173/api/v1/health  # 200

# CORS allows the configured frontend origin:
curl -s -D- -o /dev/null -X OPTIONS http://127.0.0.1:8000/api/v1/system/status \
  -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: GET" \
  | grep -i access-control-allow-origin
```

On an alternate port, all four must answer for **that** port, and the original
must be dead. Measured 2026-09-15 on `8100`/`5273`: 200 / 200 / 200 /
`access-control-allow-origin: http://localhost:5273`.

## The sweeps and tests follow

The gates read the same environment, so a port change does not silently disable
them:

| | follows? |
|---|---|
| the `backend` test skip-gate | **yes** — `COGITATE_BACKEND_URL` |
| the orphaned-app check | **yes** — `COGITATE_BACKEND_PORT` / `COGITATE_FRONTEND_PORT` |
| the frontend vitest suite | **unaffected** — jsdom, no real socket |
| the sweep itself | **unaffected** — it binds nothing |

**Still literal, and would need editing** if the ports move permanently:
`tests/e2e/test_chat_with_tools.py` and the `scripts/analysis/*` trace tools.
Those are diagnostics rather than gates; the gates are env-driven.

## Limits

- **One instance at a time.** The pid files (`.pids/backend.pid`,
  `.pids/frontend.pid`) are fixed paths, so a second launcher would overwrite the
  first's. Alternate ports let you *move* the app, not run two copies.
- **The database is shared**, not per-port: every instance points at the same
  `cogitate.db`.
