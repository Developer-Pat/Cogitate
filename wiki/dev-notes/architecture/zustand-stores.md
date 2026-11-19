---
title: Zustand Store Patterns (FE↔BE)
type: atlas-devnote
category: architecture
order: 1
confidence: stub
updated: 2026-08-05
tags: [type/dev-notes, domain/architecture]
---

# Zustand Store Patterns (FE↔BE)

## Why this is a dev-note

Zustand stores are **architectural**: frontend state with backend
backing (e.g. the Cognitive Hub store is the source of truth while
the provider component only boots/hydrates it). The FE/BE division
of labor between dev-notes and the UI Atlas is **undecided** — this
page is the stub.

## Current shape

- Stores under frontend/src/stores/ (zustand).
- ESLint rules enforce store usage patterns
  (eslint-rules-store-usage.md is the topic guide).

## Store catalogue (frontend/src/stores/)

| Store | State |
|-------|-------|
| `streamStore` | chat stream chunks/status/error |
| `agentStore` | agent list/current |
| `agentProfilesStore` | profile form state |
| `cognitiveHubStore` | cognitive hub UI state |
| `providerHealthStore` | provider health scan |
| `chatMacrosStore` / `macroSetsStore` | macro sets/topics |
| `topicStore` | meta topics |
| `notificationStore` | toasts |
| `settingsStore` / `userStore` | settings/user |
| `sharedContextStore` | shared context |
| `syncQueueStore` | offline sync queue |
| `systemStore` / `uiStore` | system + UI state |

## FE ↔ BE flow

Stores hydrate via domain services (services/domain/*) → REST;
mutations via TanStack Query. ESLint store-usage rules
(`eslint-rules-store-usage.md` is the topic guide) enforce direct
store access over prop drilling where applicable.
