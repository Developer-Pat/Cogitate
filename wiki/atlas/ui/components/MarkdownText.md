---
title: MarkdownText
type: atlas-component
path: frontend/src/components/ui/MarkdownText.tsx
confidence: high
updated: 2026-09-18
tags: [type/component, domain/atlas-ui]
---
# MarkdownText

**Path**: `frontend/src/components/ui/MarkdownText.tsx`

## Purpose

Renders markdown on the **small** surfaces — the ask-Exa flyout's answer and the Exa side
panel's messages. Exa writes markdown; as a plain `<p>` a link is just characters, a list is
dashes and a table is pipes.

It lives in the shared kit (`components/ui/`) rather than a feature folder because it is
generic: it knows nothing about agents, Exa or chat. More than one surface renders markdown, and
a general renderer inside a feature folder makes the second consumer reach into someone else's
territory.

## Why not ResponseStream

`ResponseStream` is the chat's renderer and carries TTS, the cognitive indicator, mermaid, the
fold and the macro keyboard. The job here is only "show what the model wrote, and make the links
work" inside a compact panel. Reuse would put chat behaviour on a flyout.

## Streaming: why it splits into blocks

Text that **grows** re-parses on every update, and re-parsing a whole document per token is the
expensive shape. So the text is cut at block boundaries and each block is memoized: while a
reply streams, only the block still being written re-parses, and finished blocks are skipped
entirely.

The saving is measurable, not theoretical — on the Exa panel a ~40s streaming turn went from
**31.2s to 3.2s** of long-task time, with the per-second tick dropping from ~930ms to ~54ms
(the panel re-renders on a one-second elapsed timer as well as per stream chunk, which is what
made the cost so visible).

The splitter lives in `utils/text/streamingMarkdown.ts` and is **conservative by design**: a
false split renders wrong, so it refuses to split anything it is not sure about and returns the
whole text as one block. A missed split only costs time.

## The two link rules

| href | rendered as | why |
|---|---|---|
| starts with `/` | router `Link` — **no `target`** | a clicked link navigates **in place**, which is what a link should do |
| anything else | `<a target="_blank" rel="noopener noreferrer">` | a model-written link must never navigate the SPA away from the user's page, nor reach `window.opener` |

Same rule `WikiViewer` already applies. Note this is deliberately *unlike* the navigation
**command verbs**, which open a new tab — that convention exists so an AI-driven jump does not
destroy the user's session; a link the user clicks is a different intent.

## Props

```typescript
interface MarkdownTextProps {
  children: string   // the markdown
  className?: string // layout only (the panel keeps its own scroll)
}
```

## Deliberate omissions

- **No `rehype-highlight`.** Syntax colouring is a chat-surface luxury; code still renders
  legibly as `<pre><code>`.
- **No raw HTML.** react-markdown escapes it, so an answer cannot inject markup.

## Used by

- `components/agentPanel/AgentPanel` — the Exa side panel's message rows.
- `features/agentInteraction/ExaPromptFlyout` — the answer text.

## Related

- [[atlas/ui/components/features/agentInteraction/ResponseStream|ResponseStream]] — the chat's fuller renderer
- [[atlas/ui/pages/WikiViewer|WikiViewer]] — the same link rule, independently
- [[dev-notes/frontend/app-navigation-channels|Navigating the app]] — the three nav channels
