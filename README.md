<p align="center">
  <img src="logos/cogito-multicolor-transparent.svg" alt="Cogitate Logo" width="200" height="200"/>
</p>

<h1 align="center">Cogitate™</h1>

<p align="center">
  <em>Training the AI mind by narrowing it.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.14-blue" alt="Python 3.14"/>
  <img src="https://img.shields.io/badge/node-20+-green" alt="Node 20+"/>
  <img src="https://img.shields.io/badge/license-GPLv2-blue" alt="License GPLv2"/>
  <img src="https://img.shields.io/badge/status-active%20development-brightgreen" alt="Status Active Development"/>
</p>

> 🚀 **Project Status: Active Development**
> Cogitate is published mid-build. Issues and pull requests are welcome; there is no release schedule and no
> support promise.
>
> * **Want to contribute?** Open an issue — see [CONTRIBUTING.md](CONTRIBUTING.md).

Cogitate is a research framework for one question: **how do you combine LLMs of different capabilities into
dependable workflows?**

The working hypothesis — the *factoring hypothesis* — is that a smaller or local model looks incompetent at
"trivial" tasks because those tasks are really multi-step, carry hidden state, and have no verification. A
workflow can supply the missing machinery: skills carry the *how*, workflows carry the *when / if / verify*.
The testable claim is that a workflow turns a small model's failures into bounded, verifiable outcomes — and
this application is the instrument for testing it: agents on different providers, a tool registry, and
reusable workflows, in one local installation.

The design behind that framing: [`wiki/dev-notes/design/research-framework.md`](wiki/dev-notes/design/research-framework.md)
and the [`honesty loop`](wiki/dev-notes/design/honesty-loop.md).

---

## Features

- **Multi-Agent Orchestration** — Coordinate multiple AI agents with distinct personas, tools, and provider backends in a single conversation.
- **LLM Provider Management** — Add, configure, and switch between multiple LLM providers (OpenAI, Anthropic, Groq, OpenRouter, local models, and more) with per-agent routing.
- **Workflow Composition** — Build and execute reusable workflows (macros) that chain agent calls, tool invocations, and conditional logic.
- **Tool Registry** — Extensible plugin-style tool system with built-in tools (web search, code execution, file I/O, config inspection) and support for custom tools.
- **Session History & Analytics** — Full session persistence with searchable chat history, token usage tracking, and provider performance comparison.
- **Configuration UI** — In-app management of providers, agents, tools, macros, and system settings.
- **REST API** — Full OpenAPI-documented backend API for programmatic access.

---

## Architecture Overview

Cogitate follows a modern three-tier architecture:

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)           │
│  Agent Interaction · Dashboard · Admin Panels       │
│  └─ Zustand stores · React Query · SSE streaming    │
├─────────────────────────────────────────────────────┤
│                 Backend API (FastAPI)                 │
│  Agent Engine · Tool Executor · Workflow Engine     │
│  └─ LangGraph agents · LiteLLM routing · SSE        │
├─────────────────────────────────────────────────────┤
│                   Data Layer (SQLite)                │
│  Sessions · Messages · Agents · Providers · Tools   │
│  └─ SQLAlchemy async · SQLite-vec (embeddings)      │
└─────────────────────────────────────────────────────┘
```

For detailed architecture documentation, see the tracked wiki:

- [`wiki/Site Index.md`](wiki/Site%20Index.md) — the navigable index (entities, dev-notes, concepts)
- [`wiki/entities/backend-architecture.md`](wiki/entities/backend-architecture.md) — router layers, services, database
- [`wiki/dev-notes/`](wiki/dev-notes) — the design notes and pitfalls, by area

**Storage.** A local install is SQLite throughout: `cogitate.db` for the application, `sqlite-vec` for the
conversation-turn embeddings. The vector layer is an interface (`VectorStore` plus a registry) with one
implementation, so a deployment that needs a server-side vector database — Postgres with pgvector is the one
this project is aimed at — implements that interface rather than changing anything above it. The install doc
carries the detail: [`wiki/help/setup-install.md`](wiki/help/setup-install.md) — also the app's own **Install**
help topic on the Setup page.

The API itself is documented at `/docs` on a running backend (OpenAPI).

---

## Requirements

Linux — Debian, Ubuntu or Mint — with `sudo` and `curl`. That is the whole list.

Everything else comes from the project's own script: `git`, Node.js 20 (NodeSource) and `uv`, which brings
its own Python 3.14 — the project pins 3.14 while distro releases still ship 3.12, so the interpreter
travels with the build tool rather than with your package manager.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Developer-Pat/Cogitate.git
cd Cogitate

# 2. Install the toolchain and the project's dependencies
./cogitate.sh install

# 3. Start the application
./cogitate.sh start

# 4. Open it
#    Frontend:    http://localhost:5173
#    Backend API: http://localhost:8000/api/v1
#    API Docs:    http://localhost:8000/docs
```

`install` is idempotent — a second run reports what is already present and does only what is missing. It
writes `.env` from `.env.example` (never overwriting an existing one), builds `.venv` and
`frontend/node_modules`, and then proves its own work: the venv interpreter matches `.python-version`,
`app.main` imports with every runtime dependency, and `node`/`npm` are on `PATH`.

[`wiki/help/setup-install.md`](wiki/help/setup-install.md) is the same path with the two decisions the install leaves to
you — which model, and whether to activate Exa — plus the storage note and the honest limits.

No API keys are needed to start. **Exa ships inactive** — it is part of the system, but it runs on the
Hermes runtime with a model of its own, so turning it on is your decision, taken on the Exa page. Until
then, anything that reaches for Exa answers that it is not active rather than failing. To see what it
would need on this machine: `uv run python scripts/core/activate_exa.py` (report only; `--apply`
provisions its home and takes the decision).

**Installing with an agent?** The repo carries the instructions an agent needs — clone it and point your
agent at [`skills/cogitate/install-cogitate/SKILL.md`](skills/cogitate/install-cogitate/SKILL.md). It
runs the same `./cogitate.sh install`, verifies the same three URLs, and reports Exa's state instead of
switching it on.

The database schema is built on first start — the app creates every table its models declare, so there is
no migration step to run before the first launch. For an existing database, `alembic upgrade head` (from
`backend/`) applies the versioned revisions instead, and it resolves the same database the app opens:
`DATABASE_URL` when it is set, otherwise `<project root>/cogitate.db`.

The [`cogitate.sh`](cogitate.sh) management script owns both ends of that: `install` sets the machine up,
`start`/`stop`/`restart` run the backend (FastAPI via uvicorn) and the frontend (Vite) as one unit, `mode`
switches the frontend between the live dev server and the built bundle, and `status`/`logs` report what is
actually running. It uses `setsid` so the services survive the terminal that launched them and tracks PIDs
for a clean shutdown. Run `./cogitate.sh help` for usage.

---

## What ships: the news desk

A fresh install carries two reporters — **Bob** and **Lois**, the news desk's first two agents. They are
seeded once from [`backend/templates/agents/`](backend/templates/agents), one tracked package each: a
persona, four skills copied from the shared library, three toolkits (Workspace, Online Search, Cogitate
Library) and a face. On an install with a model configured, they answer a news question the day they
arrive.

Their memory starts **empty**, and that is the design: facts, beats and sources form from your own use.
Nothing ships that pretends to know your town, your watch list or who you trust — say where you are, give
a beat, and watch it accumulate.

Each reporter takes its service from *this* installation's chat answer. The seed writes no model name into
a package, so on an install where nothing answers chat yet the agents **wait** — and say so — until the
setup step takes a model.

The desk as a **team** is not in this release: the journal, the shared role skills and the editor are the
next layer. The agents are seeds, not services — nothing schedules them for you, though any agent can be
put behind a workflow. [`wiki/help/setup-install.md`](wiki/help/setup-install.md) has the detail.

---

## Testing

The project has comprehensive test coverage for both backend and frontend. Key testing resources:

| Resource | Description |
|----------|-------------|
| [`TESTING.md`](TESTING.md) | Full testing guide — running tests, directory layout, fixtures, writing new tests |
| [`scripts/testing/generate_test_report.py`](scripts/testing/generate_test_report.py) | Automated test report generator — runs both suites, produces timestamped markdown reports with pass/fail/timing breakdowns |
| [`scripts/testing/generate_issues_report.py`](scripts/testing/generate_issues_report.py) | Automated issues report generator — runs all static analysis tools (ruff, mypy, eslint, tsc) and reports current error/warning counts |
| `backend/reports/test-report-{date}.md` | Generated test reports — gitignored, so a clone carries none; run the generator to produce one |
| `backend/reports/issues-report-{date}.md` | Generated issues reports — gitignored, same |

**Quick commands:**
```bash
# Test report — default light scan (~2 min)
python3 scripts/testing/generate_test_report.py

# Test report — full sweep (~5-6 min)
python3 scripts/testing/generate_test_report.py --full-sweep

# Issues report — static analysis (ruff, mypy, eslint, tsc)
python3 scripts/testing/generate_issues_report.py
```

For per-suite commands and detailed guidance, see [`TESTING.md`](TESTING.md).

---

## API Documentation

The backend exposes a full REST API with interactive documentation:

| Resource | URL | Description |
|----------|-----|-------------|
| **Swagger UI** | [`http://localhost:8000/docs`](http://localhost:8000/docs) | Interactive API explorer (OpenAPI/Swagger) |
| **ReDoc** | [`http://localhost:8000/redoc`](http://localhost:8000/redoc) | Alternative API documentation view |
| **OpenAPI JSON** | [`http://localhost:8000/openapi.json`](http://localhost:8000/openapi.json) | Raw OpenAPI specification |
| **Health Check** | `GET /api/v1/health` | Service health status |

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/agents` | List all configured agents |
| `POST` | `/api/v1/agents` | Create a new agent |
| `GET` | `/api/v1/sessions` | List chat sessions |
| `POST` | `/api/v1/sessions` | Create a new chat session |
| `GET` | `/api/v1/tools` | List all registered tools |
| `POST` | `/api/v1/tools` | Register a new tool |
| `GET` | `/api/v1/logs/recent` | Retrieve recent application logs |
| `GET` | `/api/v1/logs/stats` | Log statistics by level and source |

All API routes are prefixed with `/api/v1/`. See the [Swagger UI](http://localhost:8000/docs) for the complete endpoint reference with request/response schemas.

---

## Configuration

All configuration is managed through environment variables in [`.env`](.env.example). The keys that matter
most:

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `/` | Backend origin for the browser; `/` is the same-origin vite proxy |
| `APP_NAME` | `Cogitate` | Application name |
| `DEBUG` | `true` | Enable debug logging |
| `DATABASE_URL` | `<project root>/cogitate.db` | Database connection |

Copy [`.env.example`](.env.example) to `.env` at the repository root and set only the keys you need. That file
is **generated** from the settings the app reads (`python3 scripts/dev/generate_env_example.py`), so it lists
every key — each with its default — and a check keeps it that way. Every key is optional: the app runs with no
`.env` at all.

---

## Known Limitations

- **Semantic Search** — Vector-based semantic search requires SQLite-vec support. Full-text search is available via SQLite FTS5, but embedding-based similarity search is not yet optimized for large document collections.
- **pgvector** — PostgreSQL with pgvector is not currently supported. The project uses SQLite as its primary database. Migration to PostgreSQL/pgvector is a future roadmap item. If your use case requires production-grade vector search, consider forking and adding pgvector support.
- **Frontend TypeScript** — Strict mode `tsc -b` may produce pre-existing TS6133 errors (unused imports). The Vite build (`vite build`) completes successfully independently, so these do not block development.
- **API Key Rotation** — Several API keys for external LLM providers have been leaked in git history. These must be revoked and rotated before any public GitHub push.
- **LLM Provider Dependency** — Core functionality requires at least one configured LLM provider (default: Ollama with local models). Some features may be unavailable without a running provider.

---

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) to get started.

All participants in this project are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

---
## License

This project is licensed under the **GNU General Public License v2 (GPLv2)** — the same license used by the Linux kernel.

Copyright (C) 2026 The Cogitate Authors. See [`NOTICE`](NOTICE) and the [`LICENSE`](LICENSE) file for the full license text.

**Trademark Notice:** "Cogitate" and the Cogitate logo are trademarks of the project. Unauthorized use of the name or logo is prohibited. Forks must rename and remove the logo to avoid confusion.

---

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/), [React](https://react.dev/), [LangChain](https://www.langchain.com/), and [LiteLLM](https://litellm.ai/)
- Iconography by [Lucide](https://lucide.dev/)
- Charts by [Recharts](https://recharts.org/)
