---
title: Markdown Elements
type: atlas-devnote
category: display-tests
order: 1
confidence: high
updated: 2026-08-06
tags: [type/dev-notes, domain/display-tests]
---

# Markdown Elements — Numbered Test Blocks

> Report issues by block number: "Text 2 has no bold", "Table 3 is
> broken", etc.

## Text Blocks

**Text 1 — plain paragraph.** This is a normal paragraph with
**bold**, *italic*, `inline code`, and a [link to the wiki index](/wiki/Site%20Index).
It should render as a paragraph with styled inline elements.

**Text 2 — heading hierarchy.** Below this line there should be an
h4, an h5, and an h6, each visibly smaller than the last.

#### Heading 4
##### Heading 5
###### Heading 6

**Text 3 — blockquote.** A blockquote with a nested list:

> This is a blockquote.
> - Item one in the quote
> - Item two in the quote
>
> Second paragraph of the quote.

**Text 4 — task list.** GFM task list (requires remark-gfm):

- [x] Checked item
- [ ] Unchecked item
- [ ] Another unchecked

## Tables

**Table 1 — basic table.** Should render with header row + borders.

| Name | Role | Status |
|------|------|--------|
| Alice | Researcher | active |
| Bob | Reviewer | idle |
| Carol | Writer | active |

**Table 2 — table with inline code + links.** Cells containing
`code`, **bold**, and [links](/wiki/Site%20Index).

| Config | Value | Notes |
|--------|-------|-------|
| `provider` | openrouter | [docs](/wiki/entities/provider-management) |
| **timeout** | `30` | bold cell |
| `model` | deepseek-v4 | *italic cell* |

**Table 3 — alignment + multi-line cell.** Should respect the
colons (left/center/right) and wrap long content.

| Left | Center | Right |
|:-----|:------:|------:|
| short | short | short |
| a much longer value that should wrap | centered | a long right-aligned value that should also wrap to test column sizing |

## Code Blocks

**Code 1 — fenced code with language.** Should render with syntax
highlighting (rehype-highlight).

```python
def hello(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"
```

**Code 2 — JSON block.**

```json
{
  "provider": "deepseek",
  "model": "deepseek-v4-flash",
  "fallback_enabled": false
}
```

**Code 3 — plain fenced block (no language).**

```
This block has no language hint.
It should still render as a code block.
```

**Code 4 — inline code only.** The `run()` call and the `_db_path`
attribute should appear in monospace inline.

## Lists

**List 1 — nested ordered list.** Indentation levels should nest.

1. First
   1. First nested
   2. Second nested
2. Second
   - Unordered nested
   - Another

**List 2 — definition-ish list.** A bullet list with bold lead-ins.

- **Overview** — the main section
- **Details** — supporting info
- **Notes** — miscellaneous

## Misc

**Misc 1 — horizontal rule.** There should be a visible divider below.

---

**Misc 2 — wikilink alias.** This uses [[display-tests/markdown-elements|alias form]]
— should render as a clickable link labeled "alias form". (No backticks —
a real wikilink in normal text.)

**Misc 3 — stale-name check.** (intentionally none here)
