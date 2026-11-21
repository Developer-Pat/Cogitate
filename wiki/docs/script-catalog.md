---
title: Script Catalog
type: atlas-docs
path: wiki/docs/script-catalog.md
confidence: medium
updated: 2026-11-21
tags: [type/docs, domain/docs]
---

# Script Catalog

Every developer script in `scripts/` and `backend/scripts/`, generated from the
scripts themselves: **Purpose** is the file's own module docstring, **Invocation**
is its documented `Usage:` line or the project default for that file type.

Regenerate with `python3 scripts/dev/generate_script_catalog.py`; `--check`
fails when the page is stale.

**107 scripts** in 10 directories.

---

## Overview

| Directory | What lives there | Scripts |
|-----------|------------------|--------:|
| `scripts/analysis/` | Trace and log analysis, metric collection. | 10 |
| `scripts/` | Top-level verification helpers. | 2 |
| `scripts/bench/` | THE BENCH: the fixed job set and its driver. | 1 |
| `scripts/core/` | Seeding, RAG ingestion, backup, export, sweep, docs. | 33 |
| `scripts/dev/` | Developer tools: metrics, codemods, API limit probes. | 7 |
| `scripts/diagnostics/` | Health checks, model probes, conflict detection. | 3 |
| `scripts/maintenance/` | Migrations, cleanup, database recovery. | 9 |
| `scripts/spikes/` | Throwaway experiments kept for the record. | 1 |
| `scripts/testing/` | Test execution, suites, gates, provider probes. | 18 |
| `backend/scripts/` | Backend-internal: tools, schema, docs DB, workflows. | 23 |

---

## 1. `scripts/analysis/`

Trace and log analysis, metric collection.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`analyze_logs.py`](scripts/analysis/analyze_logs.py) | Log Analysis Script for Cogitate — Analyzes logs from the backend API to identify: | `uv run python scripts/analysis/analyze_logs.py` |
| [`analyze_session_lifecycle_traces.py`](scripts/analysis/analyze_session_lifecycle_traces.py) | Session Lifecycle Debug Trace Analyzer — Analyzes SessionLifecycleDebug traces to identify the root cause of duplicate session issues. Focus Areas: | `uv run python scripts/analysis/analyze_session_lifecycle_traces.py` |
| [`analyze_traces.py`](scripts/analysis/analyze_traces.py) | Trace Analysis Script — Analyzes captured trace logs to identify patterns, timing issues, and race conditions. | `uv run python scripts/analysis/analyze_traces.py` |
| [`automated_trace_workflow.py`](scripts/analysis/automated_trace_workflow.py) | Automated Trace Workflow - Chat Flow Debugging — This script automates the process of: | `uv run python scripts/analysis/automated_trace_workflow.py` |
| [`automated_trace_workflow_nobrowser.py`](scripts/analysis/automated_trace_workflow_nobrowser.py) | Fully Automated Trace Workflow - No Browser Required — This version: | `uv run python scripts/analysis/automated_trace_workflow_nobrowser.py` |
| [`comment_traces.py`](scripts/analysis/comment_traces.py) | Comment out traceService.trace() calls in TypeScript files. — This script finds all traceService.trace() calls and comments them out, preserving them for future debugging while disabling… | `uv run python scripts/analysis/comment_traces.py` |
| [`compare_trace_flows.py`](scripts/analysis/compare_trace_flows.py) | Compare trace flows between successful and failed chat attempts. | `uv run python scripts/analysis/compare_trace_flows.py` |
| [`fetch_and_analyze_traces.py`](scripts/analysis/fetch_and_analyze_traces.py) | Quick Trace Fetch & Analyze — Fetches traces from the API and analyzes them immediately. | `uv run python scripts/analysis/fetch_and_analyze_traces.py` |
| [`trace_preflight.py`](scripts/analysis/trace_preflight.py) | Pre-flight checks for trace workflow. — Ensures all prerequisites are met before running automated trace workflow. | `uv run python scripts/analysis/trace_preflight.py` |
| [`verify_incremental_ingestion.py`](scripts/analysis/verify_incremental_ingestion.py) | Verify incremental ingestion acceptance criteria for both ingest scripts. | `uv run python scripts/analysis/verify_incremental_ingestion.py` |

---

## 2. `scripts/`

Top-level verification helpers.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`verify_memory_persistence.py`](scripts/verify_memory_persistence.py) | Automated verification of agent memory persistence. | `uv run python scripts/verify_memory_persistence.py` |
| [`verify_test_harness_cleanup.py`](scripts/verify_test_harness_cleanup.py) | Verify the test harness reports (and stops) its own installation leaks. | `uv run python scripts/verify_test_harness_cleanup.py` |

---

## 3. `scripts/bench/`

THE BENCH: the fixed job set and its driver.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`run_bench.py`](scripts/bench/run_bench.py) | THE BENCH — the driver: issue each job through the app's own endpoint, collect, judge. | `uv run python scripts/bench/run_bench.py` |

---

## 4. `scripts/core/`

Seeding, RAG ingestion, backup, export, sweep, docs.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`activate_exa.py`](scripts/core/activate_exa.py) | Activate Exa — the one command behind the install skill and the docs. — Exa ships INCLUDED and INACTIVE. | `uv run python scripts/core/activate_exa.py` |
| [`archive_atlas.sh`](scripts/core/archive_atlas.sh) | Moves the current Application Atlas to the archive directory. Preserves assessment.md and plan/ for reference during the rebuild. | `./scripts/core/archive_atlas.sh` |
| [`backfill_wiki_tags.py`](scripts/core/backfill_wiki_tags.py) | Backfill tags: for every wiki .md WITHOUT tags, derive from — frontmatter + path and append a flow-style tags: line. | `uv run python scripts/core/backfill_wiki_tags.py` |
| [`backup_db.py`](scripts/core/backup_db.py) | Database backup script — a DEVELOPMENT UTILITY, not a release feature. | `uv run python scripts/core/backup_db.py` |
| [`bench_worker_llm.py`](scripts/core/bench_worker_llm.py) | Worker-LLM quality benchmark: how well the tag-survey worker LLMs extract, not merely whether they | `python scripts/core/bench_worker_llm.py` |
| [`check_agent_health.py`](scripts/core/check_agent_health.py) | Agent Provider Health Check — validate every agent's provider/model. — Recurring issue: agents can reference a deprecated or non-existent provider/model (e.g. | `uv run python scripts/core/check_agent_health.py` |
| [`check_atlas_validation.py`](scripts/core/check_atlas_validation.py) | Atlas Validation Check — wiki/atlas integrity gate. — Validates the atlases (wiki/atlas/ — ui + api) against the codebase and their own link conventions. | `uv run python scripts/core/check_atlas_validation.py` |
| [`check_commit_references.py`](scripts/core/check_commit_references.py) | Gate/Census: commit numbers written into the tree. — A commit number is a citation only while the history is there — and a shipped repository's past can be replaced by a flatten: one… | `uv run python scripts/core/check_commit_references.py` |
| [`check_dangling_links.py`](scripts/core/check_dangling_links.py) | Gate: every markdown link in the tree resolves. — A link to a file the repository does not carry is a dead end for whoever follows it — and the audience is not hypothetical: the… | `uv run python scripts/core/check_dangling_links.py` |
| [`check_stale_references.py`](scripts/core/check_stale_references.py) | Gate: the tree stops naming features that no longer exist. — Two patterns, both left over from removals: | `python3 scripts/core/check_stale_references.py [--verbose]` |
| [`exa_audit_probe.py`](scripts/core/exa_audit_probe.py) | The Exa audit live run: Exa uses the audit-consistency tool and reports the verified system state. | `uv run python scripts/core/exa_audit_probe.py` |
| [`exa_isolation_probe.py`](scripts/core/exa_isolation_probe.py) | Isolation probe for the Exa home. — The isolation is STATE-BASED by design: the external agent runs with HERMES_HOME=<project>/.hermes (its own home — memories/skills/ config/session state)… | `uv run python scripts/core/exa_isolation_probe.py` |
| [`exa_probe.py`](scripts/core/exa_probe.py) | Exa Probe Harness — the re-runnable Exa capability battery. — A probe that finds a bug has to become code, not a memory: a throwaway run leaves a result nobody can reproduce. | `uv run python scripts/core/exa_probe.py` |
| [`exa_skill_probe.py`](scripts/core/exa_skill_probe.py) | Skill probe: the seed skills are visible to the agent and usable. | `uv run python scripts/core/exa_skill_probe.py` |
| [`gen_api_atlas.py`](scripts/core/gen_api_atlas.py) | Generate API-Atlas skeleton pages from the live OpenAPI spec. — Reads /openapi.json (or a cached copy), groups paths by domain (after /api/v1/), and writes… | `uv run python scripts/core/gen_api_atlas.py` |
| [`gen_page_map.py`](scripts/core/gen_page_map.py) | Generate the page map from the frontend's own route table. — WHY THIS EXISTS The `open-page` tool's enum has to BE the app's real pages. | `uv run python scripts/core/gen_page_map.py` |
| [`ingest_code_for_rag.py`](scripts/core/ingest_code_for_rag.py) | Ingest source code files into the Code RAG vector index. — Discovers source files in configured directories (``backend/``, ``frontend/src/``, ``scripts/``), chunks them with language-aware… | `uv run python scripts/core/ingest_code_for_rag.py` |
| [`ingest_docs_for_rag.py`](scripts/core/ingest_docs_for_rag.py) | Ingest documentation files into the RAG vector index. — Discovers markdown files in configured documentation directories, chunks them with heading-aware splitting, computes embeddings via… | `uv run python scripts/core/ingest_docs_for_rag.py` |
| [`load_tool_tests_macros.py`](scripts/core/load_tool_tests_macros.py) | Load Tool Tests 00 Macro Sets into Database — Creates 5 macro sets for tool testing under the "Tool Tests 00" meta topic. | `uv run python scripts/core/load_tool_tests_macros.py` |
| [`make_clean_tar.py`](scripts/core/make_clean_tar.py) | Create a clean tar.gz snapshot of the Cogitate project. — Excludes regenerable/bloat content (venvs, node_modules, caches, logs, DBs, backups, env files, archives) so the archive is pure… | `python3 scripts/core/make_clean_tar.py Cockpit-source` |
| [`migrate_file_agents_to_db.py`](scripts/core/migrate_file_agents_to_db.py) | Migration script: convert file-based agents to DB-backed agent packages. | `uv run python scripts/core/migrate_file_agents_to_db.py` |
| [`provision_exa_home.py`](scripts/core/provision_exa_home.py) | Provision the external agent's private Hermes home (the CLI shim). | `uv run python scripts/core/provision_exa_home.py` |
| [`provision_expertise_tools.py`](scripts/core/provision_expertise_tools.py) | Provision the expertise tools to the Cogitate agents. — The repurpose: the capabilities built for Exa serve the framework's OWN agents — one capability, two consumers. | `uv run python scripts/core/provision_expertise_tools.py` |
| [`scaffold_atlas.py`](scripts/core/scaffold_atlas.py) | UI Atlas Scaffolder: a stub doc for every frontend source file the atlas does not claim. | `uv run python scripts/core/scaffold_atlas.py` |
| [`seed_agent_images.py`](scripts/core/seed_agent_images.py) | Seed curated agent images into the runtime store (idempotent). — The curated set lives git-tracked at assets/agent-images/ (the canonical home). | `uv run python scripts/core/seed_agent_images.py` |
| [`seed_agent_packages.py`](scripts/core/seed_agent_packages.py) | Seed script: populate the frontend_agent_packages table with test/dummy agents. | `uv run python scripts/core/seed_agent_packages.py` |
| [`seed_monitor_templates.py`](scripts/core/seed_monitor_templates.py) | Seed the monitor workflow family: templates + triggers. — Idempotent — skips rows that already exist (safe to re-run). | `uv run python scripts/core/seed_monitor_templates.py` |
| [`seed_system_audit_template.py`](scripts/core/seed_system_audit_template.py) | Seed the system-audit workflow template. — Idempotent — skips the row if it exists (safe to re-run). | `uv run python scripts/core/seed_system_audit_template.py` |
| [`setup_models.py`](scripts/core/setup_models.py) | The setup step — offer the VALUES a fresh install does not decide for you. | `uv run python scripts/core/setup_models.py` |
| [`sweep.py`](scripts/core/sweep.py) | Sweep Script — Comprehensive Error & Warning Detection — Thin entry point that delegates to the sweep package CLI. | `uv run python scripts/core/sweep.py` |
| [`test_nucleus.py`](scripts/core/test_nucleus.py) | Quick verification script: test Nucleus harness with seeded agents. | `uv run python scripts/core/test_nucleus.py` |
| [`update_help_docs.py`](scripts/core/update_help_docs.py) | Update in-app help documents to reflect the current UI state. — Updates the `data/cogitate_docs_en.db` database with accurate help content for Dashboard, Agent Chat, Sessions, and Logs… | `uv run python scripts/core/update_help_docs.py` |
| [`verify_readiness.py`](scripts/core/verify_readiness.py) | The install's acceptance check — one readiness sentence, from the one verdict. | `uv run python scripts/core/verify_readiness.py` |

---

## 5. `scripts/dev/`

Developer tools: metrics, codemods, API limit probes.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`check-openrouter-limits.js`](scripts/dev/check-openrouter-limits.js) | (no module docstring) | `node scripts/dev/check-openrouter-limits.js` |
| [`check_mermaid_fences.mjs`](scripts/dev/check_mermaid_fences.mjs) | (no module docstring) | `node scripts/dev/check_mermaid_fences.mjs` |
| [`fix_ts6133.py`](scripts/dev/fix_ts6133.py) | Bulk-fix TS6133 (unused declarations) errors across the frontend. — Reads `npx tsc -b` output from stdin and applies mechanical fixes. | `uv run python scripts/dev/fix_ts6133.py` |
| [`generate_env_example.py`](scripts/dev/generate_env_example.py) | Generate `.env.example` from the settings the app actually reads. | `uv run python scripts/dev/generate_env_example.py` |
| [`generate_factsheet_metrics.py`](scripts/dev/generate_factsheet_metrics.py) | Cogitate Factsheet Metrics Generator — Collects current project metrics (file counts, LOC, largest files, tech stack, database info) and outputs a timestamped markdown report. | `uv run python scripts/dev/generate_factsheet_metrics.py` |
| [`generate_script_catalog.py`](scripts/dev/generate_script_catalog.py) | Generate the script catalog from the scripts themselves. — `wiki/docs/script-catalog.md` is a catalogue, and a catalogue rots one row at a time: rows for scripts that were deleted, rows… | `uv run python scripts/dev/generate_script_catalog.py` |
| [`vite-supervisor.sh`](scripts/dev/vite-supervisor.sh) | THE VITE SUPERVISOR: wraps the dev server — on death it LOGS the exit code + the tail of the output, then AUTO-RESTARTS with an exponential backoff. | `./scripts/dev/vite-supervisor.sh` |

---

## 6. `scripts/diagnostics/`

Health checks, model probes, conflict detection.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`example_triggers.py`](scripts/diagnostics/example_triggers.py) | Example triggers for testing and demonstration. — This script creates example triggers to demonstrate the event-driven trigger system: | `uv run python scripts/diagnostics/example_triggers.py` |
| [`langfuse_sink.py`](scripts/diagnostics/langfuse_sink.py) | Langfuse rung 1 — the local sink: does the payload our code builds cross the wire? | `uv run python scripts/diagnostics/langfuse_sink.py` |
| [`verify_tool_slug_conflicts.py`](scripts/diagnostics/verify_tool_slug_conflicts.py) | Verify that no built-in tool has slug/config argument conflicts with — ToolRegistry.execute_tool(tool_slug, tool_config, arguments). | `uv run python scripts/diagnostics/verify_tool_slug_conflicts.py` |

---

## 7. `scripts/maintenance/`

Migrations, cleanup, database recovery.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`cleanup_test_agents.py`](scripts/maintenance/cleanup_test_agents.py) | Cleanup Test Agents Script — Deletes test agents from the database while preserving: | `uv run python scripts/maintenance/cleanup_test_agents.py` |
| [`fix_datetime_utcnow.py`](scripts/maintenance/fix_datetime_utcnow.py) | Fix datetime.utcnow() deprecation across the backend. — Replaces: | `uv run python scripts/maintenance/fix_datetime_utcnow.py` |
| [`fix_eslint_any.mjs`](scripts/maintenance/fix_eslint_any.mjs) | (no module docstring) | `node scripts/maintenance/fix_eslint_any.mjs` |
| [`fix_pydantic_v2.py`](scripts/maintenance/fix_pydantic_v2.py) | Automated fix for Pydantic V2 deprecations. — Replaces: | `uv run python scripts/maintenance/fix_pydantic_v2.py` |
| [`migrate_from_backup.py`](scripts/maintenance/migrate_from_backup.py) | Database Recovery Migration Script — Migrates data from backup database to newly created schema. Handles schema differences between backup and current models. | `uv run python scripts/maintenance/migrate_from_backup.py` |
| [`prepend_date.py`](scripts/maintenance/prepend_date.py) | Prepend Date Script — Prepends a machine-readable date (YYYY-MM-DD) to filenames based on file creation time, so files collate chronologically when sorted alphabetically. | `uv run python scripts/maintenance/prepend_date.py` |
| [`purge_orphan_agent_refs.py`](scripts/maintenance/purge_orphan_agent_refs.py) | Find — and, on request, clear — rows that name an agent that no longer exists. | `uv run python scripts/maintenance/purge_orphan_agent_refs.py` |
| [`recover_database.sh`](scripts/maintenance/recover_database.sh) | Database Recovery Execution Script Automates the complete database recovery process: 1. Backs up corrupted database 2. Creates working copy of backup 3. | `./scripts/maintenance/recover_database.sh` |
| [`verify_recovery.py`](scripts/maintenance/verify_recovery.py) | Database Recovery Verification Script — Verifies that the database recovery was successful by checking: | `uv run python scripts/maintenance/verify_recovery.py` |

---

## 8. `scripts/spikes/`

Throwaway experiments kept for the record.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`acp_spike.py`](scripts/spikes/acp_spike.py) | ACP spike — prove the full handshake works from a subprocess. — Protocol (JSON-RPC 2.0 over stdio): | `uv run python scripts/spikes/acp_spike.py` |

---

## 9. `scripts/testing/`

Test execution, suites, gates, provider probes.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`check_test_catalog.py`](scripts/testing/check_test_catalog.py) | The test-catalog checker - the CLI for ``app.domain.testing.catalog_check``. | `uv run python scripts/testing/check_test_catalog.py` |
| [`events_plugin.py`](scripts/testing/events_plugin.py) | The test-EVENTS plugin — the live record of a run. — WHY A PLUGIN AT ALL. | `uv run python scripts/testing/events_plugin.py` |
| [`export_test_fixtures.py`](scripts/testing/export_test_fixtures.py) | Export the reference rows the suite asserts on, as data the tree can carry. | `uv run python scripts/testing/export_test_fixtures.py` |
| [`generate_issues_report.py`](scripts/testing/generate_issues_report.py) | Issues Report Generator — run all static analysis tools and produce a — timestamped markdown report of current errors and warnings across the monorepo. | `uv run python scripts/testing/generate_issues_report.py` |
| [`generate_test_report.py`](scripts/testing/generate_test_report.py) | Test Report Generator — run both suites and produce a timestamped markdown report. | `uv run python scripts/testing/generate_test_report.py` |
| [`precommit_path_checks.py`](scripts/testing/precommit_path_checks.py) | The path gates, as a pre-commit entry point. — Runs the checks the sweep already owns, so a commit cannot introduce a path that escapes the resolver, names a specific machine, or names a… | `uv run python scripts/testing/precommit_path_checks.py` |
| [`run_tests.py`](scripts/testing/run_tests.py) | The test runner — the test-sweeps redesign's harness. — Runs the backend test GROUPS (the functional partitions — the directory layout) and writes the run's artifacts (the policy: "the hard… | `uv run python scripts/testing/run_tests.py` |
| [`scan_objects_for_secrets.py`](scripts/testing/scan_objects_for_secrets.py) | Gate: no secret reaches a git object. — Scans EVERY blob in the repository — not just the checked-out files — because a flatten publishes the tree, but a leak is usually a commit that was… | `python3 scripts/testing/scan_objects_for_secrets.py [--verbose]` |
| [`simple_chat_test.py`](scripts/testing/simple_chat_test.py) | Simple direct test of chat endpoints - no streaming complexity. | `uv run python scripts/testing/simple_chat_test.py` |
| [`test_json_adapter_workflow.py`](scripts/testing/test_json_adapter_workflow.py) | End-to-end test script for the JSON adapter (Agent Chat API) workflow. | `uv run python scripts/testing/test_json_adapter_workflow.py` |
| [`test_kvstore_session_isolation.py`](scripts/testing/test_kvstore_session_isolation.py) | Verify KVStoreMemoryManager session isolation. — Tests that session_id scoping works correctly: | `uv run python scripts/testing/test_kvstore_session_isolation.py` |
| [`test_litellm_direct.py`](scripts/testing/test_litellm_direct.py) | Direct LiteLLM test - bypass the backend entirely. — Tests if LiteLLM can connect to the providers. | `uv run python scripts/testing/test_litellm_direct.py` |
| [`test_ollama_direct.py`](scripts/testing/test_ollama_direct.py) | Simple Ollama test - direct HTTP call, no LiteLLM. | `uv run python scripts/testing/test_ollama_direct.py` |
| [`test_openrouter_direct.py`](scripts/testing/test_openrouter_direct.py) | Test OpenRouter API directly - no LiteLLM. | `uv run python scripts/testing/test_openrouter_direct.py` |
| [`test_tool_integration.py`](scripts/testing/test_tool_integration.py) | Tool Integration Test Script — Tests direct LLM calls with tools via OpenRouter API. Verifies that: | `uv run python scripts/testing/test_tool_integration.py` |
| [`test_tools_direct.py`](scripts/testing/test_tools_direct.py) | Direct Tool Testing Script - Session #33 — Test tools directly without LLM to debug tool execution issues. Removes LLM from the debug loop for faster, more reliable testing. | `uv run python scripts/testing/test_tools_direct.py` |
| [`test_tools_quick.py`](scripts/testing/test_tools_quick.py) | Quick Tool Test - Uses backend's existing OpenRouter configuration — This script tests tool integration using the same configuration as the backend. | `uv run python scripts/testing/test_tools_quick.py` |
| [`verify_flat_tree.sh`](scripts/testing/verify_flat_tree.sh) | Verify a flattened tree the way a stranger meets it. Usage: scripts/testing/verify_flat_tree.sh /path/to/flat-tree Checks, in order, and none of them needs this… | `./scripts/testing/verify_flat_tree.sh` |

---

## 10. `backend/scripts/`

Backend-internal: tools, schema, docs DB, workflows.

| Script | Purpose | Invocation |
|--------|---------|------------|
| [`alembic_roundtrip.py`](backend/scripts/alembic_roundtrip.py) | C3 gate 2 — the migration chain builds the same schema as `create_all`. | `python scripts/alembic_roundtrip.py` |
| [`apply_tag_proposals.py`](backend/scripts/apply_tag_proposals.py) | The tag-consolidation APPLIER — the wet run (W1). — Reads the boss's consolidation report and either shows what it WOULD change (`--dry-run`, the default) or makes the changes (`--apply`). | `uv run python backend/scripts/apply_tag_proposals.py` |
| [`audit_agent_schema.py`](backend/scripts/audit_agent_schema.py) | THE CLASS AUDIT: model columns vs the write schemas. — The image bug was not one missing field — it was the PATTERN: a column exists on the model, the schema omits it, and the endpoint… | `uv run python backend/scripts/audit_agent_schema.py` |
| [`backup_database.py`](backend/scripts/backup_database.py) | Database backup utility for cogitate. — Creates timestamped backups of the SQLite database before schema modifications. | `uv run python backend/scripts/backup_database.py` |
| [`check_docs_database.py`](backend/scripts/check_docs_database.py) | CRITICAL: Synchronize documents database. — This script ensures the documents table exists in the correct database and migrates any data if needed. | `uv run python backend/scripts/check_docs_database.py` |
| [`clear_sessions.py`](backend/scripts/clear_sessions.py) | Clear all chat sessions and messages from the database. | `uv run python backend/scripts/clear_sessions.py` |
| [`delegate_sse_fetch.py`](backend/scripts/delegate_sse_fetch.py) | Helper script to make a synchronous HTTP POST to an SSE chat stream. | `uv run python backend/scripts/delegate_sse_fetch.py` |
| [`describer_dryrun.py`](backend/scripts/describer_dryrun.py) | The describer DRY RUN — generate a line per test module, judge it blind, compare. | `uv run python backend/scripts/describer_dryrun.py` |
| [`diagnose_error.py`](backend/scripts/diagnose_error.py) | Error Diagnostic Utility. — Captures and displays detailed error information from LiteLLM errors. Use this to understand exactly what went wrong with provider requests. | `uv run python backend/scripts/diagnose_error.py` |
| [`estimate_workflow_cost.py`](backend/scripts/estimate_workflow_cost.py) | The workflow cost estimator — the prototype (D2). — Takes a corpus + the worker/boss prompt shapes + live OpenRouter pricing, and prints a per-step estimate. | `uv run python backend/scripts/estimate_workflow_cost.py` |
| [`init_docs_db.py`](backend/scripts/init_docs_db.py) | Initialize the Document Management System database. — Creates the cogitate_docs_en.db database with all tables, indexes, triggers, and FTS5 full-text search support. | `uv run python backend/scripts/init_docs_db.py` |
| [`make_baseline.py`](backend/scripts/make_baseline.py) | Generate the single baseline revision from Base.metadata. — Runs alembic's autogenerate against a THROWAWAY EMPTY database, so the revision it writes is the whole schema as `create_table`… | `python scripts/make_baseline.py` |
| [`probe_cost_propagation.py`](backend/scripts/probe_cost_propagation.py) | The cost-propagation probe (lane 1). — Runs a small PAID workload through the sync lane and snapshots the OpenRouter key usage before/after on a timer, to answer: how long does spend take… | `uv run python backend/scripts/probe_cost_propagation.py` |
| [`probe_describer.py`](backend/scripts/probe_describer.py) | THE DESCRIBER EXPERIMENT — can a bare LLM write a true test description? | `uv run python backend/scripts/probe_describer.py` |
| [`probe_open_page.py`](backend/scripts/probe_open_page.py) | (no module docstring) | `uv run python backend/scripts/probe_open_page.py` |
| [`probe_pseudo_agent.py`](backend/scripts/probe_pseudo_agent.py) | Probe the pseudo-agent specs end to end (the trickle-style test). — Runs the real catalog specs against a tiny input and reports which chain step served each call. | `uv run python backend/scripts/probe_pseudo_agent.py` |
| [`probe_tag_survey_nodes.py`](backend/scripts/probe_tag_survey_nodes.py) | Exercise the rewired tag-survey nodes (the pseudo-agent chain). — Run from the repo root so Settings finds the .env: .venv/bin/python3 backend/scripts/probe_tag_survey_nodes.py | `uv run python backend/scripts/probe_tag_survey_nodes.py` |
| [`render_catalog_scan.py`](backend/scripts/render_catalog_scan.py) | Render the description scan — every module and its rendered description, one page. | `uv run python backend/scripts/render_catalog_scan.py` |
| [`rotate_logs.py`](backend/scripts/rotate_logs.py) | Log Rotation Script for Cogitate — Rotates log files to prevent disk space issues by: | `uv run python backend/scripts/rotate_logs.py` |
| [`run_tag_survey_trickle.py`](backend/scripts/run_tag_survey_trickle.py) | The tag-survey TRICKLE run (the atlas's probe config). — Runs the real graph — the rewired pseudo-agent nodes — over a bounded slice of the wiki: 2 batches of 3 files, one worker thread… | `uv run python backend/scripts/run_tag_survey_trickle.py` |
| [`schema_parity_check.py`](backend/scripts/schema_parity_check.py) | C3 gate 1 — the models can build the database the app runs on. — Builds a database from `Base.metadata.create_all` into a temp file and diffs it against the live `cogitate.db`. | `python scripts/schema_parity_check.py [--verbose]` |
| [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) | Master Tool Seeding Script — Consolidated from 9 individual scripts. — Replaces the following scripts (all deleted): | `uv run python backend/scripts/seed_all_tools.py` |
| [`seed_workspace_kit.py`](backend/scripts/seed_workspace_kit.py) | The Workspace Kit seed: the SECOND toolkit (the write/state surface). | `uv run python backend/scripts/seed_workspace_kit.py` |

---

## Consolidated scripts

Gone, and where their work went. A search for one of these names should land
somewhere useful rather than nowhere.

| Script | Disposition | Now |
|--------|-------------|-----|
| `add_duckduckgo_tool.py` | folded into `seed_all_tools.py` | [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) |
| `add_jina_reader_tool.py` | folded into `seed_all_tools.py` | [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) |
| `add_sqlite_manager_tool.py` | folded into `seed_all_tools.py` | [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) |
| `add_tavily_tool.py` | folded into `seed_all_tools.py` | [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) |
| `add_wikipedia_tool.py` | folded into `seed_all_tools.py` | [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) |
| `seed_builtin_tools.py` | folded into `seed_all_tools.py` | [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) |
| `seed_guide_dev_tools.py` | folded into `seed_all_tools.py` | [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) |
| `seed_introspection_tools.py` | folded into `seed_all_tools.py` | [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) |
| `seed_tools.py` | folded into `seed_all_tools.py` | [`seed_all_tools.py`](backend/scripts/seed_all_tools.py) |
| `seed_docs_content.py` | wrote to the wrong database path; the help docs are written by this | [`update_help_docs.py`](scripts/core/update_help_docs.py) |
| `update_tavily_tool.py` | tool config is seeded from the code registry at boot (`auto_sync_tools`) | — |
| `update_tool_arguments_schema.py` | argument schemas live in the code registry and sync at boot | — |

---

## Common run patterns

| Kind | Command |
|------|---------|
| Python, project dependencies | `uv run python scripts/...` |
| Python, standard library only | `python3 scripts/...` |
| Shell | `./scripts/...` |
| Node | `node scripts/...` |

## Notes

- Scripts that rewrite files take `--dry-run` where their docstring says so — run
  that first.
- Report generators write to `backend/reports/`, which is gitignored.
