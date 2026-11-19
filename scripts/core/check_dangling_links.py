"""Gate: every markdown link in the tree resolves.

A link to a file the repository does not carry is a dead end for whoever follows
it — and the audience is not hypothetical: the `wiki/help/` pages are the in-app
help, `README.md` is the front door, and `frontend/README.md` shipped a
`file:///i:/LLMs/…` link from another machine.

What counts as a link: `[text](target)` and `![alt](target)`. `http(s)://`,
`mailto:` and bare `#anchors` are not checked (they leave the tree or stay in the
page). Everything else is resolved twice, because this project writes both forms:

1. relative to the FILE (`../backend/x.py`)
2. relative to the REPOSITORY ROOT (`backend/scripts/x.py`, the form the wiki
   catalogues use)

`%20`-style escapes are decoded, `#anchor` and `?query` suffixes dropped, and a
link to a directory that exists is fine.

Usage:
    python3 scripts/core/check_dangling_links.py [--verbose] [--enforce] [--json]

    --verbose   every dangler as path:line -> target
    --enforce   exit 1 when any are found (the gate)
    --json      machine-readable census

Exit: 0 normally (a census), 1 with --enforce when a link is dangling.
"""

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: `[text](target)` and `![alt](target)`; the target may carry a title in quotes.
LINK = re.compile(r'!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')

#: Inline code spans — a link shown as an example is not a link.
INLINE_CODE = re.compile(r"`[^`]*`")

#: Targets that leave the tree or stay in the page.
EXTERNAL = ("http://", "https://", "mailto:", "tel:", "#", "data:")

BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".db", ".zip", ".gz"}

#: Links that are dangling ON PURPOSE: (file, target) -> why.
ALLOWED = {
    ("wiki/display-tests/diagrams.md", "/wiki/diagrams/cogitate-architecture.svg"):
        "a renderer fixture — the broken-image state is the thing under test",
}


def tracked_markdown() -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "ls-files", "*.md", "*.markdown"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line for line in out.splitlines() if line]


def tracked_paths() -> set[str]:
    out = subprocess.run(
        ["git", "-C", str(PROJECT_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {line for line in out.splitlines() if line}


def ships(candidate: Path, tracked: set[str]) -> bool:
    """True when this path is part of the repository — 'exists' is not enough.

    A link to a file that sits in the working tree but not in git is dangling for
    everyone who clones: `scripts/dev/setup_boss_sandbox.sh` was local-only and
    indexed, and every local run of this gate blessed it. Git tracks files, not
    directories, so a directory ships when a tracked file lives under it.
    """
    try:
        rel = candidate.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return candidate.exists()  # outside the tree: the filesystem is the judge
    if candidate.is_dir():
        prefix = f"{rel.rstrip('/')}/"
        return any(path.startswith(prefix) for path in tracked)
    return rel in tracked


def resolve(source: str, target: str, tracked: set[str]) -> bool:
    """True when the target names something the repository actually carries."""
    cleaned = unquote(target.split("#")[0].split("?")[0])
    if not cleaned:
        return True  # a pure anchor in the same page

    if cleaned.startswith("file://"):
        return False  # an absolute path on somebody's machine
    if cleaned.startswith("~"):
        return False  # a home directory is never in the tree

    path = Path(cleaned)
    source_dir = (PROJECT_ROOT / source).parent

    candidates: list[Path] = []
    if path.is_absolute():
        candidates.append(PROJECT_ROOT / cleaned.lstrip("/"))
    else:
        candidates.append(source_dir / cleaned)          # relative to the file
        candidates.append(PROJECT_ROOT / cleaned)        # relative to the root
    # The wiki viewer routes are extensionless (`/wiki/help/chat` serves chat.md),
    # so a route target is not dangling when the page file exists.
    candidates.extend(Path(f"{candidate}.md") for candidate in list(candidates))
    return any(ships(candidate, tracked) for candidate in candidates)


def main() -> int:
    verbose = "--verbose" in sys.argv
    enforce = "--enforce" in sys.argv
    as_json = "--json" in sys.argv

    files = tracked_markdown()
    tracked = tracked_paths()
    dangling: list[tuple[str, int, str]] = []
    checked = 0

    for rel_path in files:
        try:
            text = (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        in_fence = False
        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            if raw_line.lstrip().startswith(("```", "~~~")):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            # Documentation ABOUT markdown shows links inside code spans
            # (`[Bar Baz](/wiki/foo/bar-baz)`); those are examples, not links.
            line = INLINE_CODE.sub("", raw_line)
            for match in LINK.finditer(line):
                target = match.group(1)
                if target.startswith(EXTERNAL):
                    continue
                if Path(target).suffix in BINARY_SUFFIXES and target.startswith("http"):
                    continue
                checked += 1
                if (rel_path, target) in ALLOWED:
                    continue
                if not resolve(rel_path, target, tracked):
                    dangling.append((rel_path, line_no, target))

    by_file = Counter(path for path, _, _ in dangling)

    if as_json:
        print(json.dumps({
            "files": len(files),
            "links_checked": checked,
            "dangling": len(dangling),
            "by_file": dict(by_file),
            "items": [{"file": f, "line": n, "target": t} for f, n, t in dangling],
        }, indent=1))
        return 1 if (enforce and dangling) else 0

    print(f"markdown files: {len(files)}")
    print(f"links checked:  {checked}")
    print(f"dangling:       {len(dangling)}")

    if dangling:
        print("\nby file:")
        for path, count in by_file.most_common(20):
            print(f"  {count:4}  {path}")
        if verbose:
            print("\nall danglers:")
            for path, line_no, target in dangling:
                print(f"  {path}:{line_no}  ->  {target}")

    print("\nRESULT:", "DANGLING" if dangling else "CLEAN")
    if enforce and dangling:
        print("ENFORCE: FAIL")
        return 1
    if enforce:
        print("ENFORCE: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
