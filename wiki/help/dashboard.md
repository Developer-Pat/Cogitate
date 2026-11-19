---
title: Dashboard
category: dashboard
subtopic: Overview
order: 1
confidence: high
created: 2026-07-27
updated: 2026-09-17
tags: [domain/help]
---

# Dashboard

The dashboard is the home page — a launchpad for the main features,
plus a quick health snapshot.

## Navigation Cards

Four cards take you to the core areas:

- **Agent Chat** — the chat interface (`/agent-interaction`)
- **Sessions** — browse and manage conversation sessions
- **Logs** — system-wide log viewer
- **Wiki** — the project knowledge base (atlas + dev notes)

## Quick Stats

Four live stats, pulled from the backend:

- **System Status** — Healthy / Unhealthy (backend health probe)
- **CPU Usage** — current system CPU
- **Memory Usage** — current system memory
- **Recent Logs** — recent activity count

## Header indicators

- **Backend status dot** — green when the backend API is reachable.
  If it's red, the UI will still work but live data (stats, sessions,
  chat) won't load.
- **Version tag** — the current app build.
- **Build mode** — a **`DEV`** or **`PROD`** badge naming which build you are
  being served; hover it for the difference in one line. **Development** is
  the working build: unbundled and unminified, so it renders slower but
  picks up edits the moment they are saved. **Production** is the bundled,
  minified build — the one a deployment runs, and the one to use when you
  want to see the app the way a user would. The badge reports the **build,
  not the address**: a scratch server and a deployed one can both be `PROD`,
  and both would be right.
- **Switch to production** / **Switch to development** — moves the frontend
  between the two builds. It keeps the **same address**, so you stay signed
  in and your sessions, settings and open tabs are untouched. Switching **to
  production builds first** and swaps the server only if that build
  succeeds — a failed build leaves the running app exactly as it was.
- **Clear Cache** — clears the browser's cached copy and reloads.
- **Help button** — opens this help drawer.

## Related

- [Chat & Agent Interaction](/wiki/help/chat)
- [Logs](/wiki/help/logs)
- [Provider Dashboard](/wiki/help/providers)

## The Messages card

The **Messages** card shows the recent system messages + the unread
count — click "View all" to open the Message Center page.
