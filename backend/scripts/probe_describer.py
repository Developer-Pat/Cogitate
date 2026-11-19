"""
THE DESCRIBER EXPERIMENT — can a bare LLM write a true test description?

THE QUESTION. The docstring sweep is done by hand and the catalog is clean, but the
work does not scale. The tag-survey fan-out (a deterministic core, a bare-LLM worker
at the edge) is the obvious machinery. Before trusting it, one thing has to be
settled:

    When the existing docstring is WRONG, does a worker CATCH IT or ECHO IT?

The worry is concrete. `test_agent_beats.py` says "the co-authoring store + tool" and
tests `parse` / `rejoin` / `sources_parse` — it is a PARSER. Why does it say that?
Because the docstring is the most salient thing in the file. A worker asked to
describe that module may simply paraphrase the wrong text, which would make the
pipeline a machine for propagating the defect it was hired to fix.

THE DESIGN — two prompts per module, same everything else:

    A (WITHHELD): the test code only.    -> does it derive from the SOURCE?
    B (QUOTED):   the test code + the existing docstring. -> does it ECHO?

If A and B agree, B is not a contaminant. If B collapses to the existing line while A
finds the truth, withheld is mandatory. If A ALSO echoes, the worker is reading the
file name and the experiment has failed.

THE SAMPLE is deliberately adversarial: two modules whose descriptions are known to be
questionable (`test_routing`, `test_agent_beats`) plus three the sweep already fixed,
so a right answer is known to exist.

Cost: ~10 calls over the tag-worker chain (free route -> local Bonsai -> deepseek).
Run from the repo root:

    .venv/bin/python3 backend/scripts/probe_describer.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.pseudo_agents.catalog import TAG_WORKER  # noqa: E402
from app.domain.pseudo_agents.spec import (  # noqa: E402
    PseudoAgentError, PseudoAgentSpec, invoke,
)

TESTS = Path(__file__).resolve().parents[2] / "backend" / "tests"

#: The adversarial sample. The first two are the KNOWN-QUESTIONABLE ones — the whole
#: point is whether the worker sees what a reader sees.
SAMPLE = [
    "workflows/test_routing.py",
    "unit/test_agent_beats.py",
    "unit/tools/test_jina_reader_guard.py",
    "unit/cognitive_pipeline/test_conversation_compactor.py",
    "workflows/test_trigger_scheduler.py",
]

DESCRIBER_SYSTEM = (
    "You describe Python test modules. Given the source of a test file, write ONE "
    "line saying what the tests CHECK - the properties they assert, not which module "
    "they live in. Present tense. No dates, no phase or session numbers, no project "
    "codenames. At most 95 characters. Return ONLY the line, with no quotes, no "
    "trailing period is fine, and no prose."
)

DESCRIBER = PseudoAgentSpec(
    name="describer-probe",
    system_prompt=DESCRIBER_SYSTEM,
    # The house chain: free route first, the always-up local model second.
    chain=TAG_WORKER.chain,
    temperature=0.0,
    # 4000, NOT 120. The free route is a REASONING model: with a small budget the
    # thinking consumes it and `content` comes back EMPTY while the call still
    # reports success. The probe's first run returned ten empty descriptions for
    # exactly that reason. The chat path floors max_tokens for reasoning models;
    # the pseudo-agent path does not - a live footgun for any small spec.
    max_tokens=4000,
)

MAX_SOURCE_CHARS = 6000


def source_of(path: str) -> str:
    return (TESTS / path).read_text(encoding="utf-8")[:MAX_SOURCE_CHARS]


def existing_line(path: str) -> str:
    """The current description, read crudely on purpose - this is a probe, not the app."""
    text = (TESTS / path).read_text(encoding="utf-8")
    m = re.search(r'"""(.+?)"""', text, re.DOTALL)
    if not m:
        return "(none)"
    body = m.group(1).strip()
    for line in body.splitlines():
        if line.strip():
            return line.strip()
    return "(empty)"


def clean(raw: str) -> str:
    line = raw.strip().strip('"').strip("'").strip()
    return line.splitlines()[0][:120] if line else ""


def run_one(path: str) -> dict:
    src = source_of(path)
    existing = existing_line(path)

    prompt_a = f"Describe this test module.\n\n```python\n{src}\n```"
    prompt_b = (
        f"Describe this test module. Its current description is: {existing!r}\n\n"
        f"```python\n{src}\n```"
    )

    out = {"path": path, "existing": existing}
    for label, prompt in (("withheld", prompt_a), ("quoted", prompt_b)):
        try:
            result = invoke(DESCRIBER, prompt)
            out[label] = clean(result.text)
            out[f"{label}_by"] = getattr(result, "served_by", "?")
        except PseudoAgentError as e:
            out[label] = f"<all providers failed: {e}>"
            out[f"{label}_by"] = "-"
    return out


def main() -> int:
    rows = []
    for path in SAMPLE:
        print(f"... {path}", flush=True)
        rows.append(run_one(path))
    print()
    print("=" * 100)
    for r in rows:
        print(f"\n### {r['path']}")
        print(f"  EXISTING  : {r['existing'][:92]}")
        print(f"  A WITHHELD: {r['withheld'][:92]}")
        print(f"  B QUOTED  : {r['quoted'][:92]}")
        # `"" in s` is always True, so an empty answer printed "echoes? YES" on
        # every row - the headline of the first run was produced by this bug.
        proposed = r["quoted"].strip()
        same = bool(proposed) and proposed.lower()[:40] in r["existing"].lower()
        note = "" if proposed else "  (EMPTY ANSWER - not a result)"
        print(f"  B echoes the existing line? {'YES' if same else 'no'}{note}")
        print(f"  served_by : A={r.get('withheld_by')}  B={r.get('quoted_by')}")
    out = Path(__file__).resolve().parents[2] / "local" / "probe-describer.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nraw rows -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
