r"""Gate/Census: commit numbers written into the tree.

A commit number is a citation only while the history is there — and a shipped repository's past can be
replaced by a flatten: one commit, no past. Every `(Phase B, <hash>)` in a doc, comment or todo then
points at nothing: the number cannot be resolved, the subject it stood for is gone, and the reader has
no way to recover it.

This scans the TRACKED tree for tokens that actually resolve to a commit in this
repository (a hex-looking word that is not a commit is not a reference), groups
them by area, and prints the subject each one stands for — so a rewrite can say
what the commit DID instead of naming it.

Where a citation is acceptable, and where it is not:

- **Historical records keep theirs** — `todo/`, `wiki/issues/`,
  `wiki/dev-notes/deep-dives/`. A resolved-issue narrative or a deep dive is an
  account of what happened; the number is its provenance, like a ticket number.
- **Current documentation and code do not** — `wiki/dev-notes/` (outside the deep
  dives), `wiki/atlas/`, `wiki/entities/`, code comments, frontend. A reader
  asking "how does this work" cannot use a hash, and after a flatten it is not
  even a dead end: it is noise. Those say what the code DOES.

Usage:
    python3 scripts/core/check_commit_references.py [--verbose] [--enforce] [--json]
                                                   [--include-dangling]

    --verbose           every hit as path:line
    --enforce           exit 1 for a reference OUTSIDE the historical areas,
                        whether it resolves (pre-flatten) or is a dangling hex
                        token (post-flatten) — the durable gate
    --include-dangling  also list hex tokens that do not resolve
    --json              machine-readable census

Exit code: 0 normally, 1 with --enforce when a current doc or a comment carries
one.
"""

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: A hex run that could be an abbreviated or full object name.
CANDIDATE = re.compile(r"\b[0-9a-f]{7,40}\b")

#: A UUID of the shape the app stores — its segments are hex too, and they are
#: identifiers, not commits. Removed before scanning a line.
UUID_SHAPE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)

#: Directories whose contents are runtime output, not the tree.
SKIP_PREFIXES = (
    "backend/tests/fixtures/",  # a data snapshot: hex ids, not commits
    "backend/logs/",
    "data/",
    "node_modules/",
    ".venv/",
    "frontend/dist/",
)

BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".db", ".woff", ".woff2",
    ".zip", ".gz", ".whl", ".so",
}

#: Areas whose citations are provenance, not documentation — they keep them.
HISTORICAL_PREFIXES = (
    "todo/",
    "wiki/issues/",
    "wiki/dev-notes/deep-dives/",
)

#: The area a path belongs to, for the census.
AREAS = (
    ("wiki/", "wiki"),
    ("todo/", "todo"),
    ("skills/", "skills"),
    ("backend/", "backend"),
    ("frontend/", "frontend"),
    ("scripts/", "scripts"),
    ("local/", "local (untracked — not shipped)"),
)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), *args],
        capture_output=True,
        text=True,
    ).stdout


def tracked_files() -> list[str]:
    out = git("ls-files")
    return [
        line
        for line in out.splitlines()
        if line and not line.startswith(SKIP_PREFIXES) and Path(line).suffix not in BINARY_SUFFIXES
    ]


def is_commit(token: str) -> bool:
    """True when the token names a commit in THIS repository."""
    result = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "cat-file", "-e", f"{token}^{{commit}}"],
        capture_output=True,
    )
    return result.returncode == 0


def commit_subject(token: str) -> str:
    return git("log", "-1", "--format=%s", token).strip()


def looks_like_a_hash(token: str) -> bool:
    """An abbreviated object name that no longer resolves (the post-flatten case).

    Deliberately conservative, because this runs when nothing resolves and the
    only evidence is the shape:

    - at least one digit and one letter (a hex WORD is prose, and a decimal run
      was already skipped);
    - not 32 or 64 characters — those are `uuid4().hex` ids and sha256 digests in
      this codebase, which appear by the hundred in data and tests.
    """
    if len(token) < 8 or len(token) in (32, 64):
        return False
    return any(c.isdigit() for c in token) and any(c.isalpha() for c in token)


def is_historical(path: str) -> bool:
    return path.startswith(HISTORICAL_PREFIXES)


def area_of(path: str) -> str:
    for prefix, label in AREAS:
        if path.startswith(prefix):
            return label
    return "root docs"


def main() -> int:
    verbose = "--verbose" in sys.argv
    enforce = "--enforce" in sys.argv
    as_json = "--json" in sys.argv
    strict = False

    include_dangling = "--include-dangling" in sys.argv
    files = tracked_files()
    hits: list[tuple[str, int, str, str]] = []  # path, line_no, token, line text
    dangling: list[tuple[str, int, str, str]] = []
    resolved: dict[str, bool] = {}

    for rel_path in files:
        try:
            text = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            line = UUID_SHAPE.sub("<uuid>", line)
            for match in CANDIDATE.finditer(line):
                token = match.group(0)
                if len(token) < 7:
                    continue
                # A pure decimal run is a number, not a hash.
                if token.isdigit():
                    continue
                if token not in resolved:
                    resolved[token] = is_commit(token)
                if resolved[token]:
                    hits.append((rel_path, line_no, token, line.strip()))
                elif include_dangling and looks_like_a_hash(token):
                    dangling.append((rel_path, line_no, token, line.strip()))

    distinct = sorted({token for _, _, token, _ in hits})
    by_area = Counter(area_of(path) for path, _, _, _ in hits)
    by_file = Counter(path for path, _, _, _ in hits)

    if as_json:
        print(
            json.dumps(
                {
                    "files_scanned": len(files),
                    "references": len(hits),
                    "distinct_commits": len(distinct),
                    "by_area": dict(by_area),
                    "by_file": dict(by_file),
                    "commits": {token: commit_subject(token) for token in distinct},
                },
                indent=1,
            )
        )
        return 1 if (strict and hits) else 0

    print(f"tracked files scanned: {len(files)}")
    print(f"commit references:     {len(hits)} in {len(by_file)} files")
    print(f"distinct commits:      {len(distinct)}")

    print("\nby area:")
    for area, count in by_area.most_common():
        print(f"  {area:32} {count:4}")

    print("\nby file (top 15):")
    for path, count in by_file.most_common(15):
        print(f"  {path:60} {count:4}")

    print("\nthe commits they name (the thing a rewrite has to say instead):")
    for token in distinct[:25]:
        print(f"  {token}  {commit_subject(token)[:80]}")
    if len(distinct) > 25:
        print(f"  … and {len(distinct) - 25} more")

    if verbose:
        print("\nall hits:")
        for path, line_no, token, line in hits:
            print(f"  {path}:{line_no}  [{token}]  {line[:100]}")

    current_doc_refs = [h for h in hits if not is_historical(h[0])]
    current_doc_dangling = [d for d in dangling if not is_historical(d[0])]

    if include_dangling:
        print(f"\ndangling hex tokens (do not resolve here — the post-flatten case): {len(dangling)}")
        by_file_dangling = Counter(path for path, _, _, _ in dangling)
        for path, count in by_file_dangling.most_common(10):
            print(f"  {path:60} {count:4}")
        if verbose:
            for path, line_no, token, line in dangling[:200]:
                print(f"  {path}:{line_no}  [{token}]  {line[:100]}")

    print(f"\ncurrent documentation / code: {len(current_doc_refs)} reference(s)")
    for path, line_no, token, line in current_doc_refs:
        print(f"  {path}:{line_no}  [{token}]  {line[:100]}")

    total = len(hits) + (len(dangling) if include_dangling else 0)
    print("\nRESULT:", "FOUND" if total else "NONE")
    if enforce and (current_doc_refs or current_doc_dangling):
        print("ENFORCE: FAIL — a current doc or a comment carries a commit number")
        return 1
    if enforce:
        print("ENFORCE: PASS — every citation is in a historical record")
    return 1 if (strict and total) else 0


if __name__ == "__main__":
    sys.exit(main())
