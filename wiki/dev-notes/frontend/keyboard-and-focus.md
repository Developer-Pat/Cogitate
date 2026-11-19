---
title: Keyboard and Focus
type: dev-note
category: frontend
subtopic: navigation
order: 3
confidence: high
updated: 2026-09-19
tags: [domain/dev-notes, domain/frontend, domain/navigation]
---

# Keyboard and Focus

Three things are decided in one place each, and they are the same subject: **what
the app's keys are, where a destination lands, and who holds the caret afterwards.**
`wiki/dev-notes/frontend/command-box.md` is the box itself — its verbs, its lists,
its combobox keys. This note is the layer underneath: the shell's keys, the two
axes a destination can land on, and the focus contract that decides who wins.

## The app's global keys live on ONE listener

`NavSearchHotkey` (mounted by the shell, never unmounted) owns every app-wide
chord. No mount arms a key of its own — `hotkey: false` in both mounts — because
a listener inside a mount dies with it (the sidebar's box is not even rendered
while the rail is collapsed) and two armed mounts once made one keystroke open two
boxes.

| key | what it does |
|---|---|
| `Cmd/Ctrl+K` | open the Search box and put the caret in it |
| `Cmd/Ctrl+F` | the same action — the find bar means nothing in an app with its own search |
| `Cmd/Ctrl+`` ` | toggle the navigation panel |

Local keys (the box's own) are in the command-box note: Down/Up/Home/End walk the
rows, Enter accepts one, `Alt+Down` opens the list, Escape closes the list first
and the box second, Tab leaves as one stop.

### The co-existence rule

**A key we want must be one the browser does nothing with.** The rule is the
user's, and it is not a preference: *"don't claim the Ctrl+B from Firefox. we want
to co-exist. we'll find something else."* Claiming means a chord the browser owns
and the page cancels — workable (`Ctrl+F` is exactly that, and its `preventDefault`
is what suppresses the find bar) but a fight, and one that a browser can win later.

So `Ctrl+`` was chosen by MEASUREMENT. A census fires each candidate chord as a
trusted key event at a page that reports every keydown and every resize /
visibility change, and reads whether the browser acted:

| chord | Firefox 145 | Chromium 1228 |
|---|---|---|
| **Ctrl+`** · Ctrl+\\ · Ctrl+Shift+\\ · Alt+\\ · Ctrl+Shift+` · Ctrl+. | silent | silent |
| Ctrl+B *(control)* | bookmarks sidebar (content 1200 -> 958px) | nothing |
| Ctrl+Shift+B *(control)* | bookmarks toolbar (content -> 684px) | bookmarks bar (613 -> 579px) |
| Alt+1 *(control)* | tab switch (page hidden) | nothing |
| Ctrl+T *(control)* | new tab | new tab |

Every candidate is silent in both engines — the page receives the chord and the
browser ignores it — and every control registered, so the apparatus could detect a
claim. **Two facts came out of it beyond the key**: Firefox owns `Ctrl+B` (the
bookmarks sidebar), and the study's older "panels take Alt-number" idea was never
available to us at all — Firefox binds `Alt+1..8` to tab switching.

Re-run it after a browser update: the census is a page that logs its own keydowns
plus a tiny reporter, driven by trusted key events on a private X display — no
window on the desktop. (As apparatus it is one throwaway page or the harness's own
browser: the point is that the BROWSER's reaction is what is measured, never the
page's opinion of the chord.)

## Where a destination lands: the two axes

Two verb families, and the only thing that separates them is where they land:

- **`nav` / `goto`** — the CURRENT page moves, in place.
- **`open` / `show`** — a new TAB, and the current page is left alone.

`landingFor(verb)` is the one place a verb's axis is decided. The axis travels
into `resolveTarget` (it is what breaks a name that is both a page and a tab —
`sessions`, `messages`) and rides back out on `NavTarget.landing`, where
`openTarget` is the one place that acts.

### A LIST ROW IS A `nav`

The rows in the Search box (results, a tie's candidates, the Frequent shortcuts)
carry a bare PATH, and that is all. They used to be rebuilt as `kind: 'route'`
with no landing — and `openTarget`'s default is *no landing = tab* — so **every row
took a tab while every verb that produced it moved the page.** The reported defect
was exactly that: *"selecting from the list opens a new tab as opposed to
navigating the current page."*

- `targetForPath(to, label?)` answers what a path IS, from the same tables the
  resolver uses: a path that is a TAB APP and has no page route of its own
  (`/wiki`, whose route is a wildcard) is a tab; everything else is a page.
- `accept(option, askTab)` sets the landing: **a page lands in place**, a tab app
  lands in its tab.
- **`Ctrl/Cmd+Enter`** — and a ctrl/⌘-click on the row — asks for a TAB, the way
  the `open` verb does. The list is the `nav` surface; this is the escape hatch
  that keeps the other axis reachable from it.

`openTarget`'s **default stays a tab**, deliberately: Exa's `OPEN:` marker is a
caller with no landing, and it keeps the behaviour it has always had.

## Who holds the caret

`services/focusContract.ts` is the one place the question is answered, and it has
two claimants and one rule.

### The declaration (a page yields the caret)

A page built around one field marks it `data-autofocus`. Anything about to take
the caret asks first: `declaredPrimaryInput()`. No declaration means the caret is
free.

**A declaration is a YIELD — somebody has to act on it.** `claimDeclaredPrimaryInput()`
is the page's own half: the page focuses its field on mount. That is not
bookkeeping — **routes are lazy**, so on a cold load the page's chunk resolves
AFTER the shell's arrival effect has run, which meant the box claimed the caret
with no declaration in the document to yield to, and nothing ever took it back.
Measured: a cold load of the Message Center left the caret in the box while its
search field sat there declared and empty. Pages that declare today: Message
Center, Workflow Kinds, Agent Templates.

### The handoff (a navigation the reader asked for)

The user: *"it leaves us stuck in the nav panel either way ... we want to jump to
the page we just opened / navigated to."* So a requested navigation announces
itself and the arrival answers it:

- the surface that navigates calls **`requestPageFocus()`** before it acts;
- the shell calls **`claimPageFocus()`** on every arrival (mount and route change)
  and moves the caret to the destination — the declared field if there is one,
  else **`<main>`**, which carries `tabindex="-1"` for exactly that reason (never a
  Tab stop);
- it **yields** if the caret is already on the page, because a page's own field
  effect runs first (children before parents, same commit);
- the box **peeks** (`pageFocusRequested()`) and stands down, so it cannot win the
  race — which is what it used to do every time.

**The token, not a call, because a NEW TAB cannot be reached from the opener**
(browser security). It rides `localStorage` under `cogitate-focus-handoff` with a
10-second shelf life, single-use: written before the navigation, consumed by the
arrival, dropped if stale. The shape is the house's own — see
`services/domains/providers/swapHandoff.ts`.

**A COLD arrival is not a request.** A typed URL, a bookmark or a reload leaves no
token, so the box keeps the caret exactly as it always did — the ruling behind the
box's own "caret on arrival" behaviour still stands for a load nobody asked for.

### The preference that narrowed

`appearance.keepCommandBoxOpen` (Settings > Appearance) used to mean "hand the
input back after a navigation". It now decides only what it can honestly decide:
on a **TAB** landing — the destination is a window of its own and this document is
untouched — a mount that stays open keeps its input ready for the next command. An
**in-place** navigation hands the caret to the page for every mount; no preference
overrules the reported defect. Nothing in the hook ever closed a box on a
navigation, and that is unchanged.

## One window per destination

The user: *"we don't need or want two windows showing logs. If logs is open we just
switch to it."* Two properties, both in `services/crossTab/navigationService.ts`:

1. **THE NAME.** Every destination is opened as `cog-<path>` (`windowNameFor`), so
   a second request reaches the window that already has it. `_blank` — what the tab
   apps used — stacks a fresh duplicate every time; measured: two "Message Center"
   clicks, two `/messages` tabs.
2. **NO RELOAD WHEN SWITCHING.** `window.open(url, name)` on an existing window
   focuses it **and re-navigates it**: measured, a value set on that window did not
   survive the second request. Harmless for Logs; destructive for a tab holding
   state. So `openReusing(path)` asks for the window with NO url —
   `window.open('', name)` returns the existing context untouched — and only loads
   the destination into a window that came back blank (the one the same call just
   created because none had the name). Measured: no new tab, no reload.

**Agent Chat is exempt**, on the user's call: *"a user may have more than one
conversation going at a time."* It keeps opening its own tab. One tab PER
CONVERSATION needs the conversation's identity in the window name and a name that
survives a reload — its own arc, still open.

## What is deliberately NOT here

- **No accelerator service.** Three keys ride one shell listener; a router earns
  its build when a fourth surface wants a key (the right-side panel toggle is the
  likely one). The study's §2 stays a study.
- **No key table generated into the UI.** The keys are documented here and in Help.
- **No chat-window identity**, no session-scoped window names.
- **No app-wide tab-order pass** — `data-autofocus` is an opt-in, not a program.

## Pitfalls worth remembering

- **Lazy routes break any "is there a declaration?" check made too early.** If a
  page's field must own the caret, the PAGE takes it, on its own mount.
- **Effect order is the mechanism**: children before parents in one commit. Both
  the page's claim and the box's peek depend on it.
- **A named window is not a registry.** Nothing can ask "is that window open?" —
  only the browser's answer to `window.open('', name)` can, and it hands back a
  window either way (blank when it just made one).
- **A key chosen for co-existence must be re-measured after a browser update.** The
  census exists for that, and `about:keyboard` (Firefox 147+) can rebind a
  built-in if one ever collides.
