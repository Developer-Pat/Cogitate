---
title: The streaming render
type: dev-note
category: frontend
subtopic: performance
confidence: high
created: 2026-09-17
updated: 2026-09-17
tags: [type/dev-notes, domain/frontend, domain/ui]
---

# The streaming render

How an agent reply is rendered while it streams. Read this before changing
`MessageBubble`'s render path, or before touching anything that formats markdown
that arrives incrementally.

## The constraint

While a reply streams, the message's accumulated text grows and the bubble
re-renders it. Rendering the **whole** document on each update means re-parsing
and re-creating the entire element tree every time — and the work scales with the
text the user has already read, not with the new text.

Markdown is *almost* compositional: a finished block is a stable string, so it
can be memoized and skipped, leaving only the trailing partial block to re-parse.
That is what this path does.

## The pieces

| | |
|---|---|
| `components/features/agentInteraction/streamingMarkdown.ts` | `splitStreamingMarkdown(text)` — the splitter. A pure string scan; it never parses markdown. |
| `MessageBubble` | `MarkdownBlock` — one block, wrapped in `memo` comparing its own text. `StreamingMarkdown` — splits, then renders the blocks. |

**Only the streaming branch splits.** The fold branch (long, non-streaming
replies) renders the document whole, because that output is what the user keeps
and nothing about it needs to be incremental.

**Keys are positional.** A block's text never changes once the next block exists,
and the memo compares text — so if a boundary ever shifted, the worst case is a
re-render, never a wrong render.

## The contract

`splitStreamingMarkdown(text)` returns a list of blocks such that **rendering the
blocks separately produces the same DOM as rendering the document whole** — or it
returns `[text]`, declining to split, when it cannot guarantee that.

**A single-element result is the safe answer, not a failure.** Declining costs
only performance. Splitting wrongly changes what the user sees, and during a
stream they are reading the text as it arrives, so a visible change is worse than
a slow render.

## Why a naive blank-line split does not work

Splitting at every blank line breaks these constructs:

1. **Loose lists.** A blank line between list items does **not** end the list — it
   is what makes the list *loose*. Splitting there turns one loose list into
   several separate tight lists, changing the list's markup and spacing. A blank
   line before a nested sub-list behaves the same way.
2. **Reference definitions.** `[x]: url` resolves document-wide. A block cut away
   from its definition renders `[text][x]` literally instead of as a link.

So the splitter refuses to cut:

- anywhere inside a fence (a code block may contain blank lines);
- when the document contains any reference definition at all;
- when the next non-blank line is a **list item** — it may continue the current
  list;
- when the next non-blank line is **indented** — it is a continuation of the
  previous block.

It only cuts where the next line clearly begins a new top-level block: a heading,
fence, table, blockquote, HTML block, or ordinary prose.

## Extending it

The corpus in `__tests__/streamingMarkdown.test.tsx` is the specification. It
asserts both halves of the contract:

- **renders identically** whether the document is rendered whole or split;
- **actually splits** the prose case.

The second one exists because a test of only the first would pass against a
splitter that never splits — correct, and useless. Cases also assert that the
splitter **declines** where splitting would be unsafe. Add a case before adding a
rule.

## Measuring a stream

If you change this path, measure it rather than reasoning about it. In the page,
with no code changes:

```js
// blocked main-thread time
new PerformanceObserver(l => { for (const e of l.getEntries()) lt.push(e.duration) })
  .observe({ type: 'longtask', buffered: false })

// UI updates: sample the message container, count text-length changes
previously !== (document.querySelector('.messages-container').innerText.length)
```

**Two traps:**

- **Message bubbles carry no identifying attribute.** The container is
  `.messages-container` (`ResponseStream.tsx`). A made-up selector returns
  silently empty results, which reads as "nothing rendered".
- **A backgrounded tab throttles rendering.** A hidden-tab measurement is not a
  measurement — bring the page to the front first.

**The worst single long task is the number the user feels** as a stutter; the
total is the second. Frame timing alone will mislead you.

## Related

- [[dev-notes/known-issues|Known Issues]] — the standing defect list
- [[atlas/ui/UI Atlas|UI Atlas]] — the component map
