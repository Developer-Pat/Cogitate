---
title: Setup — Express
category: setup-express
subtopic: Setup
order: 2
confidence: high
created: 2026-11-21
updated: 2026-11-21
tags: [domain/help]
---

# Setup — Express

The Express tab is the shortest path from a fresh install to something that answers: **one model, one
key, one press.** It is the first tab on the Setup page, and the door the install's closing message
points at.

It exists because every other way in assumes rows a fresh install does not have. The API Keys tab
lists keys *on* provider rows; the Default Model tab sets a model *on* a provider. With no provider at
all, both are correct and both are unusable. Express starts from the only thing a person actually has —
a key — and writes the rest.

## What the press writes

| Written | Where it lands |
|---|---|
| The provider, with the key | a provider row, and the key in the project's **`.env`** |
| The chat model | `config.default_model` |
| The five llm chains — chat, title, summary, workflow-llm, memory | each rewritten explicitly, not left to inheritance |
| The default provider | the row the models resolve against |
| The reporters | **Bob** and **Lois**, seeded the moment the model resolves |

The chains are written explicitly rather than inherited because inheritance differs between forks and
an explicit chain is one recorded answer instead of a lookup at call time.

## The shortlist

Five picks, all strong models, shipped as a JSON catalog the setup loads into the database at every
start:

| Pick | Provider | Needs |
|---|---|---|
| DeepSeek · Flash | DeepSeek | a DeepSeek key |
| OpenRouter · DeepSeek Flash | OpenRouter | an OpenRouter key |
| OpenRouter · Qwen 3.7 Flash | OpenRouter | an OpenRouter key |
| OpenRouter · GPT-OSS 120B | OpenRouter | an OpenRouter key |
| Ollama Cloud · Nemotron 3 Super | Ollama Cloud | an Ollama Cloud key |

No `:free` models are on the list. Free tiers are supported unevenly to not at all, and a model that
stops answering is indistinguishable from a broken install to someone who has just installed it.

A key is shared by every pick from the same provider: one OpenRouter key opens all three OpenRouter
entries.

## What each pick says

Each row states its own condition, measured when the page asks:

- **"Its key is already set."** — the variable is present. Nothing to do but press.
- **"Add your … key to use this model — get one from …"** — the key field appears with a link to the
  provider's key page.
- **Local models** are not on the list and say so: a local model is whatever this machine happens to
  run, so it is chosen on the Providers page once the app is up.

The badge beside a pick is a test record: **Tested** with the date, or **Not yet fully tested**. Hover
it for what was actually done.

## What it does not do

- **It does not verify the key.** It checks that a value is present, so a mistyped key still reads
  ready — the first real turn is what fails.
- **It does not estimate cost.** No prices ship with the catalog; DeepSeek's vary by model and by time
  of day, so the cost limit stays inactive rather than enforcing a fiction.
- **It does not answer for you.** No chat turn is driven from this page.
- **It does not touch the rest of `.env`.** Every other line is left exactly as it was.

## Choosing your own

**or choose your own model** on the Setup page leads to its **Default Model** tab, where any
provider and model on this install can be picked. A terminal has the same shortlist:

```bash
uv run python scripts/core/setup_models.py --list-picks
uv run python scripts/core/setup_models.py --pick deepseek-flash
```

## After the press

**Setup → Overview** should read **3 of 3**, and `./cogitate.sh verify` prints the same verdict from a
terminal with exit code 0. Bob and Lois appear on the Agents page. Chat works from that point; nothing
needs a restart.

## Where the key lives

The project's `.env` — the app's single secrets store, gitignored, parsed in Python (never `source` it,
never print a value). A key configured for **Hermes itself** lives in `~/.hermes/.env` and is **not
read** by this app; if that is where yours is, paste it here too.

## Related

- [Installing Cogitate](/wiki/help/setup-install) — the whole path
- [Setup — Overview](/wiki/help/setup-overview) — the verdict this page changes
- [Setup — API Keys](/wiki/help/setup-keys) — managing keys after the first one
- [Setup — Default Model](/wiki/help/setup-model) — the same default, chosen by hand
- [Providers](/wiki/help/providers-overview) — the Provider Dashboard in full
