---
title: Search
category: search
subtopic: Overview
order: 1
confidence: high
created: 2026-09-19
updated: 2026-09-19
tags: [domain/help]
---

# Search

The **Search** box sits in the navigation sidebar. It is a command box:
type where you want to go and it takes you there, instead of clicking
your way through the menu.

Nothing here calls a model. The map of pages lives in the app itself, so
the box answers instantly and its navigation commands work with the
backend down. `info`, `dev` and `atlas` search the wiki, which does need
the backend.

## Opening it

- **Ctrl+K** opens it from anywhere — the sidebar expands if it was
  collapsed, and the cursor lands in the box, ready to type.
- **Ctrl+F** does the same thing. It is the key most people reach for to
  search, and here it reaches *this* search rather than the browser's —
  so the browser's own find bar stays out of the way. It works while
  you are typing in another field too.
- **Ctrl+`** puts the navigation panel away and brings it back — one key,
  because the panel is a toggle. It is a key the browser does nothing
  with, so it takes nothing away from it.
- The **Search** toggle above the box shows it or hides it by hand.
- A command runs on **Enter**, or on the **Go** button — which stays
  disabled until you have typed something.
- **✕** puts the box away.
- It remembers: if the box was open when you left, it is open again the
  next time you load the app.

## What you can type

A command is a verb, then what it acts on.

| Command | What it does |
|---|---|
| `nav <page>` | go to a page in this tab |
| `open <page>` | open a page in a new tab |
| `config <subject>` | go to the page that holds a setting |
| `list <words>` | list what matches, and open nothing |
| `help` | the command list; `help nav` describes one command |
| `back` | the previous page in this tab |
| `exa <question>` | open the Exa chat tab |
| `info <topic>` | the best wiki page |
| `dev <topic>` | the best developer note |
| `atlas <topic>` | the best atlas page |
| `search <term>` | list every wiki page that matches, and open nothing |

Short forms work: `goto` is `nav`, `show` is `open`, `conf` and
`configure` are `config`, and `find` is `search`.

- **Phrases are fine.** `nav the logs page` lands the same as
  `nav logs` — not knowing the exact name is the reason to use the box.
- **Small typos are fine.** `nav worfklows` opens Workflows, and the box
  tells you it read it that way rather than correcting you silently.
- **Some pages answer to more than one word.** `nav logging` finds Logs
  and `nav tests` finds the Testing Dashboard. `config theme` reaches the
  Appearance tab of Settings, not just the Settings page.
- **`config` takes what you call a setting**, and finds where it lives —
  `config keys`, `config models`, `config notifications`.
- **`nav list` shows the map** — every destination the app has, as
  links — and so do `nav pages`, `nav all`, and a bare `list`. **Nothing
  opens until you click one.** `list triggers` lists the matching pages
  and wiki notes instead, grouped.
- **`search` is the wiki's own search.** `search triggers` — or
  `find triggers` — looks through the whole wiki, every part of it, and
  lists what it found. Nothing opens until you pick one. The verb next
  door is `info`: `info triggers` opens the single best page instead of
  listing the matches.
- **`help` teaches.** On its own it lists every command; `help nav`
  describes one.

## The two ways a page opens

- **`nav` / `goto` move the page you are on.** The page under you
  changes and your tab stays where it is — which is what makes `back`
  mean something.
- **`open` / `show` open a new tab** and switch to the new one, leaving
  the page you were on alive in its own tab.

The other destination verbs — `config`, `info`, `dev`, `atlas` — move
the current page too, like `nav`. `list`, `search` and `help` open
nothing at all: their answer is the list itself.

**Picking a row from a list is the same choice.** A row — a result, a
match, or one of your shortcuts — moves the page you are on, exactly as
`nav` does. Hold **Ctrl** (or **⌘**) as you press **Enter**, or ctrl/⌘-click
a row, to open it in a new tab instead, the way `open` does.

**Where the caret goes.** After the box takes you somewhere the caret is
on the page you asked for — its own first field if that page has one,
otherwise the page itself — so you can carry straight on there. **Ctrl+F**
brings you back to the box whenever you want it.

A few words name both a page and an app tab — `sessions`, `messages`,
`chat` and `exa`. The verb is what tells them apart: `nav sessions`
takes the page in this tab, `open sessions` takes the tab.

## When it does not understand you

It answers in the box, in one line, from what it already knows. **Nothing
is sent anywhere**, and no model is called:

- A near-miss on a verb offers the verb: `navv logs` answers
  "Did you mean `nav`?".
- A page it does not know names what was not found and offers the
  closest pages it has.
- Anything else says plainly that it is not a command and points you at
  `help`.

When several wiki pages match equally and nothing you typed breaks the
tie, you get the matches rather than a guess — and `search`/`find` always
answer that way, because listing the matches is what they are for.

## The list you start with

Once you have navigated a few times, opening the box shows **Frequent** —
the destinations you actually use, most-used first, one click away.
**Clear** empties that list. **All N** shows the rest of it, and
**Fewer** puts it back.

It is a list like any other in the box, so the keyboard reaches it: with
nothing selected, **Down** opens it at the top and **Up** at the bottom,
**End** jumps to the last one, and **Enter** opens the row that is
highlighted. **Esc** puts the list away (the box itself goes on the second
press); **Down** or **Up** brings it back.

## `exa`

`exa <question>` is the way out of the grammar, for a question that would
otherwise read as a command: "is search broken on the tools page?" opens
with the word `search`, so `exa is search broken on the tools page?` asks
the question instead.

It opens the Exa chat tab. Your question does not travel across yet, so
the box keeps your words in the input and says so — copy them into Exa's
input.

## The header button is a different thing

The **Exa** button at the right end of the page header is the chat
surface. It takes a prompt, and anything that is not one of the commands
above is sent to Exa from there, with the answer streaming into its box.

The sidebar's **Search** box is navigation only. What it cannot read, it
answers itself.

## Related

- [Chat & Agent Interaction](/wiki/help/chat) — the chat page, and the header's
  Ask-Exa box
- [Exa Agent](/wiki/help/exa-agent) — Exa's page, its commands, and its permissions
- [Dashboard](/wiki/help/dashboard) — the home page and the nav cards
