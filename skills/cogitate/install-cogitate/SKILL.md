---
name: cogitate-install-cogitate
description: "Install Cogitate on a Linux box and leave it running: download the release copy (or clone), one bootstrap command, one readiness check, then decide about Exa. Use when asked to install, set up, or run Cogitate for the first time."
version: 2.1.0
author: Cogitate Team
license: MIT
metadata:
  cogitate:
    tags: [install, setup, onboarding, deployment, cogitate, exa]
    related_skills: [cogitate-orientation]
---

# Install Cogitate

## Overview

A release copy (or a fresh clone) plus ONE command is a working install: `./cogitate.sh install`. It is idempotent, it
verifies its own steps, and it is the only thing that defines what "installed" means — every other
delivery path (a package, this skill) wraps it, so do not reimplement any part of it by hand.

Two facts that decide how you work here:

- **The bootstrap installs the toolchain.** git and Node.js 20 come from apt, `uv` from its own installer,
  and Python 3.14 is uv-managed — the distro's 3.12 is not enough and installing python by hand is how you
  end up with a venv the app never opens.
- **Exa is INACTIVE on purpose.** It ships included, switched off, with no key: activation is the user's
  decision, never a side effect of installing. Report its state; do not turn it on unasked.

## When to Use

- The user asks you to install, set up, or run Cogitate for the first time.
- A Cogitate install is broken at the environment level (missing `.venv`, `node_modules`, or a runtime).
- The user asks whether Exa is available, or asks you to "set up Exa".

## Steps

1. **Preflight — read, do not install.** Confirm the machine can host it, and say what you found:

   ```bash
   . /etc/os-release && echo "$PRETTY_NAME"; command -v apt-get curl sudo
   df -h / | tail -1; sudo -n true && echo "sudo: passwordless" || echo "sudo: will prompt"
   ```

   Debian, Ubuntu or Mint with `curl` and `sudo` is the whole requirement. Anything else: stop and report.

2. **Get the code.** The release copy is the shipped path — no git, no key, no account once the files are
   on the box:

   ```bash
   # cogitate-0.1.0.tar.gz and its .sha256, from
   # https://github.com/Developer-Pat/Cogitate/releases/tag/v0.1.0
   # (the repository is private today, so that page needs access to it)
   sha256sum -c cogitate-0.1.0.tar.gz.sha256
   tar xzf cogitate-0.1.0.tar.gz && cd cogitate-0.1.0
   ```

   Working on the code instead: `git clone https://github.com/Developer-Pat/Cogitate.git && cd Cogitate`.
   If the clone is refused for auth, the repository is not public yet — report that, and never substitute
   a mirror.

3. **Install.** `./cogitate.sh install`. It installs git if absent, uv, Node 20, creates `.env` from
   `.env.example` (never overwriting one), runs `uv sync` and `npm ci`, then proves the result (interpreter
   matches `.python-version`, `app.main` imports, node/npm on PATH). It uses `sudo` for apt. Exit 0 means
   every check passed; a failure names the step it stopped at.

4. **Start and verify.** `./cogitate.sh start`, then the acceptance check:

   ```bash
   ./cogitate.sh verify          # exit 0 = the install can answer; --json for the payload
   ```

   One line, from `GET /api/v1/setup/readiness`: `READY — 3 of 3 checks pass, 0 remaining.` When an
   item is unmet it is NAMED with the page that fixes it and the command exits non-zero, so quote
   `remaining` and the unmet items — never a paraphrase of them. Readiness asks whether the install
   can ANSWER (a provider with a key or a local server, a chat model that resolves, the agents behind
   it); Exa's runtime is reported and not counted.

   The three URLs are the separate liveness smoke test:

   ```bash
   curl -s -o /dev/null -w "frontend %{http_code}\n" http://localhost:5173/
   curl -s -o /dev/null -w "api      %{http_code}\n" http://localhost:8000/api/v1/health
   curl -s -o /dev/null -w "docs     %{http_code}\n" http://localhost:8000/docs
   ```

   All three `200`. The database is built on first start — there is **no migration step** for a fresh
   install (`create_all` creates every table the models declare).

5. **Exa — report, then ask.** Exa is the external agent the app drives; it needs a runtime on PATH, an
   isolated home, a model and a key. Print the state instead of guessing:

   ```bash
   uv run python scripts/core/activate_exa.py          # report only — writes nothing
   uv run python scripts/core/activate_exa.py --apply  # ONLY on the user's word
   ```

   The report lists runtime / home / model / keys / decision, each with the fix that is missing. `--apply`
   provisions the home and takes the activation decision; `--from-default` also writes THIS install's chat
   model. Provisioning never chooses a model — that is a decision, and a home that already has one keeps it
   (the page makes the same offer in one press). `--apply` never installs a runtime — if `hermes` is
   absent the report hands you the installer command, and installing it is the user's call.

6. **Report back** — versions (Python, Node, vite), the three URLs, and Exa's state in one line with the
   reason it is inactive (or what is still missing).

## Common Pitfalls

- **Do not pre-install the dependencies.** No `uv venv`, no `pip install -r requirements.txt`, no `npm
  install`: the repo has a uv workspace with its own lock, and a hand-built venv is one the app never uses.
- **Python 3.14 is uv-managed.** The distro ships 3.12; `.python-version` pins 3.14 and `uv sync` downloads
  it. Never `apt install python3` to "fix" an interpreter problem.
- **Node is a RUNTIME dependency, not just a build one** — both frontend modes run through `npx vite`, so a
  machine that can build but has no node cannot serve.
- **Never source `.env`** and never print a value from it; the app parses it in Python. The activation CLI
  reports key NAMES only, by design.
- **`.env` is never overwritten** by the installer: a re-run reports "present (left untouched)".
- **A second `install` is a ~10-second no-op.** If it takes minutes on a warm tree, something is
  unconditional and that is a bug worth reporting, not a wait worth enduring.
- **Migrations are not part of a fresh install.** `alembic upgrade head` is for an EXISTING database; on a
  fresh one it is a no-op at best and a confusing one at worst.
- **Do not activate Exa to "check whether it works".** Activation is a persisted user decision with a
  runtime and a model behind it. Probe, report, and let the user decide.

## Verification Checklist

- [ ] `./cogitate.sh install` exits 0 and prints "Install complete"
- [ ] `.venv/bin/python --version` matches `.python-version` (3.14)
- [ ] the installer's import check passed — or `cd backend && ../.venv/bin/python -c "from app.main import app"`
- [ ] `./cogitate.sh verify` exits 0 and prints `0 remaining` — or, on a non-zero exit, every unmet
      item is reported to the user verbatim with its page
- [ ] frontend `/`, `/api/v1/health`, `/docs` all answer `200`
- [ ] `cogitate.db` exists at the project root and carries tables (first start built it)
- [ ] `uv run python scripts/core/activate_exa.py --json` prints a truthful report, and Exa's state is
      reported to the user with the reason it is inactive (or what it still needs)
