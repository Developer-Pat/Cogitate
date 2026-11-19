---
title: Beats — the agent's own news sweeps
type: atlas-devnote
category: agents
order: 10
confidence: high
updated: 2026-09-10
tags: [type/devnote, domain/agents]
---

# Beats — the agent's own news sweeps

A beat sheet is the working model of what a reporter covers: the
purpose, the interests (Subjects / People / Places), and the sources.
It lives at `agents/<key>/news-beats/<name>.md` — plain markdown, so
it stays hand-editable and git-visible.

## The beat is co-authored

The sheet is **built with the user, in chat** — not a brief someone
maintains on the reporter's behalf. The user says *"add Janet Yellen to
the people of interest"* or *"let's drop economics from the subjects"*
and the agent edits the sheet in the same turn.

The tool is `update-beat` (`agent_beat_handler.py`), on the same
workspace write surface as `update-state` / `update-sources` (keyed,
`needs_workspace=True` — the execution service injects the agent's own
folder as `base_path`, exactly as for the state tools):

```
update-beat(list="people", action="add", items=["Janet Yellen"])
update-beat(list="subjects", action="remove", items=["economics"])
```

It returns the **verified read-back** — the list as it now stands on
disk. The skill (`beat-sheets`) requires the agent to report that
read-back rather than its intention, so a change that did not land
cannot be reported as though it did.

## Why the editing is surgical

The store (`agent_beats.py`) never round-trips the markdown through a
serializer — it edits the one line that changed, so the prose, the
other lists and the comments survive untouched. Two details make that
correct:

- **Items split on top-level commas only.** Commentary carries its own
  commas — `the war (Iran/Israel, both sides' press)` is ONE item — so
  the splitter tracks parenthesis depth.
- **Wrapped entries rejoin before parsing.** A long item continues on
  an indented line; the continuation must be joined back or the tail
  is silently dropped. Both the read and the edit share one parser
  (`_parse_interest_entries`) so a round-trip cannot drift.

A remove is an **exact** match (case/whitespace normalised). When it
matches nothing the tool refuses with the current list rather than
quietly doing nothing: silently editing the user's beat is worse than
refusing, because the user believes it changed.

## What a reporter is born with

An agent applied from the News Reporter template gets its own face, the
`beat-sheets` and `self-state-maintenance` skills (both in the shared
library at `skills/`), its beat sheets from the template's
`workspace_files`, the Workspace kit's tools, and an empty state — the
character, never the instance. See
[[dev-notes/agents/agent-identity|Agent Identity]].
