---
title: LogDetailsModal
type: atlas-component
path: frontend/src/components/logs/LogDetailsModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# LogDetailsModal

**Path**: `frontend/src/components/logs/LogDetailsModal.tsx`
**Last Updated**: 2026-08-01

## Purpose

Modal dialog showing the full details of a single log entry (the log viewer's "detail view"). Rendered by the Logs page whenever a row is selected; it displays the entry's level (with color-coded badge), source, timestamp, message, and — when present on the entry — trace ID, session ID, URL, user agent, and a pretty-printed JSON context block. Each displayed value except User Agent has a per-field 📋 Copy button that writes the value to the clipboard via the browser Clipboard API and records the action through `frontendLoggingService`. Dismissal happens by clicking the ✕ button, the Close button, or clicking the backdrop overlay (overlay click calls `onClose`; clicks inside the modal box are stopped from propagating so the modal doesn't close accidentally). Returns `null` when `selectedLog` is `null`, rendering nothing.

## Props Interface

```typescript
interface LogDetailsModalProps {
  selectedLog: LogEntry | null
  onClose: () => void
}
```

`selectedLog` is the `LogEntry` being inspected (`null` hides the modal); `onClose` is invoked when the user dismisses the modal. `LogEntry` (from `frontend/src/types/index.ts`) carries `id`, `timestamp`, `level`, `source`, `message`, and optional `context`, `userId`, `sessionId`, `user_agent`, `url`, `trace_id`, `log_type`, `created_at`.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `LogEntry` (from `../../types`) | Type import | Shape of the `selectedLog` prop |
| `frontendLoggingService` (from `../../services/frontendLoggingService`) | Service | Logs copy-to-clipboard successes (`info`) and failures (`error`) with the `'LogDetailsModal'` source |
| `navigator.clipboard.writeText` | Web API | Async clipboard write backing every Copy button |
| DaisyUI modal/badge/tooltip classes + CSS variables (`--button-radius`, `--button-padding`, `--button-transition`) | Styling | Modal shell, level badges, tooltips, button theming |

No hooks, stores, or context are used.

## Usage Example

```tsx
import { useState } from 'react'
import LogDetailsModal from '../components/logs/LogDetailsModal'
import type { LogEntry } from '../types'

function Logs() {
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null)

  return (
    <>
      {/* ...log table that calls setSelectedLog(entry) on row click... */}
      <LogDetailsModal
        selectedLog={selectedLog}
        onClose={() => setSelectedLog(null)}
      />
    </>
  )
}
```

## State Used

None — the component is fully controlled. Selection state (`selectedLog`) and the dismiss handler (`onClose`) are owned by the parent (see `Logs.tsx`, which keeps `selectedLog` in `useState` and passes `handleModalClose`). The only internal logic is the local `copyToClipboard` helper (async, with success/error logging) and `getLevelColor` (maps a `LogLevel` string to a DaisyUI badge class: `debug` → neutral, `info` → `badge-info`, `warning` → `badge-warning`, `error` → `badge-error`, `critical` → `badge-error` + `bg-red-800`, unknown → `badge-ghost`).

## Related Components

- `frontend/src/pages/Logs.tsx` — sole consumer; owns `selectedLog` state and renders the modal at the bottom of the page
- `frontend/src/components/logs/LogsTable.tsx` — row-selection UI that supplies the entry (`onLogSelect`)
- `frontend/src/components/logs/LogFilters.tsx` — filter controls on the same page
- `frontend/src/components/ui/PageContainer.tsx` / `frontend/src/components/help/HelpButton.tsx` — page scaffolding used by `Logs.tsx`
- `frontend/src/types/index.ts` — defines `LogEntry` and `LogLevel`
