---
title: Installing Cogitate
category: setup-install
subtopic: Setup
order: 0
confidence: high
created: 2026-11-18
tags: [domain/help]
---

# Installing Cogitate

Cogitate is a research framework for combining LLMs of different capabilities into dependable workflows — a
local installation of many agents, a tool registry and reusable workflows, for testing what makes a small
model's work verifiable.

The README's Quick Start is four commands. This page is the same path, with the two decisions the install
deliberately leaves to you and the honest limits of a local installation.

## What the machine needs

Debian, Ubuntu or Mint, with `sudo` and `curl`. That is the whole list — `./cogitate.sh install` brings
git, Node.js 20 and `uv`, and `uv` brings its own Python 3.14 (the project pins 3.14; distro releases
still ship 3.12).

## 1. Install

```bash
# A release copy: no git, no key, no account once downloaded. Get the tarball and
# its .sha256 from https://github.com/Developer-Pat/Cogitate/releases/tag/v0.1.0
# (the repository is private today, so that page needs access to it); check the
# download, then unpack it.
sha256sum -c cogitate-0.1.0.tar.gz.sha256
tar xzf cogitate-0.1.0.tar.gz && cd cogitate-0.1.0

./cogitate.sh install
```

A **clone** works identically — `git clone <repo> && cd Cogitate` — and is the path for working on the
code rather than running it. `install` treats git as a clone dependency: it is checked and installed
only when the directory is a repository, and skipped with `git not needed (release copy)` otherwise.

What it touches, in the order it does it:

| Step | What happens |
|---|---|
| git | `apt`, only when the tree is a clone and git is missing — never for a release copy |
| uv | astral's installer, into `~/.local/bin` |
| Node 20 | NodeSource's apt repo — the distro's nodejs is 18, and Node is a **runtime** dependency: both frontend modes run through `npx vite` |
| `.env` | copied from `.env.example`, never overwriting an existing one. No keys are set |
| dependencies | `uv sync` (creates `.venv` with a managed Python 3.14) and `npm ci` |

It is idempotent: a second run reports what is already present and does only what is missing — a warm
re-run is a matter of seconds. It ends by **proving** the install rather than assuming it: the venv
interpreter matches `.python-version`, `from app.main import app` imports with every runtime dependency,
and `node`/`npm` are on `PATH`.

## 2. Start

```bash
./cogitate.sh start
```

Backend on `http://localhost:8000`, frontend on `http://localhost:5173`. Both are supervised (one process
group each, PIDs tracked) so `stop`, `restart` and `status` mean what they say.

The database is built on first start: `cogitate.db` at the project root, carrying every table the models
declare. **There is no migration step for a fresh install.** `alembic upgrade head` (from `backend/`) is
the path for an existing database, and it resolves the same database the app opens — `DATABASE_URL` when
set, otherwise the project-root file.

## 3. Verify

```bash
./cogitate.sh verify
```

One line, read from `GET /api/v1/setup/readiness`: `READY — 3 of 3 checks pass, 0 remaining.` An
unmet item is named with the page that fixes it and the command exits non-zero, so a scripted
install can gate on it; `--json` prints the payload.

It asks whether the install can **answer** — a provider with a key or a local server, a chat model
that resolves, the agents seeded behind it. Exa's runtime is reported and not counted: activating
Exa is a decision, not a requirement. The three URLs are the liveness smoke test, and `start` waits
for both services before it returns:

```bash
curl -s -o /dev/null -w "frontend %{http_code}\n" http://localhost:5173/
curl -s -o /dev/null -w "api      %{http_code}\n" http://localhost:8000/api/v1/health
curl -s -o /dev/null -w "docs     %{http_code}\n" http://localhost:8000/docs
```

All three `200`, with no API keys set — the app starts and serves without them. A key (or a local
model server) is what makes `verify` say ready, because it is what makes an agent answer.

## 4. The two decisions the install leaves to you

### A model — the Setup page's Express tab, or `scripts/core/setup_models.py`

The shortest path is in the app: **Setup → Express**, one model from a shortlist, one key, one press
([Setup — Express](/wiki/help/setup-express)). From a terminal, the same choice is a script:

Structure ships with the install (the capability rows, the provider shells, the tables); a **value** — which
model answers — is offered rather than decided. The step reports every capability, proposes only what this
machine can actually back (a provider whose key is in `.env`, or a local server that answers and reports a
model), and takes each offer one at a time:

```bash
uv run python scripts/core/setup_models.py                  # ask about each offer
uv run python scripts/core/setup_models.py --check          # report only
uv run python scripts/core/setup_models.py --accept-defaults # take every offer (scripted installs)
uv run python scripts/core/setup_models.py --scratch        # leave it bare; say what is off
```

A capability nothing can resolve is **reported**, not filled: an install with no embedding model says that
indexing and document search are off, and leaves the choice to you.

### Exa — `scripts/core/activate_exa.py`

Exa — the external agent Cogitate drives — ships included and **inactive**. Until you turn it on, anything
that reaches for it answers that it is not active. Turning it on is a decision, and it has a sequence behind
it:

```bash
uv run python scripts/core/activate_exa.py                    # report: runtime, home, model, keys, decision
uv run python scripts/core/activate_exa.py --apply             # provision the home and activate
uv run python scripts/core/activate_exa.py --apply --from-default  # ...and take this install's chat model
```

The runtime is the one thing the CLI will not install for you: Exa runs on the Hermes agent runtime, and if
`hermes` is not on `PATH` the report hands you the installer command. Provisioning creates Exa's own home
and its skills, and carries the provider keys across — it never chooses a **model**: that is a decision,
taken by `--from-default`/`--model` here or by one press on the Exa page, which offers this install's chat
model. A home that already has a model keeps it.

## 5. What ships: the news desk

Two reporters — **Bob** and **Lois** — arrive seeded. They are the news desk's first two agents and what an
install carries out of the box: the character ships, the use is yours.

The source is tracked, one package per agent under `backend/templates/agents/<key>/` (`package.json` plus
`persona.md`). The seed creates exactly this:

| What | Detail |
|---|---|
| the agent | name, description, the persona as its system prompt, its skills and parameters |
| the workspace | `agents/<key>/` — the derived `agent.json`, `persona.md`, an **empty** `state.json`, and the skills copied out of the shared library |
| the toolkits | **Workspace** (files, notes, beats, facts), **Online Search** (duckduckgo, wikipedia, jina_reader) and **Cogitate Library** (the project's own docs and skills) — created by name, or reused when your install already has them |
| the face | copied from the curated pool into the image store |

**Their memory starts empty, and that is the design.** Facts, beats and sources form from your own use —
nothing ships that pretends to know your town, your watch list or who you trust. Tell a reporter where you
are and what to watch; the state and the beat sheets accumulate from there.

**No model is written into a package.** Each reporter takes its service from *this* installation's answer
to "what answers chat" — your keys and your hardware decide it. On an install where nothing answers chat
yet the agents **wait**: the seed reports `deferred` with the reason and tries again on the next start, and
accepting a chat model in step 4 seeds them immediately, with no restart.

**What is not in the box.** The desk as a *team* — the journal, the shared role skills, the editor — is the
next layer, not this release. Nothing schedules the reporters (any agent can be put behind a workflow
instead). Exa, the system manager, ships inactive as described above. Two agents are seeds, not a
newsroom.


## Storage: SQLite now, and the seam for a server database

A local install stores everything in SQLite: `cogitate.db` for the application, plus `sqlite-vec` for the
conversation-turn embeddings.

The vector layer is an **interface**, not a database call: `VectorStore` (an abstract base) with a registry,
and `sqlite-vec` is its only implementation today. A deployment that needs a server-side vector database —
Postgres with pgvector is the one this project is aimed at — implements that interface; nothing above it
changes. The schema is dialect-neutral where it matters: the models are SQLAlchemy, and the one full-text
index that needs a dialect-specific form declares its Postgres shape, which SQLite ignores.

## Honest limits

- **Exa needs the Hermes runtime.** It is not installed by `./cogitate.sh install`, and nothing pretends
  otherwise.
- **Image generation needs ComfyUI**, installed and running separately — the app does not bundle a diffusion
  stack.
- **This is a local application**, not a hosted service: one backend and one Vite server, no TLS, no reverse
  proxy, no multi-user auth.
- **No API keys ship, and none are needed to start.** A key, or a local model server, is what makes an agent
  answer.

## Related

- [Testing Guide](/wiki/docs/testing) — running the suite and the sweeps
- [Script Catalog](/wiki/docs/script-catalog) — every script, including the two above
