---
title: Settings
type: atlas-page
path: frontend/src/pages/Settings.tsx
confidence: high
updated: 2026-07-31
tags: [type/page, domain/atlas-ui]
---
# Settings

**Component**: `frontend/src/pages/Settings.tsx`
**Route**: `/settings`
**Last Updated**: 2026-07-31

## Purpose
User preferences page — appearance, general, notifications, and data (export/import/reset). Backed by `settingsStore` which persists to the backend settings API.

## Key Features
- **4 tabs**: Appearance, General, Notifications, Data
- **Appearance**: ThemeSelector (font size, compact mode, animations)
- **General**: language, timezone, title-generation model preference (agent/backend default/custom), auto-title toggle, onboarding tips toggle, macro ID tooltips toggle
- **Notifications**: email/push/system alerts toggles, frequency select
- **Data**: export settings as JSON (client-side), import from JSON file, reset to defaults
- Unsaved-changes indicator + last-synced timestamp
- Context help button (context: settings)

## Components Used
| Component | Path | Purpose |
|-----------|------|---------|
| PageBanner | `components/ui/PageBanner.tsx` | Page header |
| PageContainer | `components/ui/PageContainer.tsx` | Layout wrapper |
| ThemeSelector | `components/ui/settings/ThemeSelector.tsx` | Appearance controls (font size, compact, animations) |
| HelpButton | `components/help/HelpButton.tsx` | Help drawer (context: settings) |

## Hooks Used
| Hook | Path | Purpose |
|------|------|---------|
| usePageTitle | `hooks/usePageTitle.ts` | Sets document title |

## Data Flow
- **Load**: `useSettingsStore().loadSettings()` on mount -> `userSettingsService.getSettings()` -> `GET /api/v1/settings` -> Zustand state
- **Save**: `updateSettings(settings)` -> `userSettingsService.updateSettings()` -> `PUT /api/v1/settings` (every tab's Save button)
- **Reset**: `resetSettings()` -> defaults + sync to backend
- **Export/Import**: pure client-side JSON (data URI download / file read + `updateSettings`)
- `settingsStore` holds the working copy; all mutations update store first, sync on save

## State Management
- `settingsStore` (Zustand) — settings, isLoading, error, lastSyncedAt; actions loadSettings/updateSettings/resetSettings
- `notificationStore` — toasts for save/reset/import outcomes
- Local state: activeTab, hasUnsavedChanges

## API Endpoints Called
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/settings` | Load user settings |
| PUT | `/api/v1/settings` | Persist settings |

## Related Pages
- Configuration — static placeholder; Settings is the functional counterpart
- AgentInteraction — title-generation model preference affects chat sessions