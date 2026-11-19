"""The tag-survey TRICKLE run (the atlas's probe config).

Runs the real graph — the rewired pseudo-agent nodes — over a bounded
slice of the wiki: 2 batches of 3 files, one worker thread, the
adaptive pause.

Run from the repo root so Settings finds the .env:
    .venv/bin/python3 backend/scripts/run_tag_survey_trickle.py

Config (the atlas's probe values, wiki/atlas/workflows/tag-survey-fanout):
    batch_size             3
    max_batches            2   (the smoke gate — a limited run)
    max_workers            1   (the local-model concurrency cap)
    batch_delay_seconds    5   (the trickle floor — halved per batch)
    trickle                True
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# the tool registry (the nodes read files through the file-info tool)
from app.domain.tools.registry import init_default_registry

init_default_registry()

from app.workflows.graphs.tag_survey_graph import create_tag_survey_graph
from app.workflows.state.workflow_state import RunMetadata

import os

# the run size comes from the environment so one script serves the
# trickle (2), a test run (20), and the full survey (187)
CONFIG = {
    "base_path": str(Path(__file__).resolve().parents[2] / "wiki"),
    "batch_size": int(os.environ.get("TAG_BATCH_SIZE", "3")),
    "max_batches": int(os.environ.get("TAG_MAX_BATCHES", "2")),
    "max_workers": int(os.environ.get("TAG_MAX_WORKERS", "1")),
    "batch_delay_seconds": float(os.environ.get("TAG_DELAY", "5")),
    "trickle": os.environ.get("TAG_TRICKLE", "1") == "1",
    # NOTE: worker_fn is deliberately NOT set here — tag_dispatch declares
    # it inside the graph, so any caller gets the tag workers. If this run
    # falls through to File Clerk's summarize, that wiring is broken.
}

state = {
    # WorkflowState carries the ids FLAT (the nodes read state["workflow_id"])
    # AND a metadata object that holds the config (the dispatcher reads
    # state["metadata"].config). Both are required.
    "workflow_id": "wf-trickle",
    "template_id": "tag-survey",
    "inputs": {},
    "outputs": {},
    "messages": [],
    "metadata": RunMetadata(
        workflow_id="wf-trickle",
        template_id="tag-survey",
        config=CONFIG,
    ),
}

print("=" * 72)
print("THE TAG-SURVEY TRICKLE RUN")
print("=" * 72)
print(f"  config: {CONFIG}")
print()

graph = create_tag_survey_graph().compile()
result = graph.invoke(state)

print()
print("=" * 72)
print("THE RESULT")
print("=" * 72)
meta = result.get("execution_result") or {}
print("  execution_result:", {k: v for k, v in meta.items() if k != "node_results"})

outputs = result.get("outputs", {}) or {}
print(f"  output keys: {sorted(outputs.keys())}")
brs = outputs.get("batch_results", []) or []
print(f"  batches succeeded: {len(brs)}")
for b in brs:
    if isinstance(b, dict):
        print(f"    batch {b.get('batch_id')}: {len(b.get('tag_rows', []) or [])} rows, "
              f"worker_meta={b.get('worker_meta')}")
print(f"  batch_ran/batch_total: {outputs.get('batch_ran')}/{outputs.get('batch_total')}"
      f"  (limited={outputs.get('batch_limited')})")
print(f"  batch_errors: {outputs.get('batch_errors')}")

rows = outputs.get("tag_rows", []) or []
counts = outputs.get("tag_counts", {}) or {}
print(f"\n  TAG ROWS: {len(rows)}   DISTINCT TAGS: {len(counts)}")
for r in rows[:10]:
    print(f"    {r.get('page')}  →  {r.get('tags')}")

cons = outputs.get("consolidation")
if cons:
    print("\n  THE BOSS SAID:")
    if isinstance(cons, dict):
        for k in ("renames", "adds", "drops", "summary"):
            print(f"    {k}: {cons.get(k)}")
    else:
        print("   ", str(cons)[:600])

report = outputs.get("consolidation_write")
if report:
    print(f"\n  report written: {report}")
