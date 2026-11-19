---
title: Onboarding Patterns (stub)
type: atlas-devnote
category: onboarding
order: 1
confidence: stub
updated: 2026-08-05
tags: [type/dev-notes, domain/onboarding]
---

# Onboarding Patterns

## Purpose

Orientation for developers new to the codebase: the patterns used
across frontend and backend.

## What's being rewritten

The old docs/architecture/newbies/ guides covered:
- **Frontend patterns** — hooks pattern, component conventions
- **Backend patterns** — service-layer architecture
- **UI system** — DaisyUI components
- **Application atlas** — app overview (superseded by this wiki)

## Frontend patterns

- **Hooks** per domain (`useAgentInteraction`, `useChatStreaming`,
  `useSessionManagement`, `useUIStateBridge`...) — feature hooks
  own interaction logic.
- **Zustand stores** for client state (see
  [[dev-notes/architecture/zustand-stores|Zustand Stores]]);
  **TanStack Query** for server state + mutations.
- Services in `services/domain/*` (typed API wrappers).

## Backend patterns

- Layered: routers (thin) → domain services (logic) →
  infrastructure (DB). DI via `Depends(get_db)` +
  `get_*_service` factories (see
  [[entities/backend-architecture|Backend Architecture]]).
- Strategy pattern: ABC interface → Registry →
  create_default_registry() factory (cognitive pipeline,
  providers).

## UI system

- **DaisyUI** components (btn, card, modal, table, toggle) +
  Tailwind v4 + `@tailwindcss/typography` (prose). Theme via
  `data-theme` on the root; components adapt via
  `theme-*` utilities. See the UI Atlas for the component
  inventory.d newbies/ guides are the topic
> guide; much is stale (pre-rewrite).
