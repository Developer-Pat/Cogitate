"""Exercise the rewired tag-survey nodes (the pseudo-agent chain).

Run from the repo root so Settings finds the .env:
    .venv/bin/python3 backend/scripts/probe_tag_survey_nodes.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from typing import Any, cast

# THE TOOL REGISTRATION (the probe runs outside the app): the nodes read
# files through the file-info tool, so the default registry must be built
# first — the app does this at startup.
from app.domain.tools.registry import init_default_registry

init_default_registry()

from app.workflows.nodes.tag_survey_nodes import tag_extract_worker_node, boss_node

print("=== THE WORKER NODE (a 2-file batch, through the pseudo-agent chain)")
state = {
    "outputs": {
        "file_list": [
            "wiki/atlas/workflows/tag-survey-fanout.md",
            "wiki/dev-notes/known-issues.md",
        ]
    }
}
out = tag_extract_worker_node(cast(Any, state))
meta = out.get("outputs", {}).get("worker_meta", {})
rows = out.get("outputs", {}).get("tag_rows", [])
print("  worker_meta:", meta)
print(f"  rows: {len(rows)}")
for r in rows[:3]:
    print("   ", {k: (v[:4] if isinstance(v, list) else v) for k, v in r.items() if k in ("page", "tags", "type_tags")})
print()

print("=== THE BOSS NODE (fed the worker's rows)")
boss_state = {
    "outputs": {
        "tag_rows": rows,
        "file_list": state["outputs"]["file_list"],
    }
}
try:
    bout = boss_node(cast(Any, boss_state))
    outputs = bout.get("outputs", {})
    print("  boss outputs keys:", list(outputs.keys()))
    cons = outputs.get("consolidation")
    if isinstance(cons, dict):
        print("  renames:", cons.get("renames"))
        print("  drops:", cons.get("drops"))
        print("  summary:", str(cons.get("summary"))[:200])
    else:
        print("  consolidation report head:", str(cons)[:400] if cons else "(none)")
except Exception as e:
    import traceback
    print("  boss node raised:", type(e).__name__, str(e)[:300])
    traceback.print_exc(limit=3)
