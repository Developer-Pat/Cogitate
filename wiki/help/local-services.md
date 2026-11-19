---
title: Local Services
category: local-services
subtopic: Overview
order: 1
confidence: high
created: 2026-09-03
updated: 2026-09-03
tags: [domain/help]
---

# Local Services

The page for the LOCAL services on this machine — the local LLM
servers (llama-server, ollama) and the capabilities they power
(session titles today; more later). It is the operation surface:
see the state, test the wiring, and change which provider a
capability uses — all in one place.

## Local service providers

Each local provider row appears with its base URL and a **Test**
button:

- **Test** — checks the server is actually reachable and reports
  the result: "Reachable ✓" with a message, or "Unavailable —"
  with the reason. A local server that is down, or a model that
  cannot load (for example, no GPU memory left), shows its state
  here — never a silent empty.
- Local servers are keyless — the test checks them directly
  against their own address; no API key is required.

## Capabilities

A capability is something the system does using a provider. Each
capability has a card here with its controls.

### Session titles

The title capability names sessions from their conversation.
Controls:

- **Title Generation Model** — which model names the sessions:
  - **Agent model** — the active chat agent's LLM (whatever the
    agent uses — always works if the agent works).
  - **Backend default** — the default provider row (deepseek by
    default). Reasoning is turned OFF for thinking models on this
    simple task, so titles come back quickly instead of being
    consumed by "thinking".
  - **Custom** — a specific model string (e.g.
    `deepseek/deepseek-v4-flash`).
- **Auto-Title** — generate a title after the first message. Many
  sessions start with "hello" (uninformative titles) or get
  deleted anyway — leaving this off and renaming deliberately is a
  common setup. The rename buttons on the chat page and the
  Sessions page always work regardless.
- **Resolved state** — what the capability is actually using right
  now (provider, model, reasoning), plus the default-provider row.
- **Test rename** — runs a real title generation through the
  current configuration so you can verify the setup end-to-end.
- **Save** — persists the preference changes.

The same preference governs the rename buttons everywhere (chat
page and Sessions page) — one model source, consistent behavior.

## Related

- [[help/settings|Settings]] — the other application preferences
- [[help/sessions|Sessions]] — the rename actions
- [[help/providers-overview|Providers]] — the provider registry
