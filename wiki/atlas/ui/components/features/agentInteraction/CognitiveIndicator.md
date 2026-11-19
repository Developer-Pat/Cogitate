---
title: CognitiveIndicator
type: atlas-component
path: frontend/src/components/features/agentInteraction/CognitiveIndicator.tsx
confidence: high
updated: 2026-09-17
tags: [type/component, domain/atlas-ui]
---
# CognitiveIndicator

**Path**: `frontend/src/components/features/agentInteraction/CognitiveIndicator.tsx`
**Last Updated**: 2026-09-17

## Purpose

Renders a live visualization of the cognitive pipeline (context building → executor → memory management → response formatting) for an in-flight or completed streaming response. It consumes the `CognitiveState` snapshot produced by `StreamingService` (fed via the `onCognitiveEvent` callback) and shows, per pipeline component, whether it is `pending`, `active`, or `done`, along with timings, token/LLM/tool-call metrics from the final trace, and the executor's granular stage (thinking, streaming, executing, …).

Two visual variants exist:
- **Full variant** (default): a stacked card with a "🧠 Cognitive Pipeline" header, one row per pipeline component with icon, label, status color, and per-component duration, plus a footer of trace metrics (tokens, LLM calls, tool calls, compaction warning).
- **Compact variant** (`compact`): a single-line row of small pill badges (one per component) with tooltip labels, total duration, token count, and a spinner while active. Used by `ResponseStream` inline next to the last message.

Renders `null` when the pipeline is neither active nor has any recorded events.

## Props Interface

```typescript
interface CognitiveIndicatorProps {
  cognitiveState: CognitiveState
  /** If true, renders a compact inline version (for embedding in the message area) */
  compact?: boolean
}
```

The `CognitiveState` type (from `frontend/src/services/domain/StreamingService.ts`):

```typescript
export interface CognitiveState {
  /** Ordered list of cognitive events received during the current stream */
  events: CognitiveEvent[]
  /** Latest trace data (set when cognitive_trace_complete arrives) */
  latestTrace: CognitiveTraceCompleteEvent | null
  /** Whether the cognitive pipeline is currently active */
  isActive: boolean
  /** Current executor stage (e.g. 'streaming', 'thinking', 'idle') */
  executorStage: string
}
```

### Visualized pipeline phases & executor stages

The component maps the four pipeline components (keys of `STAGE_CONFIG`) to the `cognitive_*` SSE event types:

| Component key | Icon | Label | Completion event |
|---|---|---|---|
| `context_builder` | 🔍 | Context | `cognitive_context_built` |
| `executor` | 🧠 | Thinking | `cognitive_executor_completed` |
| `memory_manager` | 💾 | Memory | `cognitive_memory_updated` |
| `response_formatter` | ✍️ | Format | `cognitive_response_formatted` |

A `cognitive_trace_complete` event marks all four components `done`. The executor's sub-stages (`EXECUTOR_STAGES`, shown beside the executor badge while it is active) are `thinking` 🤔, `streaming` 📝, `executing` 🔧 and `completed` ✅. **There is deliberately no `idle` entry and no fallback:** a stage outside the map renders **no label at all**, because a fallback puts a label on screen that the badge's own tooltip contradicts — the badge reads "Thinking: active" while the text beside it says "Idle".

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useMemo`) | Hook | Memoizes the per-component `pending/active/done` status derivation from the `events` array |
| `CognitiveState`, `CognitiveEvent` | Types (`frontend/src/services/domain/StreamingService.ts`) | Props contract and event-type discrimination for status/timing extraction |

No stores, services, or context are used — the component is fully controlled by its `cognitiveState` prop.

## Usage Example

```tsx
import CognitiveIndicator from './CognitiveIndicator'
import type { CognitiveState } from '../../../services/domain/StreamingService'

// In ResponseStream.tsx — compact inline variant next to the last message:
{index === messages.length - 1 && cognitiveState && showPipelineIndicators && (
  <div className="ml-2">
    <CognitiveIndicator cognitiveState={cognitiveState} compact />
  </div>
)}

// Full detailed variant (e.g. in a debug panel):
<CognitiveIndicator cognitiveState={cognitiveState} />
```

## State Used

No local component state and no external stores. All data is derived from the `cognitiveState` prop:

- `isActive`, `executorStage`, `events`, `latestTrace` (destructured from `cognitiveState`).
- Per-component status (`pending`/`active`/`done`) derived in a `useMemo` from `events`.
- Total duration / tokens from `latestTrace.trace.total_duration_ms` / `latestTrace.trace.total_tokens`.
- Per-component durations from the last matching event's `data.duration_ms`.
- Footer metrics from `latestTrace.metrics.llm_calls`, `latestTrace.metrics.tool_calls`, and `latestTrace.memory_delta.compaction_triggered`.

## Related Components

- `frontend/src/components/features/agentInteraction/ResponseStream.tsx` — primary consumer; renders the compact variant inline on the last message when `showPipelineIndicators` is enabled.
- `frontend/src/services/domain/StreamingService.ts` — source of `CognitiveState`, `CognitiveEvent` (incl. `CognitiveTraceCompleteEvent`), produced via the `onCognitiveEvent` stream callback.
