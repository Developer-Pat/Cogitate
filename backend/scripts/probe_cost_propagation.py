"""The cost-propagation probe (lane 1).

Runs a small PAID workload through the sync lane and snapshots the
OpenRouter key usage before/after on a timer, to answer: how long does
spend take to appear on the account?

Why the PAID sibling: the free Ling bills $0, so a free run produces a
zero delta and proves nothing. `inclusionai/ling-3.0-flash` is the same
model on the same provider — the free/paid switch is the only variable.

Run from the repo root:
    .venv/bin/python3 backend/scripts/probe_cost_propagation.py
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.domain.pseudo_agents.spec import ChainStep, PseudoAgentSpec, invoke

PAID_MODEL = "inclusionai/ling-3.0-flash"      # the free sibling is :free
PRICE_IN, PRICE_OUT = 0.021, 0.063             # $/M, from the live catalog


def key_usage() -> dict | None:
    r = subprocess.run(['bash', '-c', '''cd <project-root> && .venv/bin/python3 -c "
import sys; sys.path.insert(0,'backend')
from app.core.config import get_settings
print(get_settings().openrouter_api_key or '')
" 2>/dev/null | tail -1'''], capture_output=True, text=True)
    key = r.stdout.strip()
    out = subprocess.run(
        ['bash', '-c', f'curl -s --max-time 10 -H "Authorization: Bearer {key}" https://openrouter.ai/api/v1/key'],
        capture_output=True, text=True,
    ).stdout
    try:
        d = json.loads(out)["data"]
        return {"usage": d.get("usage"), "daily": d.get("usage_daily"),
                "weekly": d.get("usage_weekly")}
    except Exception:
        return None


def snap(label: str) -> dict | None:
    u = key_usage()
    ts = datetime.now().strftime("%H:%M:%S")
    if u:
        print(f"  [{label}] {ts}  total={u['usage']:.8f}  daily={u['daily']:.8f}  weekly={u['weekly']:.8f}")
    return u


print("=" * 74)
print("THE COST-PROPAGATION PROBE")
print("=" * 74)

before = snap("BEFORE")

spec = PseudoAgentSpec(
    name="cost-probe",
    system_prompt=(
        "You extract YAML frontmatter tags from wiki pages. Return ONLY a "
        'JSON array of objects: [{"page": <path>, "tags": [<tags>]}]. '
        "Do not add prose."
    ),
    chain=(
        ChainStep(provider="openrouter", model=PAID_MODEL,
                  base_url="https://openrouter.ai/api/v1", has_api_key=True,
                  api_key_setting="openrouter_api_key"),
    ),
    temperature=0.0,
    max_tokens=4000,
)

# 3 worker-shaped calls (the trickle's two batches + one more) + 1 boss
pages = [
    ("wiki/dev-notes/known-issues.md", "- title: Known Issues\n  tags: [type/devnote, domain/dev-notes]\n"),
    ("wiki/atlas/workflows/tag-survey-fanout.md", "- title: The Tag Survey\n  tags: [type/devnote, domain/workflows]\n"),
    ("wiki/concepts/cognitive-profiles.md", "- title: Cognitive Profiles\n  tags: [profile, pipeline]\n"),
]

total_in = total_out = 0
t0 = time.monotonic()
for i, (p, c) in enumerate(pages, 1):
    prompt = f'--- {p} ---\n{c[:500]}'
    r = invoke(spec, prompt)
    u = r.usage or {}
    total_in += u.get("input_tokens") or 0
    total_out += u.get("output_tokens") or 0
    print(f"  call {i}: {r.served_by}  in={u.get('input_tokens')} out={u.get('output_tokens')}")

# the boss-shaped call
r = invoke(spec, "Consolidate these tags: [type/devnote, profile, pipeline]. Return JSON.")
u = r.usage or {}
total_in += u.get("input_tokens") or 0
total_out += u.get("output_tokens") or 0
print(f"  boss : {r.served_by}  in={u.get('input_tokens')} out={u.get('output_tokens')}")
elapsed = time.monotonic() - t0

expected = (total_in / 1e6) * PRICE_IN + (total_out / 1e6) * PRICE_OUT
print()
print(f"  the workload: 4 calls in {elapsed:.1f}s")
print(f"  tokens: in {total_in}  out {total_out}")
print(f"  EXPECTED cost at ${PRICE_IN}/${PRICE_OUT} per M: ${expected:.8f}")
print()
print("  ── the propagation watch ──")
delays = [0, 15, 30, 60, 120, 180]
t_start = time.monotonic()
for d in delays:
    target = t_start + d
    while time.monotonic() < target:
        time.sleep(1)
    u = snap(f"+{d}s")
    if u and before and u["usage"] and before["usage"]:
        delta = u["usage"] - before["usage"]
        print(f"           delta={delta:.8f}  "
              f"({'MATCHES the expectation' if abs(delta - expected) < max(expected*0.5, 1e-6) and delta > 0 else 'not yet / differs'})")
