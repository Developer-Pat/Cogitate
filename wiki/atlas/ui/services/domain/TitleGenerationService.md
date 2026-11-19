---
title: TitleGenerationService
type: atlas-service
path: frontend/src/services/domain/TitleGenerationService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# TitleGenerationService

**Path**: `frontend/src/services/domain/TitleGenerationService.ts`
**Type**: service (class)

## Purpose
LLM-based session title generation — generate, generateWithFallback, fallback title.

## Exported API
```typescript
export class TitleGenerationService {
  generateTitle(...): Promise<string>
  generateTitleWithFallback(...): Promise<string>
  generateFallbackTitle(...): string
}
```

## Endpoints
- Chat title endpoint (trace exact path — TitleService uses /api/v1/chat/generate-title)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests |
| frontendLoggingService | services | Logging |

## Usage Example
```tsx
const title = await new TitleGenerationService().generateTitle(message)
```

## Data Flow / Notes
- Only referenced by its own test file — superseded by TitleService

## Related
- domain/TitleService.ts — the ACTIVE title service (generateTitleInBackground)
- __tests__/TitleGenerationService.test.ts — only reference

## Deprecation / Obsolete Notes
**OBSOLETE — only its own test references it.** TitleService (titleService singleton) provides the active generateTitleInBackground with /api/v1/chat/generate-title. TitleGenerationService is a leftover/duplicate — candidate for removal (no consumers).