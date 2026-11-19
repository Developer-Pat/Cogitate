#!/usr/bin/env python3
"""Generate the page map from the frontend's own route table.

WHY THIS EXISTS
---------------
The `open-page` tool's enum has to BE the app's real pages. A hand-kept list
drifts, and the failure is silent — the model picks a page that no longer
exists and the jump 404s. So the list is GENERATED from
`frontend/src/config/routes.ts` (the single source of truth) and a test
asserts the two never disagree.

The frontend derives its own map the same way (`services/appNavigation.ts`
`pageMap()`), so both sides answer to routes.ts.

WHAT IT PRODUCES
----------------
`backend/app/domain/tools/page_map.json` — committed, and read by the backend
tool registry at import. Three kinds of entry, because the app has three:

  route   a path from routes.ts (`/settings`)
  alias   a surface that is NOT a route — the Settings tabs are useState,
          so they cannot be derived (`/settings?tab=appearance`)
  tab     an app that opens as its own tab (`exa`, `messages`, ...)

USAGE
-----
    python3 scripts/core/gen_page_map.py            # write the map
    python3 scripts/core/gen_page_map.py --check    # exit 1 if it is stale

The `--check` form is what the sync test and the sweep call.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTES_TS = REPO_ROOT / "frontend" / "src" / "config" / "routes.ts"
NAV_TS = REPO_ROOT / "frontend" / "src" / "services" / "appNavigation.ts"
OUT_JSON = REPO_ROOT / "backend" / "app" / "domain" / "tools" / "page_map.json"


class ParseError(RuntimeError):
    """The source no longer looks like what we know how to read.

    Raised LOUDLY. A parser that quietly returns fewer entries would make the
    map shrink without anyone noticing, which is the exact failure this script
    exists to prevent.
    """


def _strip_comment(line: str) -> str:
    """Drop a trailing // comment, leaving string contents alone."""
    out, in_str, quote = [], False, ""
    i = 0
    while i < len(line):
        ch = line[i]
        if in_str:
            out.append(ch)
            if ch == "\\":
                if i + 1 < len(line):
                    out.append(line[i + 1])
                    i += 2
                    continue
            elif ch == quote:
                in_str = False
        else:
            if ch in "'\"":
                in_str, quote = True, ch
                out.append(ch)
            elif ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                break
            else:
                out.append(ch)
        i += 1
    return "".join(out)


def _js_str(raw: str) -> str:
    """Unescape a single-quoted or double-quoted JS string literal."""
    body = raw.strip()[1:-1]
    return (
        body.replace("\\'", "'")
        .replace('\\"', '"')
        .replace("\\n", "\n")
        .replace("\\\\", "\\")
    )


def parse_routes() -> tuple[list[dict], int]:
    """Return (entries, raw_object_count).

    The raw count is returned so the caller can assert nothing was skipped —
    see the guard in build_map().
    """
    text = ROUTES_TS.read_text()
    start = text.index("export const routes: RouteConfig[] = [")
    end = text.index("\n]", start)
    body = text[start:end]

    entries: list[dict] = []
    # Each route object opens with an indented `path:` line.
    for chunk in re.split(r"\n(?=  \{)", body):
        m_path = re.search(r"^\s*path:\s*(['\"])(.*?)\1\s*,", chunk, re.M)
        if not m_path:
            continue
        path = m_path.group(2)
        m_title = re.search(r"^\s*title:\s*(['\"])(.*?)\1\s*,", chunk, re.M)
        m_desc = re.search(r"^\s*description:\s*(['\"])(.*?)\1\s*,", chunk, re.M)
        m_auth = re.search(r"^\s*requiresAuth:\s*(true|false)\s*,", chunk, re.M)
        entries.append(
            {
                "path": path,
                "title": m_title.group(2).strip() if m_title else path,
                "description": m_desc.group(2).strip() if m_desc else "",
                "requires_auth": (m_auth.group(1) == "true") if m_auth else True,
            }
        )
    raw = len(re.findall(r"^\s{4}path:\s*['\"]", body, re.M))
    return entries, raw


def parse_nav_tables() -> tuple[list[dict], int]:
    """Return (alias+tab entries, raw_object_count) from appNavigation.ts."""
    text = NAV_TS.read_text()
    entries: list[dict] = []
    raw = 0

    for const_name, kind in (("ALIASES", "alias"), ("TAB_APPS", "tab")):
        m = re.search(rf"const {const_name}[^=]*=\s*\[(.*?)\n\]", text, re.S)
        if not m:
            raise ParseError(f"{const_name} table not found in {NAV_TS.name}")
        block = m.group(1)
        for chunk in re.split(r"\n(?=  \{)", block):
            m_to = re.search(r"\bto:\s*(['\"])(.*?)\1", chunk)
            m_app = re.search(r"\bapp:\s*(['\"])(.*?)\1", chunk)
            m_label = re.search(r"\blabel:\s*(['\"])(.*?)\1", chunk)
            m_match = re.search(r"\bmatch:\s*\[(.*?)\]", chunk, re.S)
            if not (m_to or m_app) or not m_match:
                continue
            matches = [m.group(2) for m in re.finditer(r"(['\"])(.*?)\1", m_match.group(1))]
            matches = [m for m in matches if m]
            entry = {
                "kind": kind,
                "label": m_label.group(2).strip() if m_label else "",
                "match": matches,
            }
            if m_app is not None:
                entry["app"] = m_app.group(2).strip()
            elif m_to is not None:
                entry["to"] = m_to.group(2).strip()
            else:  # unreachable — the guard above requires one of them
                continue
            entries.append(entry)
            raw += 1
    return entries, raw


def build_map() -> dict:
    routes, raw_routes = parse_routes()
    nav, raw_nav = parse_nav_tables()

    # THE GUARD, in two parts. Both matter: the count comparison alone passes
    # when the parser finds NOTHING (0 == 0), which is the silent-short-map
    # failure this script exists to prevent.
    if not routes:
        raise ParseError(
            "parsed ZERO route objects from routes.ts — the file's shape changed "
            "or the table moved. Refusing to emit an empty map."
        )
    if not nav:
        raise ParseError(
            "parsed ZERO nav entries (ALIASES/TAB_APPS) from appNavigation.ts — "
            "refusing to emit a map without them."
        )
    if len(routes) != raw_routes:
        raise ParseError(
            f"parsed {len(routes)} route objects but found {raw_routes} `path:` lines "
            f"— the routes.ts shape changed and this parser no longer reads it"
        )
    if len(nav) != raw_nav:
        raise ParseError(
            f"parsed {len(nav)} nav entries but found {raw_nav} entries — "
            f"the appNavigation.ts shape changed"
        )

    # The SAME filter the frontend uses: getNavigationRoutes() keeps auth
    # routes and drops the wildcard; pageMap() additionally drops params.
    pages = [
        {"kind": "route", "path": r["path"], "title": r["title"], "description": r["description"]}
        for r in routes
        if r["path"] != "*" and r["requires_auth"] and "*" not in r["path"] and ":" not in r["path"]
    ]
    pages = sorted(pages, key=lambda p: p["path"])

    return {
        "_generated_by": "scripts/core/gen_page_map.py",
        "_source": ["frontend/src/config/routes.ts", "frontend/src/services/appNavigation.ts"],
        "counts": {"routes": len(pages), "aliases": sum(1 for n in nav if n["kind"] == "alias"),
                   "tabs": sum(1 for n in nav if n["kind"] == "tab")},
        "pages": pages,
        "aliases": [n for n in nav if n["kind"] == "alias"],
        "tabs": [n for n in nav if n["kind"] == "tab"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed map is stale")
    args = ap.parse_args()

    try:
        fresh = build_map()
    except ParseError as exc:
        print(f"PARSE FAILED: {exc}", file=sys.stderr)
        return 2

    rendered = json.dumps(fresh, indent=2, ensure_ascii=False) + "\n"
    if args.check:
        current = OUT_JSON.read_text() if OUT_JSON.exists() else ""
        if current != rendered:
            print(
                "PAGE MAP IS STALE — run `python3 scripts/core/gen_page_map.py`\n"
                "  (a route changed without regenerating the tool's enum; the model\n"
                "   would be offered a page that no longer exists)",
                file=sys.stderr,
            )
            return 1
        print(f"page map is in sync ({fresh['counts']})")
        return 0

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(rendered)
    print(f"wrote {OUT_JSON.relative_to(REPO_ROOT)}  {fresh['counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
