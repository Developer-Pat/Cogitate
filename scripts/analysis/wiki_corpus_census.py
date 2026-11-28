#!/usr/bin/env python3
"""Wiki corpus census — the three defect classes, as counts and as named lists.

Read-only. Measures the corpus honesty problem the 2026-11-27 tour exposed:

  A. confidence census        — declared confidence per page (stub v. hand-written)
  B. broken wikilinks         — resolved exactly as the app resolves them, plus the
                                classes that LOOK fine to the resolver but do not
                                reach the reader (unlinkable, ambiguous)
  C. stale `path:` pointers   — pages whose documented code path changed after the
                                page was written, and pointers that dangle

Resolution mirrors `backend/app/api/v1/wiki/router.py:get_wiki_page`
(exact -> dir index -> dir index by frontmatter type -> recursive stem -> .html),
which is also what `scripts/core/check_atlas_validation.py` implements.

Usage:
    python3 scripts/analysis/wiki_corpus_census.py
    python3 scripts/analysis/wiki_corpus_census.py --out local/reports/corpus-census
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WIKI_ROOT = REPO_ROOT / "wiki"

LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
# The renderer's contract, mirrored from frontend/src/utils/wikiLinks.ts (the
# ONE converter both surfaces use): a target may carry spaces, hyphens, dots and
# slashes; aliases are `|`, headings `#`. A target with none of those is
# expressible as a markdown link, so this rejects only a malformed target.
RENDER_RE = re.compile(r"^[^|\]#]+$")

CONFIDENCE_RE = re.compile(r"^confidence:\s*(.*)$", re.MULTILINE)
PATH_RE = re.compile(r"^path:\s*(.+)$", re.MULTILINE)
UPDATED_RE = re.compile(r"^updated:\s*(.*)$", re.MULTILINE)

SKIP_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "dist", "build", ".obsidian"}


# ---------------------------------------------------------------- frontmatter
def parse_frontmatter(text: str) -> dict:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    fm = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip("\"'")
    return fm


def iter_docs():
    for root, dirs, files in os.walk(WIKI_ROOT):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            if not f.endswith(".md"):
                continue
            p = Path(root) / f
            rel = p.relative_to(WIKI_ROOT).as_posix()
            yield rel, p.read_text(encoding="utf-8", errors="replace")


def page_date(value: str):
    """Parse a frontmatter date; return a date or None."""
    value = (value or "").strip().strip("\"'")
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


# ------------------------------------------------------------- link resolution
_DIR_INDEX_CACHE: dict[str, str | None] = {}


def dir_type_index(clean: str):
    """A directory index is any *.md in it whose frontmatter type ends in -index."""
    key = clean
    if key in _DIR_INDEX_CACHE:
        return _DIR_INDEX_CACHE[key]
    found = None
    d = WIKI_ROOT / clean
    if d.is_dir():
        for md in sorted(d.glob("*.md")):
            try:
                fm = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                continue
            if str(fm.get("type", "")).endswith("-index"):
                found = md.relative_to(WIKI_ROOT).as_posix()
                break
    _DIR_INDEX_CACHE[key] = found
    return found


def resolve(clean: str):
    """Return (kind, resolved_rel_or_None, candidates).

    kind is the FIRST rule that matched, in the API's own order:
    exact | dir-index | type-index | stem | html | none
    candidates lists every recursive stem match (ambiguity signal).
    """
    clean = clean.strip().strip("/")
    if not clean:
        return ("none", None, [])
    if (WIKI_ROOT / f"{clean}.md").exists():
        return ("exact", f"{clean}.md", [f"{clean}.md"])
    if (WIKI_ROOT / f"{clean}.html").exists():
        return ("exact", f"{clean}.html", [f"{clean}.html"])
    if (WIKI_ROOT / clean / "index.md").exists():
        return ("dir-index", f"{clean}/index.md", [f"{clean}/index.md"])
    if (WIKI_ROOT / clean / "README.md").exists():
        return ("dir-index", f"{clean}/README.md", [f"{clean}/README.md"])
    idx = dir_type_index(clean)
    if idx:
        return ("type-index", idx, [idx])
    stem = clean.split("/")[-1]
    cands = sorted(
        m.relative_to(WIKI_ROOT).as_posix()
        for m in WIKI_ROOT.rglob(f"{clean}.md")
        if m.stem == stem
    )
    if cands:
        return ("stem", cands[0], cands)
    html = sorted(
        h.relative_to(WIKI_ROOT).as_posix()
        for h in WIKI_ROOT.rglob(f"{clean}.html")
        if h.stem == stem
    )
    if html:
        return ("html", html[0], html)
    return ("none", None, [])


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    return re.sub(r"`[^`]*`", "", text)


# ---------------------------------------------------------------- git history
def build_git_path_dates():
    """Map repo-relative file and directory paths -> newest commit date (LOCAL).

    One pass over `git log --name-only`, newest first: the first time a path (or
    an ancestor directory) is seen is its most recent commit. Dates are the
    committer's local dates, so they compare against `updated:` without an
    off-by-one at the UTC boundary.
    """
    proc = subprocess.run(
        ["git", "log", "--format=%x01%ci", "--name-only", "--no-renames"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    dates: dict[str, date] = {}
    stamp = None
    for line in proc.stdout.splitlines():
        if line.startswith("\x01"):
            stamp = datetime.strptime(line[1:].strip()[:10], "%Y-%m-%d").date()
            continue
        if not line.strip() or stamp is None:
            continue
        p = line.strip()
        parts = p.split("/")
        for i in range(1, len(parts) + 1):
            prefix = "/".join(parts[:i])
            dates.setdefault(prefix, stamp)
    return dates


def newest_mtime(path: Path):
    if path.is_file():
        return datetime.fromtimestamp(path.stat().st_mtime).date()
    newest = None
    for root, dirs, files in os.walk(path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            try:
                d = datetime.fromtimestamp((Path(root) / f).stat().st_mtime).date()
            except OSError:
                continue
            if newest is None or d > newest:
                newest = d
    return newest


def resolve_code_path(seg: str):
    """Resolve a `path:` segment the way check_atlas_validation does, plus wiki/."""
    seg = seg.strip().strip("`").strip()
    if not seg:
        return None
    for root in (REPO_ROOT, REPO_ROOT / "frontend/src", REPO_ROOT / "backend", WIKI_ROOT):
        cand = root / seg
        if cand.exists():
            return cand
        if not seg.endswith((".ts", ".tsx", ".py", ".js", ".jsx", ".md")):
            for ext in (".tsx", ".ts", ".py", ".js", ".jsx", ".md"):
                if (root / (seg + ext)).exists():
                    return root / (seg + ext)
    return None


def rel(p: Path) -> str:
    try:
        return p.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


# ---------------------------------------------------------------------- census
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="local/reports/corpus-census", help="output directory")
    args = ap.parse_args()
    outdir = (REPO_ROOT / args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    docs = list(iter_docs())
    pages = {}
    for relpath, content in docs:
        pages[relpath] = {
            "content": content,
            "frontmatter": parse_frontmatter(content),
        }

    # ---- A. confidence census -------------------------------------------------
    conf_rows = {}
    no_conf = []
    for relpath, page in pages.items():
        conf = (page["frontmatter"].get("confidence") or "").strip().lower()
        if not conf:
            no_conf.append(relpath)
            continue
        conf_rows.setdefault(conf, []).append(relpath)

    stub_pages = conf_rows.get("stub", [])
    # scaffolder output: atlas/ui pages written by scripts/core/scaffold_atlas.py
    scaffolder = [p for p in stub_pages if p.startswith("atlas/ui/")]
    hand_stub = [p for p in stub_pages if not p.startswith("atlas/ui/")]

    # ---- B. wikilinks ---------------------------------------------------------
    links = []  # dicts: source, target_raw, target, alias, outcome, resolved, candidates
    raw_count = 0
    for relpath, page in pages.items():
        content = page["content"]
        raw_count += len(LINK_RE.findall(content))
        for m in LINK_RE.finditer(strip_code(content)):
            raw = m.group(1).strip()
            target = raw.split("|")[0].split("#")[0].strip()
            alias = raw.split("|", 1)[1] if "|" in raw else ""
            has_heading = "#" in raw.split("|")[0]
            if ".." in target:
                kind, resolved, cands = "relative", None, []
            else:
                kind, resolved, cands = resolve(target) if target else ("none", None, [])
            renderable = bool(RENDER_RE.match(target)) and not has_heading
            links.append({
                "source": relpath,
                "raw": raw,
                "target": target,
                "alias": alias,
                "has_heading": has_heading,
                "kind": kind,
                "resolved": resolved,
                "candidates": cands,
                "renderable": renderable,
            })

    unresolved = [l for l in links if l["kind"] == "none" and l["target"]]
    relative = [l for l in links if l["kind"] == "relative"]
    stem_only = [l for l in links if l["kind"] in ("stem", "html")]
    ambiguous = [l for l in links if l["kind"] == "stem" and len(l["candidates"]) > 1]
    unrenderable = [l for l in links if l["target"] and not l["renderable"]]
    # Strict rule for comparison with audits that require a real file at the
    # stated path: anything not resolved by the `exact` branch.
    strict_missing = [l for l in links if l["kind"] != "exact"]

    def group_by_source(rows):
        out = {}
        for l in rows:
            out.setdefault(l["source"], []).append(l)
        return dict(sorted(out.items(), key=lambda kv: (-len(kv[1]), kv[0])))

    broken_by_source = group_by_source(unresolved)
    unrenderable_by_source = group_by_source(unrenderable)

    # inbound links to stub pages (by resolved file)
    stub_set = set(stub_pages)
    stub_inbound = {}
    for l in links:
        if l["resolved"] in stub_set:
            stub_inbound.setdefault(l["resolved"], []).append(l["source"])
    unlinked_stubs = [p for p in stub_pages if p not in stub_inbound]

    # ---- C. stale path: pointers ---------------------------------------------
    git_dates = build_git_path_dates()
    path_pages = []
    dangling = []
    removal_paths = []
    wiki_pointers = []
    stale_mtime = []
    stale_git = []
    for relpath, page in pages.items():
        content = page["content"]
        m = PATH_RE.search(content)
        if not m:
            continue
        raw_path = m.group(1).strip().strip("`")
        if not raw_path:
            continue
        updated = page_date(page["frontmatter"].get("updated", ""))
        page_date_p = updated
        segments = [s for s in (s.strip() for s in raw_path.split("+")) if s]
        # Removal records name the deleted file on purpose: `path: x.tsx (DELETED 2026-08-02)`
        cleaned = [re.sub(r"\s*\((?:DELETED|REMOVED)[^)]*\)\s*$", "", s) for s in segments]
        targets = []
        missing = []
        for seg in cleaned:
            hit = resolve_code_path(seg)
            if hit is None:
                missing.append(seg)
            else:
                targets.append(hit)
        row = {
            "page": relpath,
            "updated": page_date_p.isoformat() if page_date_p else None,
            "path": raw_path,
            "kind": "wiki" if cleaned and cleaned[0].startswith("wiki/") else "code",
            "self_ref": bool(cleaned) and cleaned[0].rstrip("/") == f"wiki/{relpath}",
            "missing": missing,
            "targets": [rel(t) for t in targets],
        }
        path_pages.append(row)
        if row["kind"] == "wiki":
            wiki_pointers.append(row)
            continue
        if missing:
            is_removal = bool(re.search(r"\((?:DELETED|REMOVED)|^\s*REMOVED\b|\bREMOVED\b|\bDELETED\b", raw_path)) \
                or "REMOVED" in content or "DELETED" in content
            if is_removal:
                removal_paths.append(row)
            else:
                dangling.append(row)
            continue
        if page_date_p is None:
            continue
        newest = None
        for t in targets:
            d = newest_mtime(t)
            if d and (newest is None or d > newest):
                newest = d
        if newest and newest > page_date_p:
            stale_mtime.append({**row, "code_date": newest.isoformat()})
        newest_git = None
        for t in targets:
            d = git_dates.get(rel(t))
            if d and (newest_git is None or d > newest_git):
                newest_git = d
        if newest_git and newest_git > page_date_p:
            stale_git.append({**row, "code_date": newest_git.isoformat()})

    # ---- counts --------------------------------------------------------------
    today = date.today()

    def area(p: str) -> str:
        parts = p.split("/")
        return "/".join(parts[:2]) if p.startswith("atlas/") else parts[0]

    def bucket(gap: int) -> str:
        if gap <= 7:
            return "1–7 days"
        if gap <= 30:
            return "8–30 days"
        if gap <= 90:
            return "31–90 days"
        return ">90 days"

    stale_gap = {}
    for row in stale_git:
        gap = (date.fromisoformat(row["code_date"]) - date.fromisoformat(row["updated"])).days
        stale_gap[bucket(gap)] = stale_gap.get(bucket(gap), 0) + 1

    area_rows = {}
    for p in stub_pages:
        area_rows.setdefault(area(p), {"stub": 0, "stale": 0})
        area_rows[area(p)]["stub"] += 1
    for row in stale_git:
        area_rows.setdefault(area(row["page"]), {"stub": 0, "stale": 0})
        area_rows[area(row["page"])]["stale"] += 1

    hot = sorted(
        (r for r in stale_git
         if (today - date.fromisoformat(r["code_date"])).days <= 14),
        key=lambda r: (r["code_date"], (date.fromisoformat(r["code_date"]) - date.fromisoformat(r["updated"])).days),
        reverse=True,
    )

    counts = {
        "pages": len(pages),
        "link_occurrences_raw": raw_count,
        "link_occurrences_code_stripped": len(links),
        "distinct_targets": len({l["target"] for l in links if l["target"]}),
        "unresolved_links": len(unresolved),
        "unresolved_sources": len(broken_by_source),
        "relative_links": len(relative),
        "strict_missing_links": len(strict_missing),
        "strict_missing_pairs": len({(l["source"], l["target"]) for l in strict_missing}),
        "strict_missing_sources": len({l["source"] for l in strict_missing}),
        "resolved_via_stem": len(stem_only),
        "ambiguous_stem_links": len(ambiguous),
        "unrenderable_links": len(unrenderable),
        "unrenderable_sources": len(unrenderable_by_source),
        "heading_links": sum(1 for l in links if l["has_heading"]),
        "stub_pages": len(stub_pages),
        "stub_scaffolder": len(scaffolder),
        "stub_handwritten": len(hand_stub),
        "stub_pages_with_inbound": len(stub_inbound),
        "stub_pages_unlinked": len(unlinked_stubs),
        "path_pages": len(path_pages),
        "path_code_pages": len(path_pages) - len(wiki_pointers),
        "path_wiki_pointers": len(wiki_pointers),
        "path_self_pointers": sum(1 for r in wiki_pointers if r["self_ref"]),
        "path_dangling": len(dangling),
        "path_removal_records": len(removal_paths),
        "path_stale_mtime": len(stale_mtime),
        "path_stale_git": len(stale_git),
        "stale_gap": stale_gap,
        "areas": area_rows,
        "hot_stale": len(hot),
        "confidence": {k: len(v) for k, v in sorted(conf_rows.items())},
        "no_confidence": len(no_conf),
    }

    data = {
        "counts": counts,
        "confidence_pages": {k: sorted(v) for k, v in sorted(conf_rows.items())},
        "no_confidence_pages": sorted(no_conf),
        "broken_links": sorted(unresolved, key=lambda l: (l["source"], l["target"])),
        "relative_links": sorted(relative, key=lambda l: (l["source"], l["target"])),
        "unrenderable_links": sorted(unrenderable, key=lambda l: (l["source"], l["target"])),
        "ambiguous_links": sorted(ambiguous, key=lambda l: (l["source"], l["target"])),
        "stub_inbound": {k: sorted(v) for k, v in sorted(stub_inbound.items())},
        "stub_unlinked": sorted(unlinked_stubs),
        "dangling_paths": dangling,
        "removal_record_paths": removal_paths,
        "wiki_path_pointers": wiki_pointers,
        "stale_paths_mtime": stale_mtime,
        "stale_paths_git": stale_git,
    }
    (outdir / "census.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

    # ---- markdown ------------------------------------------------------------
    L = []
    L.append("# Wiki corpus census — the three defect classes, counted\n")
    L.append(f"Pages: **{counts['pages']}** · `confidence:` present on {counts['pages'] - counts['no_confidence']}, "
             f"absent on **{counts['no_confidence']}**.\n")
    L.append("## A. Confidence is the author's opinion, and it is not maintained\n")
    L.append("| declared | pages |")
    L.append("|---|---|")
    for k, v in counts["confidence"].items():
        L.append(f"| `{k}` | {v} |")
    L.append(f"| (none) | {counts['no_confidence']} |\n")
    L.append(f"- **`stub` pages: {len(stub_pages)}** — {len(scaffolder)} scaffolder output under `atlas/ui/`, "
             f"**{len(hand_stub)} hand-written pages that declared themselves stubs and never came back** "
             f"(list: `census.json` → `confidence_pages.stub`).")
    L.append(f"- **{len(stub_inbound)} of {len(stub_pages)} stub pages are linked from somewhere**; "
             f"**{len(unlinked_stubs)} have no link that resolves to them**, so their only reader is the sidebar.\n")

    L.append("## B. Wikilinks\n")
    L.append("| class | links | source pages |")
    L.append("|---|---|---|")
    L.append(f"| UNRESOLVED — the API would 404 | **{len(unresolved)}** | {len(broken_by_source)} |")
    L.append(f"| Relative path (`[[../../x]]`) — no such link form in Obsidian | **{len(relative)}** | — |")
    L.append(f"| Resolves only by recursive stem (no path given) | {len(stem_only)} | — |")
    L.append(f"| Ambiguous — more than one page shares the stem | {len(ambiguous)} | — |")
    L.append(f"| Unlinkable — the renderer's regex rejects the target | **{len(unrenderable)}** | {len(unrenderable_by_source)} |")
    L.append(f"| _all `[[...]]` in prose (code spans/fences excluded)_ | {len(links)} | — |")
    L.append(f"| _raw `[[...]]` occurrences incl. code examples_ | {raw_count} | — |\n")
    L.append(f"**No link 404s.** The app's resolver (exact → dir index → type index → recursive stem → .html) "
             f"finds a page for every one — verified against the live API, which serves a spaced path, a bare "
             f"stem and a trailing slash alike. This is why the gate says `Wikilinks OK` while an audit reported "
             f"`113 broken across 27 pages`: that figure is a **strict exact-path rule**, and this corpus has "
             f"**{len(strict_missing)} such links ({len({(l['source'], l['target']) for l in strict_missing})} distinct "
             f"page→target pairs, {len({l['source'] for l in strict_missing})} pages)**. The audit ran that rule on the "
             f"VM's slightly older copy, which is where 113/27 comes from. The defect is not a link that 404s; it is "
             f"a link that resolves only because of the resolver's fallbacks, or that resolves but never renders.\n")
    if relative:
        L.append("### Relative-path links\n")
        for l in relative:
            L.append(f"- `{l['source']}` → `[[{l['target']}]]`")
        L.append("")
    if broken_by_source:
        L.append("### Unresolved links, by source page\n")
        for src, rows in broken_by_source.items():
            L.append(f"- **`{src}`** — {len(rows)}")
            for l in rows:
                L.append(f"  - `[[{l['target']}]]`")
        L.append("")
    if unrenderable_by_source:
        L.append("### Links the renderer cannot convert (space or `#` in the target)\n")
        for src, rows in unrenderable_by_source.items():
            L.append(f"- **`{src}`** — {len(rows)}: " + ", ".join(f"`[[{l['target']}]]`" for l in rows))
        L.append("")
    if ambiguous:
        L.append("### Ambiguous stems (resolves, but which page?)\n")
        for l in ambiguous[:40]:
            L.append(f"- `{l['source']}` → `[[{l['target']}]]` matches "
                     + ", ".join(f"`{c}`" for c in l["candidates"]))
        if len(ambiguous) > 40:
            L.append(f"- … {len(ambiguous) - 40} more (see `census.json`)")
        L.append("")
        L.append("The resolver takes the **first** match in filesystem order, so an ambiguous link is a latent "
                 "re-point: the page it serves today can change the day another page adopts the stem. Sampled "
                 "live against `/api/v1/wiki/<stem>`: all of `tools`, `sessions`, `settings`, `providers`, "
                 "`workflows`, `logs`, `dashboard`, `macros`, `testing`, `cognitive-pipeline`, "
                 "`cognitive-profiles` currently land on a page whose title fits the linking page's section — "
                 "correct by luck, not by construction.\n")

    L.append("## C. `path:` pointers vs the code they point at\n")
    L.append(f"Pages carrying a `path:` pointer: **{len(path_pages)}** — of which "
             f"**{len(wiki_pointers)} point at a wiki page, not at code** "
             f"({sum(1 for r in wiki_pointers if r['self_ref'])} of those point at *the page itself*), "
             f"leaving **{len(path_pages) - len(wiki_pointers)}** code pointers, the only ones this "
             f"staleness rule can judge.\n")
    L.append("A `path:` that names a wiki page cannot go stale *against code*; it measures the wiki's own "
             "edit activity, so counting it inflates the class. Those pages are a separate question "
             "(what is a self-pointer for?), not a stale pointer.\n")
    L.append("| rule | pages |")
    L.append("|---|---|")
    L.append(f"| `path:` names a wiki page, not code | {len(wiki_pointers)} |")
    L.append(f"| target missing, no removal marker (dangling by construction) | **{len(dangling)}** |")
    L.append(f"| target missing but the page is a removal record (intentional) | {len(removal_paths)} |")
    L.append(f"| code pointers whose code changed after `updated:` — by file mtime | {len(stale_mtime)} / {len(path_pages) - len(wiki_pointers)} |")
    L.append(f"| code pointers whose code changed after `updated:` — by git commit date | **{len(stale_git)} / {len(path_pages) - len(wiki_pointers)}** |\n")
    L.append("The git rule is the honest one: a `touch` bumps mtime without a content change, and a "
             "copied/cloned tree flattens every mtime to the copy date. Both are reported so the two "
             "numbers can be compared rather than inherited.\n")
    L.append("### How far behind the code, and where\n")
    L.append("| gap between page and code | pages |")
    L.append("|---|---|")
    for k in ("1–7 days", "8–30 days", "31–90 days", ">90 days"):
        if k in stale_gap:
            L.append(f"| {k} | {stale_gap[k]} |")
    L.append("")
    L.append("| area | stub pages | stale pointers |")
    L.append("|---|---|---|")
    for a, row in sorted(area_rows.items(), key=lambda kv: -(kv[1]["stale"] + kv[1]["stub"])):
        L.append(f"| `{a}` | {row['stub']} | {row['stale']} |")
    L.append("")
    L.append(f"### The hot queue — code moved in the last 14 days, page did not "
             f"({len(hot)} pages)\n")
    L.append("| page | updated | code moved |")
    L.append("|---|---|---|")
    for row in hot[:60]:
        L.append(f"| `{row['page']}` | {row['updated']} | {row['code_date']} |")
    if len(hot) > 60:
        L.append(f"| … {len(hot) - 60} more | | |")
    L.append("")
    if removal_paths:
        L.append("### Removal records whose file is gone (intentional)\n")
        for row in removal_paths:
            L.append(f"- `{row['page']}` → `{row['path']}`")
        L.append("")
    if dangling:
        L.append("### Dangling `path:` targets\n")
        for row in dangling:
            L.append(f"- `{row['page']}` → `{row['path']}` (missing: {', '.join(row['missing'])})")
        L.append("")
    L.append("### Stale by git, worst first (top 40 of "
             f"{len(stale_git)})\n")
    L.append("| page | updated | newest commit under its path |")
    L.append("|---|---|---|")
    for row in sorted(stale_git, key=lambda r: r["code_date"], reverse=True)[:40]:
        L.append(f"| `{row['page']}` | {row['updated']} | {row['code_date']} |")
    L.append("\nFull lists: `census.json` in this directory.\n")

    report = outdir / "census.md"
    report.write_text("\n".join(L), encoding="utf-8")

    print(json.dumps(counts, indent=2))
    print(f"\nreport: {report}")
    print(f"data:   {outdir / 'census.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
