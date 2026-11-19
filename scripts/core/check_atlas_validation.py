#!/usr/bin/env python3
"""
Atlas Validation Check — wiki/atlas integrity gate.

Validates the atlases (wiki/atlas/ — ui + api) against the codebase and their own
link conventions. Runs standalone (exit 1 on any failure) and is wired into
the sweep (scripts/core/sweep) as a docs check.

Checks:
  1. Frontmatter completeness — every doc has title/type/path/confidence/updated
  2. Stale-name scan — no references to removed features/pages
     (removal records exempt; they intentionally name removed identifiers)
  3. Wikilink resolution — every [[link]] resolves (exact -> dir index ->
     recursive name search -> .html, mirroring the wiki API)
  4. Codebase sync — every doc `path:` frontmatter exists in the repo
  5. Mermaid fence balance — every ```mermaid has a closing fence

Usage:
    python3 scripts/core/check_atlas_validation.py
    python3 scripts/core/check_atlas_validation.py --quiet   # only failures
"""

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WIKI_ROOT = REPO_ROOT / "wiki"
ATLAS_ROOT = WIKI_ROOT / "atlas"

# Removed features/pages that docs must not reference (unless a removal record)
STALE_PATTERNS = [
    r"Performance\s+page",
    r"Statistics\s+page",
    r"AgentDiscovery",
    r"AgentVersions",
    r"ComponentTest",
    r"Boris",
]

# Phrases that mark a doc as a REMOVAL RECORD (intentionally names removed items)
REMOVAL_MARKERS = [
    "REMOVED", "Removed 2026-08-01", "removed during the legacy-name cleanup",
    "DELETED 2026-08-01", "was REMOVED", "were REMOVED", "removed from LogViewer",
    "field was REMOVED", "Field removed (2026-08-01)", "was removed (2026-08-01)",
]

# Legacy API identifiers that are documented as-is (real field names in code)
LEGACY_IDENTIFIERS = [
    "borisSystemLogs", "boris_system_logs", "boris-system", "boris_system.log",
]


def _parse_frontmatter(text: str) -> dict:
    """Minimal frontmatter extractor (mirrors backend wiki router)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"\'"')
    return fm


def iter_docs():
    """Yield (rel_path_from_wiki_root, content) for every .md under wiki/, excluding README.md files are included (they are index docs)."""
    for root, dirs, files in os.walk(WIKI_ROOT):
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            path = Path(root) / f
            rel = path.relative_to(WIKI_ROOT).as_posix()
            with open(path, encoding="utf-8", errors="replace") as fh:
                content = fh.read()
            yield rel, content


def resolve_wikilink(target: str) -> bool:
    """Mirror the backend get_wiki_page resolution: exact -> dir index -> recursive -> .html."""
    clean = target.strip()
    if (WIKI_ROOT / f"{clean}.md").exists() or (WIKI_ROOT / f"{clean}.html").exists():
        return True
    _dir = WIKI_ROOT / clean
    if (WIKI_ROOT / clean / "index.md").exists() or (WIKI_ROOT / clean / "README.md").exists():
        return True
    if _dir.is_dir():
        # descriptive index files (e.g. "Pages Index.md") — type-based
        for _md in sorted(_dir.glob("*.md")):
            try:
                _fm = _parse_frontmatter(_md.read_text(encoding="utf-8"))
                if _fm.get("type", "").endswith("-index"):
                    return True
            except Exception:
                continue
    for md in WIKI_ROOT.rglob(f"{clean}.md"):
        if md.stem == clean.split("/")[-1]:
            return True
    for h in WIKI_ROOT.rglob(f"{clean}.html"):
        if h.stem == clean.split("/")[-1]:
            return True
    return False


def check_frontmatter(issues, quiet):
    required = ["title:", "type:", "path:", "confidence:", "updated:"]
    count = 0
    for rel, content in iter_docs():
        # atlas docs (UI + API) carry the full frontmatter contract
        if not rel.startswith("atlas/"):
            continue
        if "type: atlas-index" in content or "type: wiki-index" in content:
            # index docs have a lighter frontmatter but still need title/type
            missing = [k for k in required if k not in content]
            if missing:
                count += 1
                issues.append(f"  [{rel}] frontmatter missing: {missing}")
            continue
        for k in required:
            if k not in content:
                count += 1
                issues.append(f"  [{rel}] frontmatter missing: {k}")
                break
        # api-atlas pages additionally carry tags (Obsidian testbed)
        if rel.startswith("atlas/api/") and "tags:" not in content:
            count += 1
            issues.append(f"  [{rel}] frontmatter missing: tags:")
            continue
    return count


def check_stale_names(issues, quiet):
    count = 0
    for rel, content in iter_docs():
        if any(m in content for m in REMOVAL_MARKERS):
            continue  # removal record — intentional
        if re.search(r"Documented exception", content, re.IGNORECASE):
            continue
        # scrub legacy API identifiers that are documented as-is
        c = content
        for ident in LEGACY_IDENTIFIERS:
            c = c.replace(ident, "X")
        hits = [p for p in STALE_PATTERNS if re.search(p, c, re.IGNORECASE)]
        if hits:
            count += 1
            issues.append(f"  [{rel}] stale refs: {hits}")
    return count


def check_wikilinks(issues, quiet):
    link_re = re.compile(r"\[\[([^\]]+)\]\]")
    total = 0
    broken = []
    for rel, content in iter_docs():
        # Remove inline-code spans (`` `...` ``) and fenced code blocks — those hold
        # intentional syntax examples like `[[entity-name]]`, not real links.
        stripped = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
        stripped = re.sub(r"`[^`]*`", "", stripped)
        for m in link_re.finditer(stripped):
            target = m.group(1).strip()
            total += 1
            t = target.split("|")[0].split("#")[0].strip()
            if not t:
                continue
            if not resolve_wikilink(t):
                broken.append((rel, t))
    if broken:
        for rel, t in broken:
            issues.append(f"  [{rel}] broken wikilink: [[{t}]]")
    return len(broken)


def check_sync(issues, quiet):
    """Every doc's frontmatter `path:` must exist in the repo (removal records exempt)."""
    count = 0
    for rel, content in iter_docs():
        if "REMOVED" in content or "DELETED" in content:
            continue
        m = re.search(r"^path:\s*(.+)$", content, re.MULTILINE)
        if not m:
            continue
        src = m.group(1).strip().strip("`")
        # Multi-path frontmatter: "path: a + b + c" — segments share a base
        paths = [s.strip() for s in src.split("+")]
        # Resolve each segment against candidate roots (repo root, frontend/src, backend)
        candidate_roots = [REPO_ROOT, REPO_ROOT / "frontend/src", REPO_ROOT / "backend"]
        missing_segments = []
        for seg in paths:
            if not seg:
                continue
            resolved = False
            for root in candidate_roots:
                candidates = [root / seg]
                if not seg.endswith((".ts", ".tsx", ".py", ".js", ".jsx")):
                    candidates += [root / (seg + ".tsx"), root / (seg + ".ts"), root / (seg + ".py")]
                if any(p.exists() for p in candidates):
                    resolved = True
                    break
            if not resolved:
                missing_segments.append(seg)
        if missing_segments:
            count += 1
            issues.append(f"  [{rel}] path segment(s) not found: {missing_segments} (in: {src})")
    return count


def check_mermaid(issues, quiet):
    count = 0
    for rel, content in iter_docs():
        lines = content.split("\n")
        opens = sum(1 for l in lines if l.strip() == "```mermaid")
        if opens == 0:
            continue
        closes = sum(1 for l in lines if l.strip() == "```")
        # Each mermaid block has one open + one close; closes must be >= opens.
        if closes < opens:
            count += 1
            issues.append(f"  [{rel}] unbalanced mermaid fences (opens={opens}, closes={closes})")
    return count


def main():
    parser = argparse.ArgumentParser(description="UI Atlas validation gate")
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args()

    issues = []
    results = [
        ("Frontmatter", check_frontmatter(issues, args.quiet)),
        ("Stale names", check_stale_names(issues, args.quiet)),
        ("Wikilinks", check_wikilinks(issues, args.quiet)),
        ("Codebase sync", check_sync(issues, args.quiet)),
        ("Mermaid fences", check_mermaid(issues, args.quiet)),
    ]

    print("ATLAS VALIDATION")
    print("================")
    for label, count in results:
        status = "OK" if count == 0 else f"FAIL ({count})"
        print(f"  {label:16s} {status}")

    if issues:
        print("\nISSUES:")
        for issue in issues:
            print(issue)

    total = sum(c for _, c in results)
    print(f"\n  RESULT: {'ALL PASS' if total == 0 else f'{total} issue(s)'}")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
