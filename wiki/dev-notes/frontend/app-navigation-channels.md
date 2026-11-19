# Navigating the app — the three channels

How a destination gets opened, and which channel to use. Three mechanisms
exist; they do different jobs and none replaces another.

## 1. `nav` — a command, resolved locally

Typed into the Exa flyout: `nav logs`, `nav settings`, `nav /wiki`.

`parseCommand` recognises the verb, `resolveTarget` resolves it against the
generated page map, `openTarget` opens it. **The prompt never reaches Exa** — no
LLM call, no latency, no cost, and impossible to hallucinate.

Verbs: `nav`, `info`, `dev`, `atlas`, `search`.

Use when **you already know where you want to go.** This is the fast path.

## 2. The `OPEN:` marker — Exa answers, and points

You ask a **question** ("how do I turn off the notifications?"). The prompt goes
to Exa. If the answer is better shown than told, Exa appends a line:

```
OPEN: /settings
```

The flyout strips that line before rendering (the marker is machinery, never
shown), validates the destination against the page map, and opens it. An
unknown destination is **reported, not opened**.

Use when **the question's answer is a place.**

## 3. `POST /api/v1/agent_chat/ui-navigate` — Exa acts on its own

```
POST /api/v1/agent_chat/ui-navigate
{"route": "/settings", "replace": false}
```

Broadcasts a `navigation_request` over the UI websocket; the frontend
navigates. **No message, no answer** — Exa presses the button itself, mid-task.

Use when **Exa is doing a job and decides to show you something** — e.g. "check
the provider config and tell me what's wrong" and Exa opens the configuration
page while it works.

### ⚠️ Why this is an HTTP call and NOT a tool

Cogitate's tool registry is **not reachable by Exa.** The ACP client spawns
`hermes acp` with `mcpServers: []`, and the client's own contract is explicit:
*"the agent runtime, tools, memory, and streaming are all Hermes' — this service
only manages the subprocess."* A `tool_call` frame carries **Hermes' own**
tools. A registry entry — however correct — cannot be called by the agent.

This is the wall the knowledge layer already hit (`search-knowledge`,
`graph-query` were registry closures the agent could not reach). The answer is
an **HTTP surface the agent curls**, not tool injection: MCP/plugin wiring is
heavy and buys little for this.

**So: a registry tool is for Cogitate-side agents. Exa's channel is HTTP.**
`open-page` exists on the registry and is correct there — it is simply not, and
cannot be, Exa's route.

## Which one

| | who names the destination | LLM call |
|---|---|---|
| `nav` command | you | none |
| `OPEN:` marker | Exa, while answering you | yes |
| `/ui-navigate` | Exa, on its own initiative | yes |

The channels coexist deliberately. Real use will show which earn their keep;
none should be removed on theory alone.
