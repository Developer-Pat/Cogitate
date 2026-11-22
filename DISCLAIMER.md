# Disclaimer — EXTREME ALPHA WARE. Use at your own risk.

**Cogitate is extreme alpha ware.** It is experimental, it is a work in progress, and it contains known bugs. It is
published mid-build so the work can be followed, tested and argued with — not because it is ready to operate
anything that matters.

## What that means in practice

- **It will break, and it can lose work.** The database, agent workspaces, saved macros and session history have no
  backup or migration guarantee. `alembic` cannot rebuild this schema from scratch, and resetting an installation
  is a reset, not a repair.
- **Agents take actions.** They run tools, write files in their own workspaces, and call model providers. Tool
  permissions exist and are enforced; they are not a security boundary.
- **It spends real money.** A configured cloud provider bills per call, and turns, titles, summaries and workflows
  all make calls. Nothing here estimates or caps that cost for you.
- **It has not been security-audited.** The repository is public for transparency, not as a claim of safety. An
  installation has no authentication, no TLS and no reverse proxy — never expose one to a network you do not
  control.
- **There is no support promise.** Issues and reports are welcome and read when time allows. There is no release
  schedule, no SLA, and no compatibility guarantee between versions: a new artifact can change behaviour, schema
  or configuration without a migration path.
- **Some of it is deliberately unfinished.** Where a feature is absent, the app is meant to say so rather than
  pretend — a missing capability, no embedding model, no speech engine — but absences are still absences.

## No warranty

Cogitate is distributed under the **GNU General Public License, version 2**, without any warranty, express or
implied, including the warranties of merchantability and fitness for a particular purpose — see `LICENSE`
(sections 15–17) and `NOTICE`. Nothing in this file adds to or subtracts from that licence.

**If you need software that must not fail, this is not it.**

*Use it at your own risk.*
