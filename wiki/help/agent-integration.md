---
title: Exa Agent
category: agent-integration
subtopic: Overview
order: 1
confidence: high
created: 2026-08-12
updated: 2026-11-18
tags: [type/help, domain/agents]
---

# Exa Agent

**Exa** is the external consulting agent. You work with it from the
**Exa panel** on the Chat page — ask it to investigate a problem,
and it checks the logs, traces, and system state to figure out what
went wrong and how to fix it.

This page configures the Exa connection. Currently **Hermes** is the
default Exa agent.

## Connection

- **Status** shows whether Exa is ready (`connected`) or not
  (`offline`). The panel starts Exa when you open it, so this may
  read `offline` until you've opened the panel at least once.
- **Restart agent** — stops Exa and starts it fresh with the saved
  settings. Use this after changing the configuration.

## Copying the conversation

The **⋮ More actions** menu (top-right of the panel) holds **Copy**,
**Save**, and **Clear**. **Copy** puts everything Exa did into your
clipboard: your questions, Exa's answers, **and every tool it ran** —
including lines that scrolled off screen. Useful for saving a
diagnosis or sharing it.

## Stopping Exa

If Exa is taking too long or going down the wrong path, you can stop
it from the panel:

- **Stop** — the gentle option. It asks Exa to stop what it's doing
  (like pressing Ctrl+C). If Exa doesn't stop within a few seconds,
  it is ended automatically. The next question starts a fresh Exa.
- **Force Kill** — the last resort. It ends Exa and everything it
  started, immediately. Use it only if **Stop** doesn't work.
  (Confirmation is required — Force Kill can't be undone.)

Neither button is affected by the panel being busy — they're always
available while Exa is connected.

## Configuration

- **Agent command** — the program that starts Exa (default
  `hermes acp`). You normally don't need to change this.
- **Working directory** — where Exa works (default: the project
  root). Change it only if Exa should work in a different folder.

## Time limit

Each Exa run is automatically stopped after **5 minutes** (300
seconds) by default, so a stuck or overly thorough run can't run
forever. When that happens the panel tells you *"Time limit
reached"* — you can re-ask with more detail, or raise the limit.

- Set **Whole-turn time limit (seconds)** to change it: higher for
  deep investigations, **0 for no limit** (runs until Exa finishes
  or you stop it).
- The panel shows **how long Exa has been working** while it runs
  (e.g. `thinking… · 1m 23s`), so you can tell "working" from
  "stuck" and decide whether to wait or stop.
- The limit applies to one question-and-answer turn; the next
  question starts fresh.

## Permission tier

How much write access Exa gets is the **Permission tier** card — a
3-way selector (it replaced the old fix-mode toggle):

| Tier | What Exa can write | The badge |
|---|---|---|
| **Chat approval** (default) | propose edits — EVERY one shows an Allow / Deny card in the chat | per-edit approval |
| **Fix mode** | write anywhere inside its workspace without asking | fix granted |
| **YOLO** | write anywhere — no per-edit approval (the secret-file guard still protects .env/.ssh/.git) | unrestricted |

- **YOLO is not unsupervised**: every action is still recorded and
  audited, and the chat's **Stop** button (while Exa streams) halts
  a run instantly — that's what bounds the runaway risk.
- The tier applies to the whole session; **Save** restarts Exa with
  the selected tier (the old `fix_mode` setting in saved configs
  maps to the equivalent tier automatically).
- The **panel always shows the current state** — the badge tells you
  exactly what Exa can do right now.

## Saving

- **Save** applies your settings and restarts Exa with them.
- The button is disabled until you change something.
