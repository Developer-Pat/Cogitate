"""The tag-consolidation APPLIER — the wet run (W1).

Reads the boss's consolidation report and either shows what it WOULD
change (`--dry-run`, the default) or makes the changes (`--apply`).

The three operations the report can carry:

  renames   a tag renamed everywhere it appears   (type/devnote -> type/dev-notes)
  adds      a tag added to a named file           (<path>: add <tag>)
  drops     a tag removed everywhere              (part-code)

SAFETY: the wiki is git-tracked. Run `--dry-run` first, review the
diff, then `--apply` and inspect with `git diff`. A mistake is
`git checkout wiki/` away. The applier also writes a `.bak` beside
each changed file, so a revert exists even outside git.

Frontmatter: the tags line is edited TEXTUALLY (line-level), never
re-serialized — a YAML round-trip would reflow the whole block and
bury the real change in noise. Both the inline form
(`tags: [a, b]`) and the block form (`tags:` then `- a` lines) are
handled, which the survey's own reader does NOT do.

Run from the repo root:
    .venv/bin/python3 backend/scripts/apply_tag_proposals.py            # dry run
    .venv/bin/python3 backend/scripts/apply_tag_proposals.py --apply
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WIKI = REPO / "wiki"
REPORT = REPO / "agents" / "tag-layer-sweeper" / "out" / "consolidation-report.md"


# ── the report parser ───────────────────────────────────────────────

def parse_report(text: str) -> dict:
    """Pull renames / adds / drops out of the boss's markdown report."""
    out = {"renames": [], "adds": [], "drops": []}
    section = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("## "):
            low = s.lower()
            if "rename" in low:
                section = "renames"
            elif "add" in low:
                section = "adds"
            elif "drop" in low:
                section = "drops"
            else:
                section = None
            continue
        if section and s.startswith("- "):
            item = s[2:].strip()
            if not item:
                continue
            if section == "renames":
                # "- from -> to"  (the arrow may be -> or the unicode one)
                m = re.match(r"^(\S+)\s*(?:->|→)\s*(\S+)$", item)
                if m:
                    out["renames"].append((m.group(1), m.group(2)))
            elif section == "adds":
                # "- <path>: add <tag>"
                m = re.match(r"^(.+?):\s*add\s+(\S+)$", item)
                if m:
                    out["adds"].append((m.group(1).strip(), m.group(2).strip()))
            else:
                out["drops"].append(item)
    return out


# ── the frontmatter tag reader / writer ─────────────────────────────

INLINE_RE = re.compile(r"^(?P<indent>\s*)tags:\s*\[(?P<body>[^\]]*)\]\s*$")
BLOCK_RE = re.compile(r"^(?P<indent>\s*)tags:\s*$")


def read_tags(path: Path) -> tuple[list[str], str, int]:
    """Return (tags, form, line_index). form is 'inline'|'block'|'none'."""
    lines = path.read_text(encoding="utf-8").splitlines()
    # only look inside the leading frontmatter block
    if not lines or lines[0].strip() != "---":
        return [], "none", -1
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), -1)
    if end < 0:
        return [], "none", -1
    for i in range(1, end):
        m = INLINE_RE.match(lines[i])
        if m:
            body = m.group("body").strip()
            tags = [t.strip().strip("'\"") for t in body.split(",") if t.strip()]
            return tags, "inline", i
        if BLOCK_RE.match(lines[i]):
            tags = []
            j = i + 1
            while j < end and re.match(r"^\s*-\s+", lines[j]):
                tags.append(lines[j].split("-", 1)[1].strip().strip("'\""))
                j += 1
            return tags, "block", i
    return [], "none", -1


def write_tags(path: Path, tags: list[str], form: str, idx: int) -> bool:
    """Rewrite just the tags region. Returns True when the file changed."""
    lines = path.read_text(encoding="utf-8").splitlines()
    new = ", ".join(tags)

    if form == "inline":
        m = INLINE_RE.match(lines[idx])
        if m is None:            # the line moved under us — do not guess
            return False
        rebuilt = f"{m.group('indent')}tags: [{new}]"
        if rebuilt == lines[idx]:
            return False
        lines[idx] = rebuilt
    elif form == "block":
        # find the run of "- tag" lines after the "tags:" line and
        # replace it with the same shape (or the inline form if empty)
        end = next((i for i in range(idx + 1, len(lines)) if lines[i].strip() == "---"), len(lines))
        j = idx + 1
        while j < end and re.match(r"^\s*-\s+", lines[j]):
            j += 1
        indent = " " * (len(lines[idx]) - len(lines[idx].lstrip()) + 2)
        block = [f"{indent}- {t}" for t in tags]
        lines[idx + 1:j] = block
    else:
        return False

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


# ── the plan ────────────────────────────────────────────────────────

def build_plan(ops: dict) -> list[dict]:
    """Work out every file change before touching anything."""
    changes: list[dict] = []
    rename_map = {a: b for a, b in ops["renames"]}
    drops = set(ops["drops"])
    adds = {}
    for path_str, tag in ops["adds"]:
        p = Path(path_str)
        if not p.is_absolute():
            p = WIKI / path_str
        adds.setdefault(p, []).append(tag)

    for path in sorted(WIKI.rglob("*.md")):
        tags, form, idx = read_tags(path)
        if form == "none":
            if path in adds:
                changes.append({"path": path, "form": "none", "add": adds[path],
                                "old": [], "new": adds[path], "why": "add to untagged page"})
            continue
        old = list(tags)
        new = [rename_map.get(t, t) for t in tags]
        new = [t for t in new if t not in drops]
        for t in adds.get(path, []):
            if t not in new:
                new.append(t)
        # the renamed/dropped tags may leave an untyped page: leave that alone
        if new != old:
            changes.append({"path": path, "form": form, "idx": idx,
                            "old": old, "new": new, "why": "tag edit"})
    return changes


# ── main ────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    ap.add_argument("--report", default=str(REPORT))
    args = ap.parse_args()

    report = Path(args.report)
    if not report.exists():
        print(f"no report at {report} — run the survey first")
        return 1

    ops = parse_report(report.read_text(encoding="utf-8"))
    print("=" * 74)
    print("THE TAG CONSOLIDATION — " + ("APPLY" if args.apply else "DRY RUN"))
    print("=" * 74)
    print(f"  parsed: {len(ops['renames'])} renames, {len(ops['adds'])} adds, {len(ops['drops'])} drops")
    for a, b in ops["renames"]:
        print(f"    rename  {a} -> {b}")
    for p, t in ops["adds"]:
        print(f"    add     {t}  ->  {Path(p).name}")
    print(f"    drops   {', '.join(ops['drops'])}")

    changes = build_plan(ops)
    print(f"\n  FILES AFFECTED: {len(changes)}")

    # THE EMPTY-TAG WARNING (2026-09-10, found by the first dry run): the
    # drops strip EVERY tag from a few pages, leaving an empty tag list.
    # The applier does not invent a replacement — it makes the loss loud
    # so a human decides (this is the "never silent" rule).
    emptied = [c for c in changes if c["new"] == [] and c["old"]]
    if emptied:
        print(f"\n  ⚠️  {len(emptied)} file(s) would be left with NO tags:")
        for c in emptied:
            print(f"       {c['path'].relative_to(REPO)}")
            print(f"          was: {c['old']}")
        print("     The applier will NOT invent a replacement — add a type tag")
        print("     to those pages by hand, or leave them untagged deliberately.")

    for c in changes[:25]:
        print(f"    {c['path'].relative_to(REPO)}")
        print(f"        {c['old']}  ->  {c['new']}")
    if len(changes) > 25:
        print(f"    ... and {len(changes) - 25} more")

    if not args.apply:
        print("\n  (dry run — nothing written. Re-run with --apply to write.)")
        return 0

    written = 0
    for c in changes:
        path = c["path"]
        if c["form"] == "none":
            # An untagged page has NO frontmatter block at all, so this
            # must PREPEND one. (The first version inserted after lines[0]
            # only when it was already '---' — which an untagged page by
            # definition is not — so all 5 adds silently did nothing.
            # Found by verifying the writes after the apply.)
            text = path.read_text(encoding="utf-8")
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
            path.write_text(
                f"---\ntags: [{', '.join(c['add'])}]\n---\n\n{text}",
                encoding="utf-8",
            )
            written += 1
            continue
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        if write_tags(path, c["new"], c["form"], c["idx"]):
            written += 1

    print(f"\n  ✅ APPLIED: {written} files written (each with a .bak beside it)")
    print("     review with:  git diff --stat wiki/")
    print("     revert with:  git checkout wiki/  &&  find wiki -name '*.bak' -delete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
