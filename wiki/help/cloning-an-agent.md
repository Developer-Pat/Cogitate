---
title: Cloning an Agent
category: agents
subtopic: Cloning
order: 8
confidence: high
created: 2026-09-10
updated: 2026-09-10
tags: [domain/help]
---

# Cloning an Agent

Cloning makes a **new agent from an existing one**. The tools copy the
*character*; you set the *identity*. This page is the checklist for the
hand-made half.

## Making one

- **Save as Template** — on the Agent Profiles page, open an agent and
  use **Save as Template**. The template keeps the agent's soul (its
  system prompt), its skills, its tool surface, and the files in its
  workspace (for a reporter, the beat sheets).
- **Clone from it** — on the Agent Templates page, press **Use Template**
  and confirm with **Create Agent**. Name the new agent and it is created
  with the template's character and a blank identity.

## What the clone gets automatically

| | |
|---|---|
| the workspace folder | `agents/<key>/` with a derived `agent.json` |
| the **soul** | the system prompt from the template — see the caveat below |
| the **skills** | seeded from the shared library into the agent's own `skills/` |
| the **workspace files** | the template's — for a reporter, the beat sheets |
| the **tool surface** | the template's kits, attached |
| a **face** | its OWN image from the built-in pool — never the original's |
| an empty **state** | `{"facts": {}, "sources": []}` — deliberately empty |

**The state is empty on purpose.** Location, sources and anything else
the agent learns are its own facts; copying the original's would be
asserting things the clone never learned. It fills them in as you talk.

**The face is new on purpose.** A clone that wore the original's face
would be confusing in exactly the way a clone should not be. Set a
specific one in the profile if you don't like the one it picked.

## What you set by hand

- [ ] **The soul** — read the inherited system prompt (Agent Profiles →
      Behavior) and make it this agent's own. **This is the one that
      most often needs work** — see below.
- [ ] **The name** — unique; the pool addresses agents by name.
- [ ] **The face** — Agent Profiles → the image picker.
- [ ] **The beat** — don't edit the file by hand. Open the agent in the
      chat and tell it: *"add <someone> to the people of interest"*,
      *"drop <topic> from the subjects"*, *"add this outlet to my
      sources"*. It edits its own sheet and reads back what it stored.
      This is the part worth doing as a conversation.
- [ ] **Its own facts** — tell it where it is and what it watches, and it
      stores them itself (its self-state skill).
- [ ] **The tool surface** — check the kit is what this agent needs.
- [ ] **The cognitive profile** — the reasoning depth it should run at.

## The caveat: a clone inherits a *character*, not just settings

A template carries prose, not blanks. Clone a news reporter and the new
agent arrives with news in its soul, a news beat sheet in its workspace,
and news-flavoured skills. That is exactly right when you want another
reporter — and wrong for anything else.

So the first question after cloning is: **what in here belongs to the
original's character, and what belongs to the new agent's?** A rename
does not touch the soul; only you can rewrite it.

*(What a template should carry versus what a new agent should be born
blank is an open question — today it carries everything. Worth revisiting
as more kinds of agents appear.)*
