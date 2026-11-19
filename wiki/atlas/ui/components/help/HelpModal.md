---
title: HelpModal
type: atlas-component
path: frontend/src/components/help/HelpModal.tsx
confidence: high
updated: 2026-08-01
tags: [type/component, domain/atlas-ui]
---
# HelpModal

**Path**: `frontend/src/components/help/HelpModal.tsx`
**Last Updated**: 2026-08-01

## Purpose

The core of the wiki-backed help system. Renders a right-drawer overlay (converted from an earlier center-modal layout) that displays help documentation served by the wiki API (`/api/v1/wiki/help` markdown pages). It is context-sensitive: it opens help content for the page the user is currently on, keyed by a `context` string that maps to wiki `help/` pages matched by their frontmatter `category`.

The component is **uncontrolled** — it listens for a global `open-help-modal` CustomEvent (dispatched by `HelpButton`) rather than being driven by props. The optional `isOpen` prop is accepted but deliberately ignored (renamed `_controlledIsOpen`).

Features:
- Right-drawer overlay (slides in from the right edge, 560px wide)
- Markdown rendering via `react-markdown` with custom Mermaid diagram support
- Help index grouped by category with expandable/collapsible groups
- Back button + keyboard navigation with an in-memory navigation history stack
- Related Topics navigation (same category, different page)
- Loading spinner and error alert states

## Props Interface

```typescript
interface HelpModalProps {
  isOpen?: boolean;
  onClose?: () => void;
  initialContext?: string;
}
```

Note: `isOpen` is accepted but unused (`_controlledIsOpen`); open/close is driven entirely by the `open-help-modal` event and the internal `isOpen` state. `onClose` is invoked when the modal closes (backdrop click, Escape, X button, or Close footer button). `initialContext` seeds the initial context state (defaults to `help_page`).

## Dependencies

| Dependency | Type | Purpose |
|---|---|---|
| `react` (`useState`, `useEffect`, `useCallback`) | hooks | Component state, event-listener lifecycle effects, memoized callbacks |
| `react-markdown` (`ReactMarkdown`) | npm package | Renders wiki markdown content; custom `code` component swaps in Mermaid rendering (no `remark-gfm` plugin is used) |
| `mermaid` | npm package | Renders fenced ` ```mermaid ` code blocks to SVG. Initialized module-level: `startOnLoad: false`, `theme: 'default'`, `securityLevel: 'loose'`, `fontFamily: 'inherit'` |
| `lucide-react` | npm package | Icons: `X`, `HelpCircle`, `ChevronRight`, `ChevronDown`, `Book` |
| `frontendLoggingService` (`../../services/frontendLoggingService`) | internal service | Error logging for failed index loads, page fetches, back-navigation, and Mermaid render failures |

## Usage Example

`HelpModal` is not mounted with props in normal usage — it is opened by the global event dispatched from `HelpButton` (or any component that dispatches `open-help-modal`). Mount the drawer once at app root, then open it from anywhere:

```tsx
// App shell — mount once
import { HelpModal } from '../components/help/HelpModal';

function App() {
  return (
    <>
      <Header /> {/* contains <HelpButton context="settings" /> */}
      <HelpModal />
    </>
  );
}
```

```tsx
// HelpButton dispatches the event the modal listens for
// (see frontend/src/components/help/HelpButton.tsx)
window.dispatchEvent(
  new CustomEvent('open-help-modal', {
    detail: {
      context: 'settings',               // maps to wiki/help pages with frontmatter category: settings
      documentTitle: 'Help',
      timestamp: new Date().toISOString(),
    },
  })
);
```

## State Used

| State | Type | Initial | Purpose |
|---|---|---|---|
| `isOpen` | `boolean` | `false` | Drawer visibility; renders `null` when closed |
| `context` | `string` | `initialContext \|\| 'help_page'` | Current help context; set from `event.detail.context`; used to highlight the active category in the index |
| `content` | `string` | `''` | Raw markdown of the current page (preprocessed for wikilinks before render) |
| `title` | `string` | `'Help'` | Current page title shown in the header |
| `currentPage` | `WikiHelpPage \| null` | `null` | Currently open page object (slug, title, category, subtopic, order, content, summary, frontmatter) |
| `allPages` | `WikiHelpPage[]` | `[]` | All help pages loaded from the wiki index (for related-topics and grouping) |
| `relatedPages` | `WikiHelpPage[]` | `[]` | Pages in the same category as `currentPage`, excluding itself |
| `groupedPages` | `Map<string, WikiHelpPage[]>` | `new Map()` | `allPages` grouped by category, each group sorted by frontmatter `order` |
| `isLoading` | `boolean` | `false` | True while fetching a page; shows the loading spinner |
| `error` | `string \| null` | `null` | Error message rendered in an `alert alert-error` box |
| `showIndex` | `boolean` | `false` | Index view vs. document content view |
| `expandedCategories` | `Set<string>` | `new Set()` | Which index categories are expanded |
| `navigationHistory` | `string[]` | `[]` | Stack of previously visited page slugs for back navigation |

### Open-help-modal event listener contract

`window.addEventListener('open-help-modal', ...)` (registered in a `useEffect`, removed on cleanup):

```typescript
interface ModalEventData {
  context: string;
  documentTitle: string;
  timestamp: string;
}
```

Handler behavior:
1. `setContext(event.detail.context)` and `setIsOpen(true)` — always.
2. If `context` is non-empty and not `'help_page'`: fetch the context page (`loadContextPage`) and prefetch the full index (`loadAllPages`).
3. Otherwise (empty or `help_page`): show the index view directly (`setShowIndex(true)`) and load the index.

The effect depends on `loadAllPages` and `loadContextPage`, so the listener is re-registered when those callbacks change identity (i.e., when `allPages` changes).

## Wiki API Calls

All fetches are relative (`fetch('/api/v1/wiki...')`) and hit the frontend dev-server/proxy. No request caching is implemented — every open, page change, and back-navigation re-fetches from the API.

| Endpoint | Method | When | Response shape used |
|---|---|---|---|
| `/api/v1/wiki` | GET | `loadAllPages()` — on every open-help-modal event | JSON with a `tree` array; finds the `help` directory node (`name === 'help' && type === 'directory'`) and reads its `children` |
| `/api/v1/wiki/${c.path}` | GET | Per-file fetch for each `type === 'file'` child under the `help` directory (path is dynamic, e.g. `/api/v1/wiki/help/settings.md`) | JSON with `path`, `title`, `content`, `frontmatter` (`category`, `subtopic`, `order`, `summary`). Failed fetches are silently skipped |
| `/api/v1/wiki/help?context=${slug}` | GET | `handleOpenPage(slug)` (index/related-topic click), `loadContextPage(context)` (on modal open), `handleGoBack()` (back navigation) | JSON with a `pages` array; uses `pages[0]` as the page. **Query param, not path param** — a route collision fix moved the slug into `?context=` |

Failure handling: `loadAllPages` and `loadContextPage` catch errors and log via `frontendLoggingService.error`; `handleOpenPage` surfaces the error into `error` state (rendered as an alert) and always clears `isLoading` in `finally`. `loadContextPage` falls back to `setShowIndex(true)` (expanding the context's category) on any failure or empty result.

## UI Structure (right drawer)

- **Root**: `fixed inset-0 z-50 flex justify-end` — overlay pinned to the right edge.
- **Backdrop**: `bg-black/50 backdrop-blur-sm`, `onClick={handleClose}`, `aria-hidden`.
- **Drawer panel**: `role="dialog" aria-modal="true" aria-labelledby="help-modal-title"`, `w-[560px] max-w-[90vw] h-full`, flex column with header / scrollable body / footer.
- **Header**: Back button (chevron, shown when `navigationHistory.length > 0`), `HelpCircle` or `Book` icon, title `<h2 id="help-modal-title">` (`Help Index` in index view), plus "All Topics" (`Book` + text, hidden below `sm`) and Close (`X`) buttons.
- **Body** (scrollable `flex-1 overflow-y-auto p-6`) — one of three states:
  - `isLoading` → spinner (`loading loading-spinner loading-lg`) + "Loading help content..."
  - `error` → `alert alert-error` with the message
  - `showIndex` → index view: categories sorted alphabetically, each a card with a toggle button (`ChevronDown`/`ChevronRight`), doc-count badge, and a "Current Page" accent badge when the category matches the active context; expanded groups list page buttons with title + 1-line summary; empty state "No help topics available."
  - else → document view: breadcrumb nav (`Help` > `category` > `subtopic` > `title`), markdown body, optional "Related Topics" card, and a "View All Help Topics" outline button.
- **Footer**: `Close` primary button.

### Markdown rendering

- `ReactMarkdown` from `react-markdown` renders the content (no `remark-gfm` — the component is not passed any remark/rehype plugins).
- Wikilinks are preprocessed by `processWikilinks()`: `[[foo/bar-baz]]` → `[Bar Baz](/wiki/foo/bar-baz)` (title = last path segment, dashes → spaces, Title Cased), matching wiki-viewer link behavior. Links point at `/wiki/<name>` client routes.
- Custom `code` component: fenced blocks with `language-mermaid` render via `MermaidDiagram` (calls `mermaid.render` with a random id, injects the resulting SVG via `dangerouslySetInnerHTML`; shows a spinner while rendering and a warning alert with the error message on failure). Other code renders as styled `<pre><code>` (block) or inline `<code>`.
- Content wrapper classes: `prose prose-sm dark:prose-invert prose-a:text-primary ...` (Tailwind Typography + DaisyUI theme).

### Navigation

- **Open**: `open-help-modal` event (above).
- **Page change**: index/related-topic buttons call `handleOpenPage(slug)` — pushes the current slug onto `navigationHistory` (only if a page is already open), fetches the page, recomputes `relatedPages`.
- **Back**: header chevron button or keyboard (`Backspace`, or `Alt+Left`, both only when history is non-empty and not on the index) → `handleGoBack()` pops the history stack and fetches the previous slug.
- **Index**: "All Topics" header button, breadcrumb "Help" click, or "View All Help Topics" button → `setShowIndex(true)`.
- **Close**: backdrop click, `Escape` key, header `X`, or footer `Close` → `handleClose()` resets open state, index flag, history, content, and current page, then calls `onClose?.()`. While open, `document.body.style.overflow` is set to `hidden` (restored on close/unmount).

## Related Components

- `frontend/src/components/help/HelpButton.tsx` — the event dispatcher; context-aware help button that fires `open-help-modal` with `{ context, documentTitle: 'Help', timestamp }` (default context `'help_page'`).
- `frontend/src/components/help/__tests__/HelpButton.test.tsx` — test asserting the button dispatches `open-help-modal` on click.
- Backend wiki API serving `/api/v1/wiki`, `/api/v1/wiki/<path>`, and `/api/v1/wiki/help?context=...` (markdown pages under `wiki/help/`).
