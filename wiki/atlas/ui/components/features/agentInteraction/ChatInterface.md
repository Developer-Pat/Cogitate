---
title: ChatInterface
type: atlas-component
path: frontend/src/components/features/agentInteraction/ChatInterface.tsx
confidence: high
updated: 2026-09-15
tags: [type/component, domain/atlas-ui]
---
# ChatInterface

**Path**: `frontend/src/components/features/agentInteraction/ChatInterface.tsx`
**Last Updated**: 2026-09-15

## Purpose

The main chat input container of the agent interaction page (rendered below the message stream). It is a **presentational** component: it owns the textarea draft state, attachments, macro insertion, and the send/stop controls, but delegates the actual message sending to the `onSendMessage` callback and the streaming lifecycle to the `isStreaming` / `onStopStreaming` props. It makes **no direct API or SSE calls** — streaming is orchestrated by the parent page via the `useAgentInteraction` -> `useChatStreaming` -> `StreamingService` -> `apiClient.stream()` chain.

The component composes: `MacroKeyboard` (with the bank selectors + the Exa ACP-trio slot), `LoadingIndicator`, `AttachmentPreview`, and `BadgeButton` (the under-Send controls). The standalone `TopicFlyoutButton` pill was REMOVED from the input row (2026-09-03, Phase 5b — the selectors live on the keyboard). Note that `ResponseStream` and `SessionManager` are **not** composed here — they are siblings rendered by the parent page (`pages/AgentInteraction.tsx`). The component is wrapped in `memo` with a custom comparator so parent re-renders caused by message updates during streaming do not re-render the input (it keeps its draft in local state).

## Props Interface

```typescript
interface ChatInterfaceProps {
  onSendMessage: (message: string, attachments?: File[]) => void
  isStreaming: boolean
  disabled?: boolean
  placeholder?: string
  onStopStreaming?: () => void
  onToggleRightPanel?: () => void
  agentId?: string
  sessionId?: string
}
```

Defaults: `disabled = false`, `placeholder = "Type your message..."`. The Send/Stop swap, the `Generating...` indicator, and textarea disabling are all driven by `isStreaming`. The attachment button is only rendered when `sessionId` is truthy.

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useRef`, `useEffect`, `memo`) | React hooks | Local draft/attachment/tool state, textarea auto-resize + focus management, memoized export with custom comparator |
| `useUIStore` (`stores/uiStore`) | Zustand store | `toggleSidebar` — wired to the Layout flyout's "Toggle navigation" item (the under-Send Layout controls, not a standalone button) |
| `useSystemMacrosStore` (`stores/macroSetsStore`) | Zustand store | `metaTopics`, `selectedMetaTopicId`, `selectMetaTopic`, `macroSets` (aliased `macros`), `loadMetaTopics`, `isLoadingMetaTopics`, `loadAllMacros` — feeds `MacroKeyboard`; on mount auto-loads meta topics and macros, and auto-selects the first topic with `namespace === 'agent'` |
| `MacroKeyboard` (`./MacroKeyboard`) | Child component | Macro/topic quick-insert + the bank selectors; `onMacroSelect` appends the macro text to the draft; receives `aKeysMetaTopicId` + `afterAKeys` (the Exa ACP trio, `agentId === 'exa'` only) |
| `TopicFlyoutButton` (`./TopicFlyoutButton`) | Child (via MacroKeyboard) | The bank selectors — no longer a direct ChatInterface child; the standalone pill row is gone |
| `LoadingIndicator` (`./LoadingIndicator`) | Child component | Spinner shown next to `Generating...` while `isStreaming` |

| `AttachmentPreview` (`./AttachmentPreview`) | Child component | Renders attached files with per-file `uploadProgress`, `onRemove`, `onSummarize` |
| `BadgeButton` (`../ui/BadgeButton`) | Child component (UI) | Icon buttons: the under-Send Collapse-long-responses control + the Layout control |
| `attachmentService` (`services/domain/AttachmentService`) | Domain service | `validateFile(file)` on selection — rejects files over 10 MB or outside the allow-list (`.md .txt .py .json .csv .yaml .yml .pdf .docx .xlsx .png .jpg .jpeg .gif .svg`); errors surface via `console.error` + `alert` |
| `Paperclip` (`lucide-react`) | Icon | Attach-file button icon |

## Usage Example

```tsx
// pages/AgentInteraction.tsx (the only consumer; default-imported)
<ChatInterface
  onSendMessage={(msg, attachments) => handleSendMessage(msg, selectedModel, attachments)}
  isStreaming={isStreaming}
  disabled={!selectedAgent || !currentSession}
  onStopStreaming={stopStreaming}
  placeholder={
    !selectedAgent
      ? "Select an agent to start chatting..."
      : !currentSession
      ? "Select or create a session to start chatting..."
      : `Message ${selectedAgent.name}...`
  }
  onToggleRightPanel={() => setSidebarOpen(!sidebarOpen)}
  agentId={selectedAgent?.id}
  sessionId={currentSession?.id ?? undefined}
/>
```

## State Used

Local `useState`:
- `inputValue` — textarea draft; drives auto-resize, character count, and `canSend`

- `attachedFiles: File[]` — validated files awaiting send, shown in `AttachmentPreview`
- `uploadProgress: number[]` — per-file progress mirrors `attachedFiles` indices
- `justSent` — triggers a 0 ms deferred refocus of the textarea after a send clears the input

Local `useRef`:
- `fileInputRef` — hidden `<input type="file">` (multiple; `accept` allow-list above), clicked by the attach button
- `textareaRef` — target for auto-resize (height reset to `auto`, then `scrollHeight`) and focus restoration

External store state: `useUIStore.toggleSidebar`; `useSystemMacrosStore` fields listed in Dependencies.

Note: the custom `memo` comparator only compares `isStreaming`, `disabled`, `placeholder`, `agentId`, `sessionId`, and the three callback props by identity — so inline lambdas for `onSendMessage`/`onToggleRightPanel` from the parent defeat memoization in practice (the comment in source acknowledges this trade-off is intentional).

## Send-Message Flow and Streaming Integration

1. **Compose**: user types in the textarea; `Enter` (without `Shift`) triggers `handleKeyDown` -> `e.preventDefault()` + `e.stopPropagation()` (stops bubble-up to page-level shortcuts) -> `handleSubmit`.
2. **Guard**: submit only proceeds when `(trimmedValue || attachedFiles.length > 0) && !disabled && !isStreaming`; otherwise it is a no-op.
3. **Send**: `onSendMessage(trimmedValue, attachedFiles.length > 0 ? attachedFiles : undefined)`; then the draft, attachments, and progress are cleared and `justSent` is set (textarea refocuses next tick).
4. **Parent chain**: the page forwards to `handleSendMessage(msg, selectedModel, attachments)` from `useAgentInteraction`, which routes to `useChatStreaming.startStream` -> `StreamingService` -> `apiClient.stream()` — an SSE request (`Accept: text/event-stream`, 60 s timeout, `AbortSignal` support) against the chat endpoint. `StreamingService` also emits cognitive-pipeline events consumed by the cognitive overlay.
5. **While streaming**: the parent sets `isStreaming = true`; ChatInterface disables the textarea and send button, hides Send, and shows the `Stop` button (`onStopStreaming` -> `stopStreaming` -> abort signal) plus `LoadingIndicator` + `Generating...`.
6. **Completion**: the parent flips `isStreaming = false`; ChatInterface refocuses the textarea after 100 ms (unless `disabled`).

## Related Components

- **Parent**: `frontend/src/pages/AgentInteraction.tsx` — composes `ChatInterface` with `ResponseStream` (message display) and `SessionManager` (right sidebar); wires streaming via `useAgentInteraction`
- **Sibling**: `frontend/src/components/features/agentInteraction/ResponseStream.tsx` — renders the streamed messages (`messages`, `isStreaming`, `cognitiveState`)
- **Sibling**: `frontend/src/components/features/agentInteraction/SessionManager.tsx` — right-panel session list, toggled by `onToggleRightPanel`
- **Children (same dir)**: `MacroKeyboard.tsx` (composes the bank selectors), `LoadingIndicator.tsx`, `AttachmentPreview.tsx` — `ToolPicker.tsx` + the standalone `TopicFlyoutButton.tsx` are no longer composed here
- **UI**: `frontend/src/components/ui/BadgeButton.tsx`
- **Stores**: `frontend/src/stores/uiStore.ts`, `frontend/src/stores/macroSetsStore.ts`
- **Service**: `frontend/src/services/domain/AttachmentService.ts`
- **Streaming chain (not imported by this file)**: `frontend/src/hooks/useAgentInteraction.ts` -> `frontend/src/hooks/useChatStreaming.ts` -> `frontend/src/services/domain/StreamingService.ts` -> `frontend/src/services/apiClient.ts` (`stream()`)

## Notes

**The composer takes a hand-off from the History tab.** Two optional props:

```typescript
pendingPrompt?: string | null
onPendingPromptConsumed?: () => void
```

An effect **appends** `pendingPrompt` to the input (matching how `handleMacroSelect`
inserts), focuses the textarea, and reports it consumed so the same prompt cannot
re-append on the next render. **It never sends** — the user still presses Send.

The hand-off exists because the composer's text state is **local to this component** and
the History tab lives in a SIBLING (`SessionManager`), so the page
([[atlas/ui/pages/AgentInteraction]]) carries it.

**Appending, not replacing**, is deliberate: a prompt is a starting point the user edits,
not a value that should silently eat a draft.

**`onDeselectSession` is DEPRECATED here.** The control lives in the panel header now.
The prop stays in the interface so the page's pass-through type-checks, but it is not
destructured; remove it with the commented block.
