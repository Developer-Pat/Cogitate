---
title: Developer Scripts Guide
type: atlas-devnote
category: api
order: 3
confidence: stub
updated: 2026-08-10
tags: [type/dev-notes, domain/api]
---

# Developer Scripts Guide

Maintenance/utility scripts under scripts/ (core/, maintenance/):

- **scripts/core/check_atlas_validation.py** — wiki/ link +
  structure gate
- **scripts/core/check_dangling_links.py** — every markdown link
  resolves (file-relative or root-relative, code spans skipped)
- **scripts/core/check_agent_health.py** — agent health scan
  (honors health_dismissed_at)
- **scripts/core/backup_db.py** — DB backup → backups/<ts>/
- **scripts/core/make_clean_tar.py** — clean project tar.gz →
  ~/Cogitate-cleaned-<date>.tar.gz (~15M, excludes venv/
  node_modules/caches/logs/DBs). Archive frequently now that
  archives are small; older tarballs move to
  <external-drive>/TarZips/ (the external backup drive).
- **scripts/core/seed_monitor_templates.py** — idempotent seed
  of the monitor workflow family (rss-monitor + market-watch
  templates + hourly/5-min triggers).
- **scripts/core/sweep.py** — post-change verification sweep
- **scripts/bench/run_bench.py** — THE BENCH: issues the fixed job
  set (`scripts/bench/jobs/*.json`) through the app's own chat
  endpoint and judges it (tokens, peak prompt, calls, fetched chars,
  pass/fail). Real paid turns, so it announces its cost and needs
  `--go`; `--list` and `--check-fixtures` are free.
- **local/scripts/file_roller.py** — session file rolling

## Script catalog (current)

**Core (scripts/core/)**:
- `sweep.py` — post-change verification sweep (backend)
- `gen_api_atlas.py` — API Atlas generator (openapi.json → pages)
- `backfill_wiki_tags.py` — idempotent tag backfill
- `check_atlas_validation.py` — atlas validator (frontmatter,
  wikilinks, stale names, mermaid)
- `check_dangling_links.py` — markdown links that point at nothing
  (`--enforce` = gate)
- `backup_db.py` — DB backup to backups/<ts>/

**Bench (scripts/bench/)**: `run_bench.py` — THE BENCH driver:
issues the fixed job set through the app's chat endpoint, collects
the turn's own numbers and judges the mechanical check. `--go` is
the consent to spend.

**Local (local/scripts/)**: `file_roller.py` — session-file
rolling (status_report/session_plan archives).

> The full script catalog lives in
> [[docs/script-catalog|Script Catalog]] — this page covers the
> dev-notes view; the split is: catalog = inventory, this page =
> usage notes.
