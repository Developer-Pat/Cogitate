---
title: chatService
type: atlas-service
path: frontend/src/services/domains/llm/chatService.ts
confidence: high
updated: 2026-08-01
tags: [type/service, domain/atlas-ui]
---
# chatService

**Path**: `frontend/src/services/domains/llm/chatService.ts`
**Type**: service (object, domain facade)

## Purpose
LLM chat completions — createChatCompletion + createStreamingChat (IChatService). Core chat backend client.

## Exported API
```typescript
export const chatService: IChatService = {
  createChatCompletion(...): Promise<ChatCompletionResponse>
  createStreamingChat(...): Promise<Response>  // SSE stream
}
```

## Endpoints
- `/api/v1/chat` (completion + stream)

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| apiClient | services/apiClient.ts | Requests (incl. stream()) |

## Usage Example
```tsx
const res = await chatService.createStreamingChat({ messages, agentId })
```

## Data Flow / Notes
- createStreamingChat powers the SSE chat stream; re-exported via ServiceFactory.getChatService()

## Related
- domain/StreamingService.ts — primary consumer (createStreamingChat)
- domain/TitleGenerationService.ts — consumer (createChatCompletion; itself obsolete)
- services/index.ts — DI facade

## Deprecation / Obsolete Notes
Active (used by StreamingService — core chat path). No deprecation markers.