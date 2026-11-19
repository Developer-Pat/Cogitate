---
title: Frontend Architecture
type: atlas-entity
path: wiki/entities/frontend-architecture.md
confidence: medium
updated: 2026-08-05
tags: [type/entity, domain/entities]
---

# Frontend Architecture

## Overview

React + Vite + TypeScript. State via **Zustand** stores; server
state via **TanStack Query**; routing via react-router.

## Structure

- **pages/** — 29 page components (Dashboard, AgentInteraction,
  Sessions, ProviderDashboard, SetupPage, WikiViewer, Debugging...)
- **components/** — ui/ (widgets), features/ (per-domain), settings/
- **stores/** — zustand: agentProfilesStore, agentStore,
  chatMacrosStore, cognitiveHubStore, macroSetsStore...
- **providers/** — CognitiveHubProvider (boot/hydrate — NOT a
  context provider; the zustand store is the source of truth),
  QueryProvider
- **services/** — API clients per domain (profiles, providers,
  wiki, sessions, tools...)
- **hooks/** — useChatStreaming, useUIStateBridge, useWiki...

## Key patterns

- Zustand stores hold app state; components subscribe. ESLint rules
  enforce store usage (see [[dev-notes/architecture/zustand-stores]]).
- Server state via TanStack Query (react-query) with mutations.
- Wiki viewer: /wiki/{path} routes + wikilinks render as links.

## Routing table (config/routes.ts)

`/`, `/setup`, `/logs`, `/history`, `/configuration`, `/system-info`, `/settings`, `/macros`, `/agents/templates`, `/analytics`, `/sessions`, `/providers/:providerId/models`, `/workflow-templates`, `/providers`, `/provider-dashboard`, `/agent-interaction`, `/workflow-execution`, `/testing-dashboard`, `/debugging`, `/tools`, `/collections`, `/collections/:collectionId`, `/toolboxes`, `/toolboxes/:collectionId`, `/tool-collections/:collectionId`, `/teams`, `/teams/:teamId`, `/cognitive-pipeline`, `/agent-profiles`, `/wiki/*`

## Component tree

The UI atlas documents the full tree (pages → components by
feature area): see [[atlas/ui/UI Atlas|UI Atlas]] — pages (28),
components (grouped by feature: agentInteraction, workflows,
providers, cognitive, collections, debugging, tools, teams,
monitoring, history, logs, sessions, testing, forms, ui), hooks,
stores, services. State: zustand (client) + TanStack Query
(server).
