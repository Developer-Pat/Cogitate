---
title: useChatStreaming
type: atlas-hook
path: frontend/src/hooks/useChatStreaming.ts
confidence: high
updated: 2026-08-01
tags: [type/hook, domain/atlas-ui]
---
# useChatStreaming

**Path**: `frontend/src/hooks/useChatStreaming.ts`
**Type**: hook

## Purpose
Thin React wrapper around StreamingService — handles callback wiring, state subscription (100ms polling), and cognitive-state sync for chat streaming.

## Exported API
```typescript
interface UseChatStreamingOptions {
  agent: Agent | null
  session: ConversationSession | null
  onMessageComplete?: (message: ConversationMessage) => void
  onStreamStart?: () => void
  onStreamError?: (error: Error) => void
  onAddMessage?: (message: ConversationMessage, sessionId: string) => void
  onUpdateMessage?: (messageId: string, content: string, metadata?: unknown, sessionId?: string) => void
  onCognitiveEvent?: (event: CognitiveEvent) => void
}

interface UseChatStreamingReturn {
  isStreaming: boolean
  streamingMessage: ConversationMessage | null
  error: string | null
  startStream: (content: string, overrideModel?: string, attachmentIds?: number[]) => Promise<void>
  stopStream: () => void
  sendMessage: (content: string, overrideModel?: string, attachmentIds?: number[]) => Promise<void>
  cognitiveState: CognitiveState
  getCognitiveState: () => CognitiveState
}
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| StreamingService | domain/StreamingService.ts | Stream engine (singleton per hook via useRef) |
| StreamingCallbacks, CognitiveEvent, CognitiveState | StreamingService types | Callback + state shapes |
| Agent, ConversationSession, ConversationMessage | types/agentInteraction | Data shapes |

## Usage Example
```tsx
const { isStreaming, sendMessage, cognitiveState } = useChatStreaming({ agent, session, onMessageComplete: addMsg })
await sendMessage('hello', undefined, attachmentIds)
```

## State / Data Flow
- Wraps StreamingService.startStream(content, { agent, sessionId, callbacks, attachmentIds })
- Callback refs wired to React state (isStreaming, streamingMessage, error, cognitiveState)
- 100ms setInterval syncs service state → React state (incl. cognitive state)
- overrideModel clones agent with model override before streaming

## Related
- useAgentInteraction.ts — orchestrates this hook
- services/domain/StreamingService.ts — engine (961 lines)
- features/agentInteraction/ChatInterface.tsx — consumer