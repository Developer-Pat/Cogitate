"""Probe the pseudo-agent specs end to end (the trickle-style test).

Runs the real catalog specs against a tiny input and reports which chain
step served each call. Run from the repo root so Settings finds the .env:

    .venv/bin/python3 backend/scripts/probe_pseudo_agent.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the backend root

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.core.config import get_settings
from app.domain.pseudo_agents import CATALOG, PseudoAgentError, invoke

s = get_settings()
print("keys:", {"openrouter": bool(s.openrouter_api_key), "deepseek": bool(s.deepseek_api_key)})
print()
for name, spec in CATALOG.items():
    print(f"=== {spec.describe()}")
print()

WORKER_PROMPT = """--- wiki/test-page.md ---
---
title: A Test Page
tags: [type/devnote, domain/workflows, status/active]
---
Some body text.
--- wiki/other.md ---
---
title: No Tags Here
---
Just prose."""

BOSS_PROMPT = """TAG COUNTS: {'type/devnote': 40, 'domain/workflows': 12, 'type/dev-note': 3}
MESSY VARIANTS: {'type/dev-note': 'type/devnote'}
PAGES WITH NO TAGS: ['wiki/other.md']
NON-NAMESPACED (junk): ['misc', 'todo']
Propose the consolidation."""

for name, prompt in (("tag-worker", WORKER_PROMPT), ("tag-boss", BOSS_PROMPT)):
    spec = CATALOG[name]
    print(f"--- {name}")
    try:
        r = invoke(spec, prompt)
        print(f"    served by: {r.served_by}  ({r.elapsed}s, degraded={r.degraded})")
        for a in r.attempts:
            status = "OK" if a["ok"] else f"FAILED: {str(a.get('error'))[:80]}"
            print(f"      step {a['step']} {a['provider']}/{Path(a['model']).name}: {status} ({a['seconds']}s)")
        print(f"    output: {r.text.strip()[:220]!r}")
    except PseudoAgentError as e:
        print(f"    ALL FAILED: {e}")
    print()
