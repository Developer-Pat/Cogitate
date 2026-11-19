# Contributing to Cogitate™

First off, thank you for considering contributing to Cogitate! We appreciate your interest in this project.

> 🚀 **Note:** This project is under **active development**. Contributions, bug reports, and feature requests are welcome! See the [README](README.md) banner for details.

---

## Table of Contents

- [How to Report Issues](#how-to-report-issues)
- [How to Propose Changes](#how-to-propose-changes)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Pull Request Process](#pull-request-process)
- [Forks and the Name](#forks-and-the-name)
- [Code of Conduct](#code-of-conduct)

---

## How to Report Issues

Bug reports and feature requests are tracked via the [GitHub Issues](https://github.com/Developer-Pat/Cogitate/issues) tab.

When reporting a bug, please include:

1. A clear and descriptive title
2. Steps to reproduce the issue
3. Expected vs. actual behavior
4. Screenshots or logs, if applicable
5. Environment details (OS, Python version, Node.js version)

For feature requests, describe the feature you'd like, why it's useful, and any implementation ideas you have.

---

## How to Propose Changes

For significant changes or new features, start by opening an [issue](https://github.com/Developer-Pat/Cogitate/issues) describing what you intend to change and why. This coordinates efforts and avoids duplicate or conflicting work before you invest time in a Pull Request.

Small bug fixes and documentation improvements are welcome as direct Pull Requests.

---

## Development Setup

### Prerequisites

A Debian, Ubuntu or Mint machine with `sudo` and `curl`. That is the whole list — `./cogitate.sh install`
brings git, Node.js 20 and `uv`, and `uv` brings its own Python 3.14 (the project pins 3.14; distro
releases still ship 3.12).

### Getting Started

```bash
# Clone the repository
git clone https://github.com/Developer-Pat/Cogitate.git
cd Cogitate

# Install the toolchain and the project's dependencies (idempotent)
./cogitate.sh install

# Start the development servers
./cogitate.sh start
```

See [`README.md`](README.md) and the [`cogitate.sh`](cogitate.sh) help output (`./cogitate.sh help`) for detailed development instructions, including:
- How to view logs (file-based and API-based)
- How to run specific backend services
- Debugging workflows

---

## Coding Standards

### Backend (Python)

- **Formatter:** [Black](https://black.readthedocs.io/) with line length 88
- **Imports:** [isort](https://pycqa.github.io/isort/) with the `black` profile
- **Type Hints:** Strongly encouraged (checked with [mypy](https://mypy-lang.org/))
- **Testing:** [pytest](https://docs.pytest.org/) with `pytest-asyncio` for async tests
- **Linting:** Ruff (configured in `pyproject.toml`)

Run backend checks:
```bash
cd backend
uv run black --check .
uv run isort --check .
uv run mypy .
uv run pytest
```

### Frontend (TypeScript/React)

- **TypeScript:** Strict mode enabled
- **Testing:** [Vitest](https://vitest.dev/) with React Testing Library
- **Linting:** ESLint with project-specific rules (see `eslint.config.js`)
- **Formatting:** Prettier (follow project conventions)

Run frontend checks:
```bash
cd frontend
npm run lint
npm run test
npm run build
```

---

## Pull Request Process

1. **Fork** the repository and create your branch from `main`.
2. **Commit** changes with clear, descriptive messages.
3. **Test** your changes — ensure existing tests pass and add new ones for new functionality.
4. **Lint** your code to match project style.
5. **Open a Pull Request** with a clear title and description explaining what your changes do and why.
6. **Respond to feedback** — reviewers may ask for clarifications or changes.

### Pull Request Checklist

- [ ] Code follows project coding standards
- [ ] Tests added/updated and passing
- [ ] Documentation updated if needed (README, docs/, inline comments)
- [ ] No new lint warnings or errors
- [ ] Changes are focused and well-scoped (one feature/fix per PR)

---

## Forks and the Name

Forking is welcome — the GPLv2 gives you that right. The license covers the code; it does not cover the
project's identity, which is the one thing a fork may not carry.

- **Rename the project.** A fork is not called Cogitate — not on its own, and not with a prefix or a suffix,
  since "Cogitate Plus" still tells a reader it is this project.
- **Remove or replace the logo.** No copy of the mark in the fork's README, app title, favicon, or published
  bundle.
- **Keep the attribution the license requires.** The copyright notices and the GPLv2 text stay.

Using the name or the mark for a hosted service, a distribution or a commercial offering needs written
permission.

---

## Code of Conduct

All participants in this project are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before contributing.

---

## Questions?

If you have questions about contributing, open an issue in the [Issues](https://github.com/Developer-Pat/Cogitate/issues) tab.
