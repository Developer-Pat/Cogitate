---
title: LoggingConfigPanel
type: atlas-component
path: frontend/src/components/settings/LoggingConfigPanel.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# LoggingConfigPanel

**Path**: `frontend/src/components/settings/LoggingConfigPanel.tsx`
**Last Updated**: 2026-08-01

## Purpose
Logging configuration panel (Settings) — toggles for flow-trace logging, deduplication, trace sampling rate, and backend logging. Polls loggingConfigService every second for external changes.

## Props Interface
```typescript
interface LoggingConfigPanelProps {
  onConfigChange?: (config: LoggingConfig) => void
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| loggingConfigService.getConfig/updateConfig | Service | Config read/write (subscriber pattern) |
| LoggingConfig | services/domain/LoggingConfigService | Config shape |
| ToggleSwitch | ui/ToggleSwitch.tsx | Toggle controls |

## Usage Example
```tsx
<LoggingConfigPanel onConfigChange={setLoggingConfig} />
```

## State Used
- config (mirrored from service via 1s polling interval)

## Related Components
- ui/ToggleSwitch.tsx — toggle primitive
- features/debugging/TraceControls.tsx — related runtime trace config
- services/domain/LoggingConfigService.ts — backing service