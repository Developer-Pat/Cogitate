#!/usr/bin/env python3
"""Gate: the tree stops naming features that no longer exist.

Two patterns, both left over from removals:

- **Boris / Ouroboros** — the self-reflection/monitor system replaced by the
  external ACP agent (Exa).
- **`migration 00NN`** — citations of the retired alembic chain. The schema is
  one baseline now (`0001`), so a revision number in prose or a comment points
  at a file that does not exist. Describe the state instead.

Files listed in ALLOWED may carry the names, on purpose:

- `todo/done/`, `todo/old/`, `todo/banks/` — completed records, kept verbatim
  (the todo rules forbid rewriting them).
- `todo/master.md` — the live ruling that names the removed tools in order to
  keep them removed.
- `wiki/dev-notes/known-issues.md` — a removal record names what it removed.
- the three tool-curation tests — they ASSERT the names are absent from tool
  descriptions; deleting the names deletes the guard.
- the two atlas checkers — they list the names as forbidden patterns.

Usage: python3 scripts/core/check_stale_references.py [--verbose]
Exit code 1 when a mention appears outside the allowed set.
"""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PATTERNS = {
    "removed-system": re.compile(r"boris|ouroboros", re.IGNORECASE),
    "retired-revision": re.compile(r"\bmigrations? 00(?!01\b)\d\d\b", re.IGNORECASE),
}

ALLOWED = {
    "scripts/core/check_stale_references.py",  # this gate names them
    # completed and archived records
    "todo/done/",
    "todo/old/",
    "todo/banks/",
    # the live ruling and the removal record
    "todo/master.md",
    "wiki/dev-notes/known-issues.md",
    # negative assertions and forbidden-pattern lists
    "backend/tests/unit/test_tool_curation.py",
    "backend/tests/unit/test_tool_cruft_removal.py",
    "backend/tests/unit/test_tool_capability_taxonomy.py",
    "scripts/core/check_atlas_validation.py",
}

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".db", ".woff", ".woff2"}


def allowed(path: str) -> bool:
    return any(path == entry or path.startswith(entry) for entry in ALLOWED)


def tracked_files() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def main() -> int:
    verbose = "--verbose" in sys.argv
    findings: list[tuple[str, int, str, str]] = []

    for rel_path in tracked_files():
        if allowed(rel_path) or Path(rel_path).suffix in BINARY_SUFFIXES:
            continue
        try:
            text = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in PATTERNS.items():
                if pattern.search(line):
                    findings.append((rel_path, line_no, kind, line.strip()))

    print(f"tracked files scanned: {len(tracked_files())}")
    print(f"allowed holders: {len(ALLOWED)} entries")
    if findings:
        print(f"\n{len(findings)} mention(s) outside the allowed set:")
        for rel_path, line_no, kind, line in findings:
            print(f"  {rel_path}:{line_no}  [{kind}]")
            if verbose:
                print(f"      {line[:160]}")
        print("\nRESULT: FAIL")
        return 1

    print("\nRESULT: CLEAN")
    return 0


if __name__ == "__main__":
    sys.exit(main())
