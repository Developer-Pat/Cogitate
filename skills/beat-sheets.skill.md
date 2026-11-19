---
name: beat-sheets
description: "Your named news sweeps — the beat sheets in your news-beats/ folder (e.g. news-beats/middle-east-vox.md). Use when the user asks for a scan by codeword or name (Vox Populi, etc.), OR when the user asks you to change your beat ('add X to my people of interest', 'drop Y from the subjects') — read the matching sheet; it carries the sources and the interests for that sweep, and you edit it with update-beat."
version: 1.1.0
tags: [news, beat, sources, scans, self-editing]
---

# Beat Sheets

Your beats are **beat sheets** — markdown files in your workspace at
`news-beats/` (workspace-relative — your tools are sandboxed to your own
root, so never prefix with agents/<you>/). Each sheet declares one
sweep: its purpose, the interests (subjects, people, places to watch),
and its sources with `name (description, language)`.

## When to use them

- The user names a sweep by codeword — e.g. **"Vox Populi"** — or
  points at a beat ("the Middle East beat", "run the Vox Populi
  scan"): read the matching sheet from `news-beats/` first, then
  run the sweep from the sheet's sources.
- The sheet's interests are what the user cares about; your
  judgment decides what goes in and what stays out — distill the
  headlines to the best topics.
- Report each item with the outlet's name (description, language)
  as the sheet lists it.

## Co-authoring your beat

The sheet is a working model **you and the user build together** — not
a brief someone else maintains. When the user tells you to change it,
make the change with `update-beat` in the same turn, then confirm it:

| the user says | the call |
|---|---|
| "add Janet Yellen to the people of interest" | `update-beat(list="people", action="add", items=["Janet Yellen"])` |
| "let's drop economics from the subjects" | `update-beat(list="subjects", action="remove", items=["economics"])` |
| "add this outlet to my sources" | `update-beat(list="sources", action="add", items=["TRT (state, Turkish) — https://www.trt.net.tr"])` |

Then:

- **Report the read-back, not your intention.** The tool returns the
  VERIFIED list read from disk — say what it returned. If you did not
  see the item in the read-back, the change did not happen.
- **A remove matches exactly.** If the tool refuses ("not in the
  list"), the wording differs from what is stored: say so, show the
  current list, and ask which one they meant. Never quietly drop a
  near-match — the beat is the user's model of what they care about.
- **Keep their wording.** The items are the user's own words for what
  matters; do not "tidy" them into your own phrasing.
- **One change per request.** If they ask for several, make several
  calls and confirm each.

## Reading a sheet you have not seen

- `list` the sheets before assuming a name; say which beat you are
  reading and which sources it carries.
- If a sheet is missing, or the interests are empty, say so plainly
  and offer to start one — an empty beat is a real answer, not a
  failure to hide.
