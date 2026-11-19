---
title: ResponseStream
type: atlas-component
path: frontend/src/components/features/agentInteraction/ResponseStream.tsx
confidence: high
updated: 2026-09-17
tags: [type/component, domain/atlas-ui]
---
# ResponseStream

**Path**: `frontend/src/components/features/agentInteraction/ResponseStream.tsx`
**Last Updated**: 2026-09-17

## Purpose
Main chat message stream — renders the conversation as DaisyUI chat bubbles (user/assistant/system/tool roles), with markdown (react-markdown + remark-gfm + rehype-highlight), mermaid diagram rendering, auto-scroll with user-scroll override, copy-to-clipboard, message delete, tool-result display (badge + execution time + success state), and optional cognitive pipeline indicators.

**Streaming markdown is rendered block-wise.** While a response streams, the growing text is split into markdown blocks and each finished block is memoized on its own string, so only the block still being written re-renders. The splitter is `streamingMarkdown.ts` and the memoized block component lives in `MessageBubble.tsx`. The splitter is **conservative**: it declines to split where a boundary is not provably safe — loose lists, nested lists, and any document carrying a reference definition — because splitting those changes the rendered output. **Only the streaming branch splits**; a completed message renders whole, so the optimisation cannot alter final output. Design, contract and pitfalls: [[dev-notes/frontend/streaming-render|Streaming Render]].

## Props Interface
```typescript
// Base type from types/agentInteraction
export interface ResponseStreamProps {
  messages: ConversationMessage[]
  isStreaming: boolean
  onDeleteMessage?: (messageId: string) => void
}

// Extended in component
const ResponseStream = ({
  messages,
  isStreaming,
  onDeleteMessage,
  theaterMode = false,
  cognitiveState,   // CognitiveState from StreamingService
}: ResponseStreamProps & { theaterMode?: boolean; cognitiveState?: CognitiveState })
```

## Dependencies
| Dependency | Type | Purpose |
|------------|------|---------|
| ReactMarkdown + remark-gfm | Library | Markdown rendering (GFM) |
| streamingMarkdown (`./streamingMarkdown`) | Module (local) | The conservative block splitter used on the streaming branch |
| rehype-highlight + atom-one-dark.css | Library | Code syntax highlighting |
| mermaid | Library | `mermaid.run()` after streaming completes / new messages |
| CognitiveIndicator | Component (local) | Pipeline state indicators when enabled |
| useSettingsStore | Store | `settings.general.showPipelineIndicators` gate |
| useNotificationStore | Store | Copy/delete success toasts |
| frontendLoggingService | Service | mermaid + clipboard logging |

## Usage Example
```tsx
<ResponseStream messages={messages} isStreaming={streaming} onDeleteMessage={del} theaterMode={theater} cognitiveState={state} />
```

## State Used
- autoScroll (bool — disables when user scrolls up), messagesEndRef
- mermaid re-render effects keyed on isStreaming/messages (100ms delay)

## Related Components
- features/agentInteraction/CognitiveIndicator.tsx — pipeline indicators
- features/agentInteraction/ChatInterface.tsx — owner container
- features/agentInteraction/MessageMetadata.tsx — per-message metadata