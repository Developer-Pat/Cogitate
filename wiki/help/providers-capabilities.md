---
title: Capabilities
category: providers-capabilities
subtopic: Provider Management
order: 3
confidence: high
created: 2026-10-05
updated: 2026-10-09
tags: [domain/help]
---

# Capabilities

**Capabilities** answers one question for each job the app needs a service for — *which service does
it use, and what would it try if that fails?* — and it is where you change the answer.

## What a capability is

A capability is a **job**, not a provider. The app has eight:

| Capability | What it powers |
|---|---|
| **Chat** | the models that answer your turns |
| **Title service** | the automatic name a new session gets |
| **Conversation summary** | the rolling summary a long conversation is compacted into |
| **Memory manager** | the model that stores and recalls memory |
| **Workflow LLM steps** | the model a workflow node runs |
| **Text to speech** | what speaks — `piper` (local) or `edge` |
| **Speech to text** | what transcribes — `whisper` |
| **Exa (external agent)** | the external agent process |

No service is named in code: each capability carries its own answer, and this page is where it lives.

## The chain

Each capability has a **chain** — a primary, then optional backups:

- the **primary** is tried first;
- every attempt below it is a **backup**, tried in the order shown;
- the first attempt that answers wins, and nothing below it is consulted.

Saving replaces the **whole** chain, in the order shown. To stop a capability using a service, remove
that attempt — leaving a dead one above a working one only delays every call.

## Why you would configure one

Two reasons, and they are what this page is for:

- **Prefer a local engine.** Put your local server's provider first, with a cloud provider below it —
  then the local one is used whenever it is up.
- **Have somewhere to fall back to.** A capability with one attempt has nowhere to go when that
  service is down; one with a backup keeps working.

## What each card shows

Every card answers with the service, each attempt's role, and the **rung that supplied the answer**:

| Rung | Meaning |
|---|---|
| **capability config** | this capability's own chain answered |
| **global default** | nothing is configured here, so the default provider row answers |
| **agent profile** | the agent's own declaration answered (see the picker below) |
| **override** | an explicit per-request override answered |
| **disabled** | the capability is switched **off** — nothing resolves, and it never falls through |

A card also shows each attempt's **availability**, from the last live check: **up**, **down**, **in use
elsewhere** (another local server holds the machine), or **no key**, with the time it was checked. An
attempt nobody has checked shows **nothing** — an unchecked service is not painted as broken.

## Resolve for an agent

By default the page shows the **sessionless** view: each capability's own chain, with no agent on the
ladder. Picking an agent shows what each capability resolves to **for that agent**. An agent's own
declared service is in play only where a live turn passes one — today the chat capability alone — so
the other cards keep their own answer.

## Editing a chain

**Edit** on a card opens that capability's stored chain in a dialog — one capability at a time, with
the chain it replaces still visible behind it. **Cancel**, the **✕**, or **Escape** closes it without
saving. Each attempt names its service in one of three ways:

- **Provider** — one specific provider row (the usual case);
- **Prefer a class** — every provider of that class, best first, so "prefer local" is configuration
  rather than a named row;
- **Named service** — an engine or process as its own registry lists it (`edge`, `whisper`, `exa`).

**Model** is picked from the **curated list** for that attempt's provider where one exists, so the name
cannot be typed wrong; a provider with no curated models keeps a free-text field. An attempt whose
stored model is not in the curated list keeps it — the picker shows it as
`… (not in the curated list)` rather than replacing it. **Thinking** left empty means any level.
**Up** and **Down** reorder the chain, **Remove** drops an attempt, and **Add a service** appends one.

**Off** switches the capability off entirely: nothing resolves for it, and the part of the app that
needs it **refuses** rather than falling back to a service nobody chose.

## Tips

- Two attempts and the availability badges are how you tell *"is it broken?"* from *"is it simply not
  my turn?"* — a working service with no key reads **no key**, not down.
- The **key** on the right of a card (`tts`, `workflow-llm`) is the name the logs and the API use.
- See [Provider Dashboard — Overview](providers-overview.md) for the providers themselves, and
  [Provider Reference & Quirks](providers-reference.md) for per-provider setup gotchas.
