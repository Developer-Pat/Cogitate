---
title: appNavigation
type: atlas-service
path: frontend/src/services/appNavigation.ts
confidence: high
updated: 2026-09-19
tags: [type/service, domain/navigation, status/active]
---

# appNavigation

**Path**: `frontend/src/services/appNavigation.ts`

ONE navigator for "take me there" requests. The page map is **generated** from
`config/routes.ts` (`getNavigationRoutes`), so a page is reachable the moment it
is routed and nobody hand-keeps a list. The single hand-kept table is `ALIASES`,
and it is declared as such: Settings' tabs are `useState`, invisible to the route
table — which is why "themes" needed an entry.

## Exports

| Export | What it does |
|---|---|
| `pageMap()` / `pageMapPrompt()` | the generated map, and its text form (what Exa is handed) |
| `resolveTarget(raw)` | path / title / alias -> a destination, or a LOUD failure with candidates |
| `targetForPath(to, label?)` | what a bare PATH is — a page, or a tab app with no page route of its own. The Search box's rows carry paths, and this is what tells them where to land |
| `openTarget(target, inPlaceNavigate?)` | the ONLY place a navigation happens |
| `parseCommand(input)` | the verbs: `nav` / `list` / `search` / `info` / `dev` / `atlas` |
| `resolveWikiCommand(cmd)` | `info` / `dev` / `atlas`: the best wiki hit, or candidates on a tie; `search` / `find`: EVERY hit across the whole wiki, nothing opened |
| `searchAll(terms)` | the `list` verb: PAGES + WIKI, grouped, **nothing opened** |
| `searchWiki(q, prefix?)` | the wiki's own search endpoint |
| `extractOpenRequest(reply)` | pulls the `OPEN: <path>` marker out of an Exa answer |
| `COMMAND_VERBS`, `OPEN_MARKER`, `OPEN_IN_NEW_TAB` | the vocabulary and the one switch |

## Rules the code enforces
- a target that is not in the map **fails loudly** — opening a plausible 404
  because it looked right is worse than saying so
- typos resolve only when one candidate is **strictly nearer** than the
  runner-up, and the correction is stated ("read as ..."), never silent
- ties break on the user's own evidence — a structural segment they named, the
  leftover noun in the title, a hub note — and otherwise return candidates
- navigation opens a **new tab** with ONE WINDOW NAME PER DESTINATION
  (`cog-<path>`), and a repeat request **switches to the tab that already has it
  rather than stacking a duplicate — without navigating it.** The switch asks for
  the window with no url (`openReusing`); `window.open(url, name)` on an existing
  window both focuses AND re-navigates it, which was measured and is destructive
  for a tab holding state. Agent Chat is exempt by design (see
  [[dev-notes/frontend/keyboard-and-focus|Keyboard and Focus]])
