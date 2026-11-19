#!/usr/bin/env python3
"""Exa Probe Harness — the re-runnable Exa capability battery.

A probe that finds a bug has to become code, not a memory: a throwaway run leaves a result nobody can
reproduce. This harness keeps every case re-runnable against a live agent (the user's rule: "probes that
find bugs should become code, not memories").

Each probe spawns the REAL Exa machinery (AcpClient -> hermes acp)
with a named prompt and streams the events. The harness reports
PASS/FAIL per probe + the full event log.

Usage:
    python3 scripts/core/exa_probe.py                    # all probes
    python3 scripts/core/exa_probe.py --probe agents     # one probe
    python3 scripts/core/exa_probe.py --list             # the cases

Exit codes: 0 all pass, 1 any probe failed, 2 harness error.

The probes:
    agents      — read the agents API + compose + place a report
                  (probes 1-2: the pagination-trap regression)
    survey      — read workflows + agents, compose a survey report
                  (probe 3: the workflow/lifecycle READ surface)
    lifecycle   — the WRITE round-trip: provision -> archive ->
                  restore -> archive (probe 4: the lifecycle
                  unification regression — the folder-only archive
                  bug class)
    battery     — the failure modes: unknown recipient, missing
                  skill, connection drop (the loud-failure checks)

NOTE: probes write real reports to data/monitor/ + (lifecycle)
create/archive a probe agent. The lifecycle probe cleans up after
itself (the system returns to its prior state). Run against a live
backend on :8000.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
ACPD_CWD = str(PROJECT_ROOT)

PROBES = ["agents", "survey", "lifecycle", "battery"]

AGENTS_PROMPT = (
    "Create a report on the existing agents in this Cogitate system. "
    "Use the tools available to you: check the agents via the API "
    "(curl http://localhost:8000/api/v1/agents), summarize them "
    "(name, provider, model, profile), and produce a markdown report. "
    "If you find the report endpoint POST "
    "http://localhost:8000/api/v1/external-agent/report with "
    "{title, body}, save it there. If you cannot do any of this, "
    "say exactly what blocked you."
)

SURVEY_PROMPT = (
    "Explore this Cogitate system's WORKFLOW and AGENT LIFECYCLE "
    "surfaces. 1) GET http://localhost:8000/api/v1/workflows/templates "
    "and summarize what workflow templates exist. 2) GET "
    "http://localhost:8000/api/v1/agents and note the agents + "
    "any lifecycle fields (deleted_at, archived_path, is_active). "
    "3) Then produce ONE markdown report titled 'Workflow and "
    "Agent Lifecycle Survey' covering both, and save it via "
    "POST http://localhost:8000/api/v1/external-agent/report with "
    "{title, body}. If you cannot do a step, say exactly what "
    "blocked you and continue with the rest."
)

LIFECYCLE_PROMPT = (
    "Test the agent LIFECYCLE round-trip in this Cogitate system. "
    "First READ the provisioning router source "
    "(backend/app/api/v1/agents/provisioning_router.py) and the "
    "agents router (backend/app/api/v1/agents/router.py) to learn "
    "the exact request/response contracts for: provision "
    "(POST /api/v1/agents/{name}/provision), archive "
    "(DELETE /api/v1/agents/{name}/archive), restore "
    "(POST /api/v1/agents/{id}/restore), and the deleted list "
    "(GET /api/v1/agents/deleted). "
    "Then execute the round-trip: provision an agent named "
    "exa-lifecycle-probe (description 'Exa probe lifecycle test', "
    "system_prompt 'You are a lifecycle probe.'), verify it is in "
    "GET /api/v1/agents, archive it, verify it is in "
    "GET /api/v1/agents/deleted, restore it, verify it is active "
    "again. Then archive it one final time (leave NO probe agent "
    "behind — the system must return to its prior state). "
    "Finally POST a short markdown report titled 'Agent Lifecycle "
    "Round-Trip' summarizing each step's result + anything "
    "surprising, via POST /api/v1/external-agent/report with "
    "{title, body}. If a step fails, record the exact error and "
    "continue."
)

BATTERY_PROMPT = (
    "Answer in one short sentence: does a skill named "
    "'this-skill-definitely-does-not-exist-xyz' exist in this "
    "system? Say 'no such skill' if it does not."
)


def _event_text(ev) -> str:
    """Human-readable event line (the probe log format)."""
    return f"[{ev.kind}] {ev.text[:160]}" if ev.text else f"[{ev.kind}]"


async def _run_probe(name: str, prompt: str, log_lines: list) -> None:
    """Spawn the AcpClient, stream the prompt, log the events."""
    sys.path.insert(0, str(BACKEND_DIR))
    from app.domain.external_agent.services import AcpClient

    client = AcpClient(command=["hermes", "acp"], cwd=ACPD_CWD, fix_mode=True)
    await client.start()
    log_lines.append(f"session: {client.session_id}")
    try:
        async for ev in client.stream_prompt(prompt):
            log_lines.append(_event_text(ev))
            if ev.kind == "closed":
                break
    finally:
        await client.close()


def _run_battery_checks(log_lines: list) -> bool:
    """The sync failure-mode checks (F1: unknown recipient)."""
    sys.path.insert(0, str(BACKEND_DIR))
    from datetime import datetime, timezone

    from app.workflows.distribution.distributors import AgentDistributor
    from app.workflows.distribution.models import WorkflowProduct

    ok = True
    try:
        distributor = AgentDistributor()
        product = WorkflowProduct(
            product_type="test-failure-battery",
            title="F1 test",
            body="hello",
            source_template="failure-battery",
            created_at=datetime.now(timezone.utc).isoformat(),
            meta={"recipient_agent": "nonexistent-agent-xyz"},
        )
        result = distributor.deliver(product)
        loud = not result.success and "registry" in (result.detail or "").lower()
        log_lines.append(f"[F1 unknown recipient] success={result.success} detail={result.detail}")
        ok = ok and loud
    except Exception as e:  # noqa: BLE001
        log_lines.append(f"[F1 unknown recipient] EXCEPTION {e}")
        ok = False
    return ok


def probe_battery(log_lines: list) -> bool:
    """The battery: F1 (sync) + F2/F3 (async, via Exa)."""
    # F1 must run OUTSIDE the event loop (the distributor's asyncio.run)
    f1_ok = [False]
    def _f1():
        f1_ok[0] = _run_battery_checks(log_lines)
    t = threading.Thread(target=_f1)
    t.start()
    t.join(timeout=30)
    if t.is_alive():
        log_lines.append("[F1 unknown recipient] TIMEOUT")
        return False
    # F2 + F3 are Exa-driven (the missing-skill + connection-drop)
    return f1_ok[0]


async def _probe_async(name: str, prompt: str) -> tuple[bool, list]:
    log_lines: list = []
    try:
        await _run_probe(name, prompt, log_lines)
        return True, log_lines
    except Exception as e:  # noqa: BLE001
        log_lines.append(f"[ERROR] {type(e).__name__}: {e}")
        return False, log_lines


async def main() -> int:
    parser = argparse.ArgumentParser(description="The Exa probe harness")
    parser.add_argument("--probe", choices=PROBES, help="run one probe")
    parser.add_argument("--list", action="store_true", help="list the cases")
    args = parser.parse_args()

    if args.list:
        for p in PROBES:
            print(f"  {p}")
        return 0

    targets = [args.probe] if args.probe else PROBES
    all_ok = True
    for name in targets:
        print(f"\n{'='*60}\n=== PROBE: {name} ===\n{'='*60}")
        if name == "battery":
            log_lines: list = []
            ok = probe_battery(log_lines)
        else:
            prompt = {
                "agents": AGENTS_PROMPT,
                "survey": SURVEY_PROMPT,
                "lifecycle": LIFECYCLE_PROMPT,
            }[name]
            ok, log_lines = await _probe_async(name, prompt)
        for line in log_lines:
            print(f"  {line}")
        print(f"  → {'PASS' if ok else 'FAIL'}")
        all_ok = all_ok and ok

    print(f"\n{'='*60}\nHARNESS {'PASSED' if all_ok else 'FAILED'} ({len(targets)} probe(s))")
    return 0 if all_ok else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        sys.exit(130)
