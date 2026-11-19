---
title: Trash
category: trash
subtopic: Overview
order: 1
confidence: high
created: 2026-10-06
tags: [domain/help]
---

# Trash

Everything that was moved out of the way instead of erased. Nothing arrives here
on its own — there is no retention rule, nothing is pruned automatically, and no
shelf is emptied on a schedule. Something is on a shelf because a person, a
script or a test put it there.

A delete in this app is a move. Retiring a test run, deleting an agent's
workspace, and the files that no part of the app claims all land on a shelf
rather than disappearing, so that the decision to destroy anything is made
deliberately and in the open.

## The five shelves

Each shelf holds one kind of thing, and it answers only to its own phrase —
emptying one never touches another.

**Agents** — workspaces of deleted agents. This is the one shelf that reads the
database: an entry a row still names can be **restored** (the row is the
destination), and a folder no row names is **residue** — purge only, because
nothing records where it came from.

**Test runs** — runs retired from the user-testing page, kept whole with their
`report.md`, `report.xml` and `events.jsonl`. Restoring one puts it back in the
runs list; if the name has been taken since, it comes back with a suffix and the
page says so.

**Reports** — report folders that were moved out of the way rather than deleted.
Nothing recorded where they came from, so there is no restore: purge only.

**Databases** — retired database backups. These are recovery material: removing
them is permanent, and putting one back is never automatic. Copy one out and
restore it by hand if you need it.

**Misc** — everything the other shelves do not claim: a loose file dropped in the
trash root, a directory nobody registered, the leftovers of something else's
move. It exists so the trash has no invisible content. A shelf's own directory is
never an entry on this shelf.

## Restore

Puts one entry back where it came from. It is offered only on rows a record
backs; the rest say why they cannot be restored rather than showing a button that
would not work. A restore is additive — it moves one entry back and changes
nothing else.

## Delete forever

The one action in this app that cannot be undone. Both forms are plain
confirmations — a dialog that names exactly what goes, and two buttons:

- **A single entry** names the entry, the directory it comes off, what it holds,
  and that nothing can restore it. Where the shelf has a way back, the dialog
  points at Restore as the alternative.
- **Emptying a whole shelf** names the shelf, its directory, and how many entries
  go.

Nothing is retyped: a sentence read off the dialog in front of you and typed back
adds nothing to a decision you have already made. And neither form is offered as
a shortcut anywhere else — there is no global empty and no "clean up" button.
