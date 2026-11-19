---
title: Navigation & Routing
type: atlas-devnote
category: frontend
order: 5
confidence: stub
updated: 2026-09-15
tags: [type/dev-notes, domain/frontend]
---

# Navigation & Routing

Frontend routing: react-router with routes declared in
frontend/src/config/routes.ts; the sidebar renders nav links
manually; the wiki viewer navigates via /wiki/{path} with
breadcrumbs.

## Route groups (config/routes.ts)

- **Pages**: `/`, `/setup`, `/logs`, `/history`, `/configuration`,
  `/system-info`, `/settings`, `/macros`, `/analytics`,
  `/sessions`, `/providers`, `/provider-dashboard`,
  `/agent-interaction`, `/workflow-execution`,
  `/testing-dashboard`, `/debugging`, `/tools`, `/collections`,
  `/toolkits`, `/teams`, `/cognitive-pipeline`, `/agent-profiles`
- **Parametric**: `/providers/:providerId/models`,
  `/collections/:collectionId`, `/toolkits/:collectionId`,
  `/teams/:teamId`
- **Utility**: `/agents/templates`, `/workflow-templates`,
  `/wiki/*` (the wiki viewer)

## Sidebar

Collapsible nav groups (collection, teams, tools, agents,
workflows, debugging...) — manual link rendering from the route
table.

## New-tab navigation

The message-buttons (the AgentInteraction + the ExaChat headers) open
their destinations in a **new tab** via the tab-services' navigation
service (`navigateTo` → `window.open`) — the current tab is never
left. The browser's tabs are the navigation. See
[[dev-notes/frontend/tab-services|Tab Services]].

The **command box** opens the same way under its `open`/`show` verbs, but with
a STABLE window name per destination: asking for the same page twice
FOCUSES the tab already open instead of stacking a duplicate. Its page map is
generated from the route table above, so a new route is reachable from the box
the moment it is routed — there is no second list to keep in step. `nav`/`goto`
move the current page in place instead, and the bridge's `navigation_request`
is the backend-driven in-place channel. See
[[dev-notes/frontend/command-box|The Command Box]].

## Wiki-viewer contract

`/wiki/{path}` — the viewer resolves wikilinks against the wiki
API, renders breadcrumbs, and falls back to the atlas root for
bare dirs. See the wiki router docs in the API Atlas.

## The Configuration section (2026-08-31, the _28 arc)

The sidebar's CONFIGURATION section (between the Workflows and the
Utilities) is the app's config home, ALPHABETICAL:

Configuration (/configuration) -> Macros (/macros) -> Notifications
(/notifications-config) -> Pipeline Config (/cognitive-pipeline) ->
Provider Dashboard (/provider-dashboard) -> Settings (/settings) ->
Speech (/speech) -> System Configs (/system-configs).

- The Speech + Notifications pages re-homed from the Assets (the
  _27 phases 2-3); the Sounds page STAYS the Assets (the wav
  catalog — the asset, not the config).
- The five roundup moves: Configuration, Settings, Pipeline
  Config, Provider Dashboard, Macros (the old homes: the System
  section, the Utilities, the Agents).
- The System Configs page (the _28 Phase-5): the status/info +
  the config-surfaces pointers — the 'coming' placeholder's
  replacement.
- The convention: the section's entries stay alphabetical; the
  docs' atlas entries record the nav home per page.
