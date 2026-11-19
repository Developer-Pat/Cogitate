---
title: The Command Box
type: dev-note
category: frontend
subtopic: navigation
order: 2
confidence: high
updated: 2026-09-19
tags: [domain/dev-notes, domain/frontend, domain/navigation]
---

# The Command Box

The command box has **two surfaces**, and they share almost everything. Both
mount the same hook (`frontend/src/components/features/agentInteraction/useCommandBox.ts`)
and the same panel (`CommandBoxPanel.tsx`), and both read the same verb table.
The ONLY behavioural difference between them is one per-mount option,
**`exaFallthrough`** (default `false`): the nav sidebar passes false, the header
flyout passes true. That is the whole split. Two components with separate logic
is the wrong picture.

## The two surfaces

| surface | component | in the UI | makes a model call | mounted |
|---|---|---|---|---|
| Nav sidebar | `NavSearchSection` | **Search**, button **Go** | no | once, in the app shell |
| Header flyout | `ExaPromptFlyout` | **Exa**, button **Send** | yes, over the bridge | per page |

**The nav sidebar's box is a NAVIGATOR.** It makes no model call. Input that is
not a command gets a LOCAL, instant, one-line answer: the nearest verb, the
not-found answer with its candidates, or `Unknown command — help lists them.`
`exa <question>` opens the Exa CHAT TAB — the chat owns the call, its own Stop
and its own session, which is why a navigator mount needs no stop button
anywhere.

- Opened with **Ctrl+K** or **Ctrl+F** (Cmd on macOS for either — the shell's
  `NavSearchHotkey` carries both on its one listener, and both `preventDefault`:
  Ctrl+K would otherwise be the address bar's search, Ctrl+F the browser's find
  bar).
- Its open state persists across page loads and tabs: it is
  `navSearchOpen` on `uiStore`, persisted to `localStorage` (not
  `sessionStorage`), so the box comes back the way it was left.
- It is mounted ONCE, by the app shell (`frontend/src/App.tsx`), in the nav
  column — and only while the sidebar is expanded.

**The header flyout keeps the full Exa path.** An input that is not a command
still reaches Exa over the bridge (`/api/v1/external-agent/ws`), exactly as it
always did: that mount has the room for a short answer and for stopping a run,
and it is where a dispatch is typed. It is mounted per page.

The visible difference follows the same line, and it lives in the panel's
`variant` + `COPY`: the sidebar reads "Search"/"Go" and draws no "Full page"
control and no streamed-answer area; the flyout keeps "Ask Exa"/"Send", "Full
page" and the answer. The input's placeholder (`nav logs · nav list · exa
<question>`) is shared.

## Navigation

Every command is answered locally by
`frontend/src/services/appNavigation.ts` — `parseCommand` -> `resolveTarget` ->
`openTarget`. A command is deterministic, costs nothing, and cannot
hallucinate; that is the whole reason the verbs exist.

### The two axes

Two verb families decide WHERE a destination lands, and that is the only thing
that separates them:

- `nav` / `goto` — move the **current** page, in place.
- `open` / `show` — open a **new tab** and switch to it.

`landingFor(verb)` is the ONE place a verb's axis is decided. The axis travels
INTO `resolveTarget` (it is what breaks a name that is both a page and a tab)
and rides back out on the target (`NavTarget.landing`), where `openTarget` acts
on it. A caller that passes no verb keeps the tab — the default — which is what
Exa's own `OPEN:` marker gets.

The in-place landing is react-router's own `navigate()`, which the hook already
holds, so it needed no new plumbing. The backend has a separate in-place
channel — the bridge (`frontend/src/services/uiStateBridge.ts`, consumed by
`useUIStateBridge`) receives a `navigation_request` over its ws and calls
`navigate(route, { replace })`, which is how the backend asks the frontend to
move.

### A list ROW is a `nav`

The rows in the box (results, a tie's candidates, the Frequent shortcuts) carry a
bare PATH, and that was the whole of it: they were rebuilt as `kind: 'route'` with
no landing, and `openTarget`'s default is *no landing = tab* — so **every row took
a tab while every verb that produced it moved the page.** The user hit it exactly
that way: *"selecting from the list opens a new tab as opposed to navigating the
current page."*

- `targetForPath(to, label?)` answers what a path IS, from the same tables the
  resolver uses: a path that is a TAB APP with no page route of its own (`/wiki`,
  a wildcard route, so it is never in the page map) is a tab; everything else is a
  page.
- `accept(option, askTab)` sets the landing from that: **a page lands in place**,
  a tab app lands in its tab.
- **`Ctrl/⌘+Enter`** — and a ctrl/⌘-click on the row — asks for a TAB, the way the
  `open` verb does. The list is the `nav` surface; this is the escape hatch that
  keeps the other axis reachable from it.
- `openTarget`'s **default stays a tab**, deliberately: Exa's `OPEN:` marker is a
  caller with no landing and keeps the behaviour it always had.

**The caret goes with the reader.** A navigation the reader asked for hands them
the destination — the page's declared field, else the `<main>` region — and it is
the shell that answers it (`services/focusContract`; see
[[dev-notes/frontend/keyboard-and-focus|Keyboard and Focus]]). The box stands down
rather than claiming the caret back, and the box's own mount stays open.

### The command keys

Eleven canonical verbs. Aliases resolve to their canonical verb, so `help` lists
eleven entries and a new alias never needs a new help line.

| verb | aliases | what it does | lands |
|---|---|---|---|
| `nav` | `goto` | go to a page — `nav logs`, `nav the settings page` | current page |
| `open` | `show` | open a page — `open logs` | new tab |
| `config` | `conf`, `configure` | the page that holds a setting — `config theme`, `config provider` | current page |
| `list` | — | list what matches and open NOTHING — `list workflow`; bare `list` shows every destination | nowhere |
| `help` | — | the command list; `help nav` describes one verb | nowhere |
| `back` | — | the previous page in THIS tab | current page |
| `exa` | — | the system agent — `exa is search broken?` skips the grammar entirely; bare, opens the Exa page | the mount decides |
| `info` | — | the best wiki page — `info workflows` | current page |
| `dev` | — | the best dev note — `dev architecture` | current page |
| `atlas` | — | the best atlas page — `atlas settings page` | current page |
| `search` | `find` | the WIKI's own search across every namespace, listed and NOT opened — `search triggers`; `info` opens the best hit instead | nowhere |

**`search` was `list`'s alias until 2026-09-19** (and that is why the sidebar
box, named "Search", did not search). It is the wiki's own search now — no
prefix, so every namespace is searched — and `find` is the alias it gained in
the move. The two verbs are told apart by what they DO with the hits, not by
what they search: `info` opens the single best page, `search` returns all of them
as candidates and opens none, and `list` is the app map plus the wiki, grouped.
`parseCommand('search triggers')` therefore resolves to the `search` verb, not to
`list`.

`config` rides the declared alias table, so `config theme` reaches
`/settings?tab=appearance` — the Appearance *tab*, not merely the Settings page.
Its subjects are the ones the resolver already knew plus `models` and `keys`;
the rest were measured against the live resolver, not invented.

### The parse contract

| input | outcome |
|---|---|
| a verb + a **resolved** target | acts. No model call. |
| a verb + an **unresolved** target | stays local: names what it did not find and offers the close matches ("I do not know a page called ...") |
| a **near-miss on a verb** — one edit away, and no rival verb at the same distance | stays local: offers the correction (``Did you mean `nav`?``) |
| **anything else** | the MOUNT decides: the sidebar answers locally in one line (`Unknown command — help lists them.`), the flyout falls through to Exa |

The two local answers are `noCommandAnswer`'s: a near-miss on a verb OFFSETS it,
and anything else is told plainly that it is not a command and pointed at
`help`.

`parseCommand` returning null means only "not a verb" — it conflates a QUESTION
with a TYPO of a verb, and only the typo wastes a model turn on something the
user meant locally. `nearVerb` applies the near-miss rule one level up, and it
scans the aliases as well as the canonical verbs: "gotto" is one edit from the
alias `goto`, which a canonical-only scan misses entirely.

The scan moved with `search` (2026-09-19): "serch" is one edit from `search` and
offers the same word it always did, but that word now resolves to the SEARCH verb
rather than to `list` — the offer was right and its destination changed with the
verb. "fnd" is one edit from the alias `find`, which a canonical-only scan would
miss exactly as it misses `gotto`.

Two SPELLINGS of one verb are not ambiguity: "confg" is one edit from both
`conf` and `config` — the same destination twice. Rivals are different VERBS at
the same distance, and canonical verbs are scanned first, so the suggestion
prefers the canonical spelling.

The same tolerance covers TARGETS. A near-miss RESOLVES and the correction is
stated out loud (`Opened Workflows (read as "Workflows")`) — a silent fix would
hide the day the guess is wrong. Damerau-Levenshtein (a transposition costs 1)
is used, and a correction is applied ONLY when one candidate is strictly nearer
than the runner-up; equal distances return candidates, because that is where
picking *is* guessing.

### A name that is both a page and a tab

A term can name a page AND an app tab — `sessions` is the route `/sessions` AND
the Sessions tab, and `messages` is the same shape — and the names are
identical, so only the axis can tell them apart. **The verb decides:**
`nav sessions` takes the PAGE in place, `open sessions` takes the TAB. See
`dualPage`; the declared alias `message list` names the losing side explicitly,
because the page's own title ("Message Center") is the tab's word too.

### help, back and config

- `help` is generated from the verb table (`COMMAND_VERBS`), so a verb with no
  description fails loudly at `verbHelp` instead of going quietly
  undocumented. `help <verb>` answers with that verb's line and its aliases.
- `back` walks the **TAB's own history** (`window.history.state.idx`), not the
  box's shortcut list — that list is a FREQUENCY list, most-used first, so it
  cannot answer "where was I just now". At index 0 it refuses honestly ("this
  tab started here") rather than calling `navigate(-1)` and walking out of the
  app.
- `config <subject>` is a shortcut to the page that holds a setting.

**A typed sentence that BEGINS with a verb word is a command:** "open the
themes page" is the `open` verb, not a question. `exa <question>` is the escape
hatch.

## Where the map comes from

- The page list is **generated** from `getNavigationRoutes()`
  (`frontend/src/config/routes.ts`), so a page is reachable the moment it is
  routed and nobody hand-keeps a list.
- The ONE hand-kept table is `ALIASES`, and it is declared as such. It exists
  because the Settings tabs are `useState`, invisible to the route table. If a
  tab becomes a route, delete its alias.
- The wiki verbs (`info` / `dev` / `atlas`) ride the wiki's own search endpoint.
  A `prefix` filter is applied **before** scoring: the endpoint returns the
  global top 10, so ten unrelated pages can crowd a namespace out and the verb
  would report "nothing found" while the note exists.
- A target that is **not** in the map fails loudly with the nearest candidates.
  Opening a plausible-looking 404 because it seemed right is worse than saying
  "I don't know that one".
- `list` and the other listing words (`list`, `lists`, `pages`, `all`,
  `everything`) are checked BEFORE `resolveTarget`, because `list` is a word
  inside the key "session list": the fuzzy stage would otherwise match it at
  distance 0 and open Sessions with full confidence. Asking for the map is
  answered by the map.

## The panel

One panel, two shells. `variant` is `'flyout'` (the default) or `'sidebar'`,
and it carries the whole visible difference — `COPY` and which controls are
drawn. The content is identical.

- `flyout`: the popover anchored under its trigger, `w-[440px]`, with the
  answer area and "Full page".
- `sidebar`: fills the column it is given and caps its own height (`max-h-64`),
  because the nav sidebar is one scroll column shared with the nav list — an
  unbounded panel would push the list off-screen. Its input row is `sticky
  bottom-0`: the panel puts the input LAST, and in a capped column it is the
  first thing to go below the fold the moment a result list or a long answer
  arrives (measured at 256px with a `help` answer: 75px past the bottom edge).

## The keyboard — the box is a COMBOBOX

The reported defect (2026-09-19): *a keyboard user presses ArrowDown and nothing
happens.* The box reached its rows with **Tab** — one stop per result — so the
natural key for a list did nothing, and assistive tech heard a run of links
beside a text field rather than one control with an active option. The pattern
that fixes it is the WAI-ARIA combobox
(`local/studies/keyboard-accelerators.md` §3):

- **DOM focus never leaves the input.** The list carries a *virtual* focus: the
  active row is a highlight, named by the input's `aria-activedescendant`
  (`cmdbx-option-N`), and the input is a `role="combobox"` with `aria-expanded`
  and `aria-controls`. There is no second thing to jump to, so nothing has to
  decide which key jumps.
- **The rows are ONE model** — `useCommandBox`'s `options`: the candidate
  results, a tie's candidates and the Frequent shortcuts, in draw order. The
  panel draws them (`role="listbox"` per group, `role="option"` per row) and the
  keys move over the SAME array, so the two cannot disagree about "the next row".
- **There is ONE popup, and it is that whole array** (2026-09-19). `listOpen`
  and `aria-expanded` are `options.length > 0` — so *any* drawn list counts, the
  Frequent list included — and the panel gates each block on its own rows, so a
  heading or a Clear button cannot outlive the rows under it.
- **No row is a Tab stop** (`tabIndex={-1}`). Reaching a row is ArrowDown; Tab
  leaves the box — one stop, not one per result.
- **The active row wears the house's selected-row tint** (`bg-primary/10` +
  `text-primary`), never a dimmer one: gray-dim means DISABLED in this app
  (`design/control-system.md`, the text roles), so the active row reads as MORE
  present, not less.

| key | what it does |
|---|---|
| type | clears the active row (see below), so Enter still runs the command |
| Down | next row; with nothing active, the list opens at its FIRST row |
| Up | previous row; with nothing active, the list opens at its LAST row; from the FIRST row, back to editing the input |
| Alt+Down | open the list without moving in it (nothing active -> its first row) |
| Home / End | first / last row — **while a list is up**; with none they stay the caret keys |
| Enter | accept the ACTIVE ROW (opens it — **in place**, since a row is a destination); with no row active, run the typed command |
| **Ctrl/⌘+Enter** | accept the active row **in a NEW TAB** — the `open` axis asked for from the list (ctrl/⌘-click does the same) |
| Escape | close the LIST first (putting the popup away, Frequent included); the box itself goes on the second press |
| Tab | leave the box (closes the list; the typed value is what was accepted) |

**The active row is scrolled into view as it moves** (2026-09-19 — the reported
defect: *"the arrows DO scroll through the list one item at a time starting at
the bottom which is off the screen"*). This is part of the pattern, and it was
the missing piece that made Up look broken. Moving the active row moves a
VIRTUAL focus: no element is focused, so the browser scrolls nothing — and the
panel's own scrolling under the arrow keys was exactly the behaviour the
combobox consumed without replacing. Up opens the list at its LAST row, and with
nothing scrolling to it that row sat below the visible area.

The panel does the scrolling (`CommandBoxPanel`, on every change of the active
row) with `scrollIntoView({ block: 'nearest' })`: the minimum scroll that
reveals the row, so nothing else — the panel's own position or the page — moves.
`scrollIntoView` walks the scrollable ANCESTORS, so one rule covers every list
the panel draws and whichever box is short of the row (the list's own capped box
or the panel's shell). It looks the row up inside the panel's own shell rather
than the document: the option ids are index-based and both mounts can draw a
list at once.

**The sidebar's shell reserves the pinned input row's height** (`scroll-pb-14`,
the same fix). The input row is `sticky bottom-0`, so the bottom ~49px of that
scrollport is painted over by it, and `scrollIntoView` — which knows the box but
not what is drawn on top of it — stopped with the last row underneath the input.
Measured before the fix: `End` and Up-from-closed both put the last Frequent row
at 336–360px in a shell whose input row began at 312px, i.e. scrolled to and
still invisible.

**Closing the popup and opening it again.** The Frequent list has no state of its
own to clear — it is what the box shows when nothing is typed — so Escape's
first press sets `listDismissed`, which empties the drawn set: no list, no
heading, no Clear button, `aria-expanded=false`, the caret untouched. Up, Down
and Alt+Down put it back (`moveActive`/`openList` clear the flag), a command
clears it (`ask` is the funnel every submitted command goes through), and so does
reopening the box. That flag is what gives a keyboard user a way IN: before it,
Up with nothing active did nothing at all, End was refused (no list was "up"),
and the only way into Frequent was one Down per row.

**Accept has two shapes, and both already existed.** The panel's row click and
its tie-candidate click are now one `accept` in the hook, keyed by the row's
group: a result or shortcut row records the destination and clears the list; a
tie's candidate opens the page the resolver had already validated, without
recording a shortcut for a guess.

**A new list starts on its first row — and TYPING CLEARS the active row.** This
is the one place the convention was adapted rather than copied. The study's
*type → the active option resets to the first* assumes a list FILTERED by what is
typed; these lists are produced by a COMMAND, so a row activated by a keystroke
would be a row the reader never chose — Enter after typing `nav logs` would open
whatever sat at the top of Frequent instead of going to Logs. A command whose
answer IS a list does activate its first row, which is the same reset kept where
it is true.

**The APG's whole key set is wired now.** `Alt+Down` was left out at first — "there
is no closed list to open on demand, the candidates arrive with a command" — and
that reasoning only held while Frequent was not a popup: it is the LIST, and the
list can be closed. `Ctrl+F` joined `Ctrl+K` on the shell's ONE listener
(2026-09-19): the study's §1 platform test settles the key — the browser's find
bar means nothing in an app with its own search — so it runs the SAME
`openNavSearch()` action rather than growing a listener of its own, and its
`preventDefault` is what keeps the find bar out of the way. The accelerator
SERVICE the rest of the study describes still does not exist; this is one key on
the listener that already was there.

## The shortcuts

`frontend/src/services/navHistory.ts` — `localStorage`, aggregated BY
destination so a repeat raises a count instead of duplicating a row; most-used
first with recency as the tie-break, bounded (a shortcut list, not a log). It is
a convenience, never a source of truth: a corrupt store degrades to "no
history". One effect loads it whenever the box opens, however it was opened, so
a click shows the list rather than an empty panel.

## Mounting

- **The sidebar's box: one shell mount.** `App.tsx` renders `NavSearchSection`
  in the nav column, and only while the sidebar is expanded
  (`{!sidebarCollapsed && <NavSearchSection />}`). The section is `sticky
  bottom-0` in that column: the nav list is long enough to scroll, and a section
  resting at the end of the flow would sit below the fold. The panel's close
  control means "collapse the section" — the thread is still there when it is
  unrolled again.
- **The flyout: per page.** `PageBanner` carries it on the title row's right
  side; the pages with their own right-hand button group seat it themselves
  (Logs, Message Center, Agent Interaction) and the banner opts out via
  `hideCommand` — in a `justify-between` header row a banner-seated pill lands
  at the page's left edge and its leftward-opening panel is clipped.
- **The app-wide key is ONE listener, in the shell**
  (`NavSearchHotkey`, rendered by `App.tsx`). It cannot live inside a mount: the
  sidebar's section is not even rendered while the rail is collapsed, so a
  listener there would be dead in the very case the key exists to serve — and
  with two mounts armed it was a real bug (Ctrl+K opened the flyout AND pulled
  focus into the sidebar box). No mount sets `hotkey: true`; the hook keeps the
  capability for a surface with no shell around it. The shell writes one store
  action (`navSearchFocusPending`), and the section — which owns the input's ref
  — answers the focus signal.
- **The caret on arrival.** The sidebar's box can be open on a fresh page load,
  and a new tab is a fresh load the opener cannot focus — so that mount puts the
  caret in the box, unless the page declares a primary input of its own
  (`frontend/src/services/focusContract.ts`, the `data-autofocus` contract) **or a
  navigation the reader asked for is waiting to be honoured** — in which case the
  arrival is the page's, and the shell's `claimPageFocus()` takes the caret there
  (that page's declared field, else `<main>`). The box PEEKS at the request; it
  never consumes it. And a declaring page takes its own field on mount
  (`claimDeclaredPrimaryInput()`), because **lazy routes mount after the box's
  arrival effect has already run** — a cold load of the Message Center used to
  leave the caret in the box with its search field declared and empty. An explicit
  Ctrl+K or Ctrl+F is not governed by any of this: a keystroke that asks for the
  box is intent, not an arrival.

WARNING — **the import cycle this exposed.** `PageBanner` importing the flyout
closes a cycle (`config/routes -> pages -> PageBanner -> the widget ->
services/appNavigation -> config/routes`), and the navigation directive handed
to Exa was a MODULE-SCOPE template literal — so it evaluated before `routes`
existed and every mount threw "Cannot access ... before initialization".
Type-checking cannot see that class of bug; the test suite caught it. The
directive is now built on first use.

## The tests that carry the weight

- **The round-trip invariant**: every route in the table resolves to itself, so
  the generated map cannot silently drift.
- **A command opens no socket** — the determinism promise, asserted rather than
  assumed. The sidebar's local answers assert the same, and
  `exa <question>` in that mount reaches no socket either.
- **The two axes**: `open`/`show` take a tab where `nav`/`goto` move the page,
  and `nav sessions` / `open sessions` follow the verb.
- **The `OPEN:` marker never reaches the reader** (it is machinery).
- **The shortcut list loads on a click**, not just on the hotkey.
- **The sidebar's box draws no Exa controls** — no "Full page", no answer area,
  and its button says "Go".
- **The combobox keys** (`NavSearchSection.test.tsx`, "the box is a combobox"):
  Down moves the ACTIVE ROW while the input keeps the DOM focus, Enter accepts
  the active row, Enter with nothing active still runs the typed command, Escape
  closes the list before the box, and no row is a tab stop. jsdom cannot move
  focus on Tab, so the file pins what the markup actually promises there; the
  behaviour itself was checked by hand in the running app.
- **The active row is kept on screen** (same file, 2026-09-19): jsdom implements
  no `scrollIntoView` at all, so the test stubs it and pins that the call lands
  on the row the virtual focus moved to, that it asks for `block: 'nearest'`
  (the half that keeps the page still), that it follows the selection from one
  keypress to the next, and that a box with no active row scrolls nothing. The
  overflowing-panel half was measured in the running app: a Down-walk over a
  43-row listing plus Frequent kept the active row fully visible at every step,
  and Up from a closed list (the reported case) opened at the last row with the
  row on screen.
- **The landing and the caret** (2026-09-19, the same file): a row lands in the page the reader is ON
  (`window.open` is NOT called, the router moved), `Ctrl/⌘+Enter` takes the tab instead, and the caret
  ends up on the page — the shell's half pinned as COMPOSITION (`ShellHandoff`, the two lines of
  `Layout` this needs). The pieces underneath have their own files:
  `focusContract.test.ts` covers the token's lifecycle (written, honoured once, dropped when stale,
  never honoured for a cold arrival, yielding to a page that already has the caret), and
  `navigationService.test.ts` the one-window rule (load a window that did not exist, SWITCH to one
  that did without reloading it, fall back when there is no handle, and Agent Chat's exemption).
- **The ONE popup, and the Frequent list as part of it** (same file, 2026-09-19):
  `aria-expanded` is true with Frequent alone on screen and End/Home jump its
  rows; Up with nothing active opens the list at its LAST row while the caret
  never leaves the input; Escape puts the popup away (heading and Clear button
  with it) and Down/Up bring it back, with the box taking its own two steps
  again; Alt+Down opens without stepping; and running the SAME listing twice
  after an Escape still draws it.

## Known gaps

- **The chat input's suggestion surfaces are not converted yet.** They have the
  same problem and take the same pattern; the study's open question (combobox or
  menu) is still open there.
- **The input keeps the caret while the popup is up, and that is the point** — so
  a reader who wants the rows GONE and the text back presses Escape (or Tab,
  which leaves the box and closes the list on the way out).

- **`exa <question>` does not carry the question yet.** In the sidebar's box the
  verb opens the Exa chat tab — which is a fresh page load the opener cannot
  write to — and nothing on the Exa page reads a question. Until that wiring
  lands, the typed words STAY IN THE INPUT (losing the text is worse than a
  refusal) and the outcome line says so.
- **A failed parse has no dedicated error UI** in the panel beyond the one-line
  outcome and its candidates.
- **`OPEN:` answers ride free text.** The directive handed to Exa is prose; no
  typed tool carries the page map as its schema enum yet. The frontend half is
  already source-agnostic: something produces a destination, `resolveTarget`
  validates it, `openTarget` navigates.
