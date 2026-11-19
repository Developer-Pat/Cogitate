---
title: ExaPromptFlyout
type: atlas-component
path: frontend/src/components/features/agentInteraction/ExaPromptFlyout.tsx
confidence: high
updated: 2026-09-19
tags: [type/component, domain/atlas-ui, domain/navigation]
---
# ExaPromptFlyout

**Path**: `frontend/src/components/features/agentInteraction/ExaPromptFlyout.tsx`
**Last Updated**: 2026-09-19

## Purpose
The app's **Ask-Exa box**: a trigger reading *Exa* (on the same
`pill-button` tokens as its neighbours) and a flyout that takes a prompt and
answers with a **message** or a **destination**.

The command verbs (`nav` / `exa` / `list` / `search` / `info` / `dev` / `atlas`)
are resolved in the browser. All but `exa` **never reach the LLM** — `nav` opens
no socket at all, which is the determinism the feature rests on. Anything that is
not a verb is sent to Exa over the `/api/v1/external-agent/ws` bridge, and the
answer streams in.

`exa` is the exception and the reason it exists: it is the **escape hatch**. A
question that opens with a verb word ("search is broken on the tools page") is
otherwise read AS that verb and never reaches Exa. `exa <question>` forces the
model path — `sendPrompt`, the one place a prompt leaves for Exa — with the
prefix stripped. Bare, `exa` opens the Exa page (`nav exa`'s own target).

`nav list` / `nav pages` answer with the whole map as links, reusing the
`list` result list. They are checked BEFORE `resolveTarget`: `list` is a word
inside the key "session list", so the fuzzy stage matched it at distance 0 and
opened Sessions — the plausible-wrong-jump this module refuses to make.

Mounted **once per page, never in a bar of its own**: `PageBanner` carries it on
the title row's right side (26 of 45 pages), and the Agent Chat page carries it
in its own header cluster as the right-most control. A page with its own
right-hand button group seats it there instead and passes `hideCommand` — in a
`justify-between` header row a banner-seated pill lands at the page's left edge
and its leftward-opening panel is clipped by the nav panel (the Logs and Message Center pages). See
[[dev-notes/frontend/command-box|The Command Box]].

## Props Interface
```typescript
interface ExaPromptFlyoutProps {
  onOpenExaPage?: () => void   // defaults to the app's own Exa destination
}
```
A **bare mount** (`<ExaPromptFlyout />`) is complete — no plumbing, nothing to
fetch.

## Responsibilities
- the command verbs, resolved locally; a tie or an unknown target returns
  candidates rather than a guess
- the ws prompt path: coalesced streamed chunks, live tool-call activity, and
  LOUD failures on `status: error / cancelled / time_limit`
- the `OPEN: <path>` marker (answer-form 2): stripped from the reader's view,
  then resolved and validated before anything opens
- the shortcut list (`Frequent` / `All` / `Clear`) fed by `navHistory`
- Cmd/Ctrl+K (open from anywhere), Escape, click-outside

The flyout is **one of three ways a destination opens**, and the only one that
rides this component: the `nav` verb is local, the marker is Exa answering, and
`POST /agent-chat/ui-navigate` is Exa acting on its own with no message at all.
The endpoint is Exa's channel rather than a tool because the agent cannot reach
the host's registry. See
[[dev-notes/frontend/app-navigation-channels|Navigating the app]].

## Related
- [[atlas/ui/services/appNavigation|appNavigation]] — the map, the resolver, the verbs
- [[atlas/ui/services/navHistory|navHistory]] — the shortcut list
- [[atlas/ui/pages/AgentInteraction|AgentInteraction]] — its Agent Chat mount
- [[atlas/ui/components/ui/PageBanner|PageBanner]] — the row it rides elsewhere
- [[dev-notes/frontend/app-navigation-channels|Navigating the app]] — the three channels
