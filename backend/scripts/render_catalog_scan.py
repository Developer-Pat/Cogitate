"""Render the description scan — every module and its rendered description, one page.

WHY A PERSON AND NOT A MODEL, which is the whole reason this script exists: the audit
mode in `describer_dryrun.py` was built to find the weak descriptions automatically and
FAILED its own validation — the same module scored 5/5 in one pass and a 2.67 mean in the
next, same prompt minutes apart, so a threshold cannot separate anything on it. The
question "does this line tell me what the test does?" is a human judgment call, and a
person scanning 174 lines answers it in minutes with no variance.

Output: a markdown table per group, with a mark column, so the file doubles as the
worklist. Mark the lines that say nothing (or say the wrong thing); leave the rest.

Run from the repo root:
    uv run python backend/scripts/render_catalog_scan.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.testing.catalog import build_catalog  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "local" / "describer-scan.md"

HEADER = """# The description scan — {n_files} modules, one page

**Mark the lines that do not tell you what the test does.** Two shapes, both worth a mark:

- **says nothing you could not guess** from the file name — `The jina_reader scheme-guard tests.`
- **says something the tests do not check** — a wrong or misleading subject

Leave everything else alone. This file IS the worklist: when you are done, the marked rows
are the modules that get a new line, and the unmarked ones are the answer to "how much of
this actually needs doing".

Why a person and not the model: the automatic audit (rating each line 0-5) failed its own
validation — the same module scored 5/5 in one pass and a 2.67 mean in the next, same
prompt, minutes apart. A human scanning this page answers the same question with no
variance at all.

**Source:** the derived catalogue (`build_catalog`), so these are the lines the testing
page renders. **Counts:** {n_files} modules, {n_tests} tests, {n_groups} groups
({n_clusters} clusters — the page's finer grouping).

"""


def main() -> int:
    catalog = build_catalog()
    tests = catalog["tests"]
    groups: dict[str, list[dict]] = {}
    for row in tests:
        groups.setdefault(row["group"], []).append(row)

    lines = [
        HEADER.format(
            n_files=catalog["totals"]["files"],
            n_tests=catalog["totals"]["tests"],
            n_groups=len(groups),                        # counted, not read off a total
            n_clusters=catalog["totals"]["clusters"],
        )
    ]
    for group in sorted(groups):
        rows = sorted(groups[group], key=lambda r: r["path"])
        lines.append(f"## {group} — {len(rows)} modules\n")
        lines.append("| mark | description as rendered | module | tests |")
        lines.append("|---|---|---|---|")
        for r in rows:
            desc = (r["description"] or "(none)").replace("|", "\\|")
            lines.append(f"| [ ] | {desc} | `{r['path']}` | {r['test_count']} |")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {len(tests)} modules across {len(groups)} groups -> {OUT.relative_to(ROOT)}")
    print(f"  {len(lines)} lines, {OUT.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
