"""Wiki Viewer API Router.

Serves markdown files from the project's wiki/ directory.
Mounts at /api/v1/wiki/* via api/v1/router.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/wiki", tags=["wiki"])

# Resolve wiki/ relative to project root (4 levels up from this file)
from app.core.config import Paths, get_settings
WIKI_ROOT = Paths.from_settings(get_settings()).wiki_dir


class WikiPageResponse(BaseModel):
    path: str
    title: str
    content: str
    frontmatter: dict
    children: list[dict]


class WikiIndexResponse(BaseModel):
    tree: list[dict]


class WikiHelpListResponse(BaseModel):
    context: str
    pages: list[dict]


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and return (frontmatter_dict, body)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        return {}, text

    fm_lines = lines[1:end_idx]
    body = "\n".join(lines[end_idx + 1:])

    fm: dict = {}
    for line in fm_lines:
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"\'\"')

    return fm, body


def _build_tree(dir_path: Path, prefix: str = "") -> list[dict]:
    """Build a recursive tree of wiki files and directories."""
    entries = []
    try:
        for entry in sorted(dir_path.iterdir()):
            if entry.name.startswith(".") or entry.name == "_archive":
                continue
            if entry.is_dir():
                child_prefix = f"{prefix}/{entry.name}" if prefix else entry.name
                sub = _build_tree(entry, child_prefix)
                entries.append({
                    "name": entry.name,
                    "path": child_prefix,
                    "type": "directory",
                    "children": sub,
                })
            elif entry.suffix in (".md", ".html"):
                name = entry.stem
                # Read title from frontmatter (md) or <title> tag (html)
                try:
                    text = entry.read_text(encoding="utf-8")
                    if entry.suffix == ".md":
                        fm, _ = _parse_frontmatter(text)
                        title = fm.get("title", name)
                    else:
                        # Extract <title> from HTML
                        import re as _re
                        m = _re.search(r"<title>(.+?)</title>", text, _re.IGNORECASE)
                        title = m.group(1) if m else name
                except Exception:
                    title = name
                entries.append({
                    "name": title,
                    "path": str(entry.relative_to(WIKI_ROOT).with_suffix("")),
                    "type": "file",
                })
    except PermissionError:
        pass
    return entries


@router.get("", response_model=WikiIndexResponse)
@router.get("/", response_model=WikiIndexResponse)
async def get_wiki_index(response: Response):
    """Return the full wiki tree structure."""
    # THE NO-CACHE (2026-08-30, the user's 'got nothing'): the wiki's
    # mutable — a browser's heuristic cache (from before a help page
    # landed) made the Help modal miss new pages.
    response.headers["Cache-Control"] = "no-cache"
    if not WIKI_ROOT.exists():
        raise HTTPException(status_code=404, detail="Wiki directory not found")
    tree = _build_tree(WIKI_ROOT)
    return WikiIndexResponse(tree=tree)


@router.get("/help", response_model=WikiHelpListResponse)
async def get_wiki_help_context(context: str, response: Response):
    """
    Return help pages for a given context (category), sorted by frontmatter 'order'.
    Used by HelpModal to load context-sensitive help content.
    """
    response.headers["Cache-Control"] = "no-cache"
    help_dir = WIKI_ROOT / "help"
    if not help_dir.exists():
        raise HTTPException(status_code=404, detail="Help directory not found")

    pages = []
    for md_file in sorted(help_dir.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
            fm, body = _parse_frontmatter(text)
            category = fm.get("category", "")
            if category == context:
                order_str = fm.get("order", "99")
                try:
                    order = int(order_str)
                except ValueError:
                    order = 99
                pages.append({
                    "slug": md_file.stem,
                    "title": fm.get("title", md_file.stem),
                    "category": category,
                    "subtopic": fm.get("subtopic", "General"),
                    "order": order,
                    "content": body,
                    "summary": fm.get("summary", ""),
                    "frontmatter": fm,
                })
        except Exception as e:
            logger.warning(f"Failed to parse help page {md_file.name}: {e}")

    # Sort by order, then by title
    pages.sort(key=lambda p: (p["order"], p["title"]))

    return WikiHelpListResponse(context=context, pages=pages)


class WikiSearchResponse(BaseModel):
    query: str
    results: list[dict]
    count: int


@router.get("/search", response_model=WikiSearchResponse)
async def search_wiki(q: str = "", prefix: str = ""):
    """Search the wiki by title + content keywords.

    THE EXPERTISE WIRING (2026-08-22): Exa hit /wiki/index -> 404 and
    gave up — there was no search. This scans the wiki's markdown files
    (title + body, frontmatter-aware) and returns ranked matches, so an
    agent can FIND pages, not just fetch known paths.

    THE NAMESPACE FILTER (2026-09-15, the ask-Exa command verbs): the
    `dev` and `atlas` verbs are namespace-scoped — "dev architecture"
    means a note under dev-notes/ — and the GLOBAL top-10 can crowd a
    namespace out entirely, so the verb would find nothing while ten
    unrelated pages scored higher. Filtering here (before scoring) keeps
    the verb honest.
    """
    q = q.strip()
    if not q or not WIKI_ROOT.exists():
        return WikiSearchResponse(query=q, results=[], count=0)

    # tokenize the query (lowercase, split on non-alphanumerics)
    import re as _re
    terms = [t for t in _re.split(r"[^a-zA-Z0-9]+", q.lower()) if t]

    # a namespace scope, normalised ("dev-notes/", "/dev-notes" -> "dev-notes")
    scope = prefix.strip().strip("/")

    results = []
    for md_file in WIKI_ROOT.rglob("*.md"):
        if "_archive" in md_file.parts or md_file.name.startswith("."):
            continue
        if scope and not str(md_file.relative_to(WIKI_ROOT)).startswith(scope + "/"):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        fm, body = _parse_frontmatter(text)
        title = fm.get("title", md_file.stem)
        haystack = f"{title} {body}".lower()

        # score: title hits weigh 3x, body hits 1x; require >=1 term
        score = 0
        for t in terms:
            if t in title.lower():
                score += 3
            elif t in haystack:
                score += 1
        if score == 0:
            continue

        # snippet around the first term hit
        snippet = ""
        for t in terms:
            idx = haystack.find(t)
            if idx >= 0:
                start = max(0, idx - 60)
                snippet = body[start:idx + 120].strip()
                break
        rel = str(md_file.relative_to(WIKI_ROOT).with_suffix(""))
        results.append({
            "path": rel,
            "title": title,
            "score": score,
            "snippet": (snippet or body[:240]).replace("\n", " ")[:300],
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return WikiSearchResponse(query=q, results=results[:10], count=len(results))


@router.get("/{path:path}", response_model=WikiPageResponse)
async def get_wiki_page(path: str, response: Response):
    """Return a wiki page by its file path (without .md)."""
    response.headers["Cache-Control"] = "no-cache"
    if not path:
        path = "index"

    # Security: prevent directory traversal
    clean_path = Path(path).as_posix()
    if ".." in clean_path or clean_path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")

    file_path = WIKI_ROOT / f"{clean_path}.md"
    if not file_path.exists():
        # Try as index within a directory
        file_path = WIKI_ROOT / clean_path / "index.md"
    if not file_path.exists():
        # README.md was the old dir-index convention (retained for links)
        file_path = WIKI_ROOT / clean_path / "README.md"
    if not file_path.exists():
        # Index files now carry descriptive names (e.g. "Pages Index.md",
        # "UI Atlas.md") — find the directory's index by frontmatter type.
        _dir = WIKI_ROOT / clean_path
        if _dir.is_dir():
            for _md in sorted(_dir.glob("*.md")):
                try:
                    _fm, _ = _parse_frontmatter(_md.read_text(encoding="utf-8"))
                    if _fm.get("type", "").endswith("-index"):
                        file_path = _md
                        break
                except Exception:
                    continue
    if not file_path.exists():
        # Search recursively — wikilinks may omit the directory prefix
        for md_file in WIKI_ROOT.rglob(f"{clean_path}.md"):
            # Ensure we're matching the stem, not a partial match
            if md_file.stem == clean_path.split("/")[-1]:
                file_path = md_file
                break
    if not file_path.exists():
        # Try as .html file
        file_path = WIKI_ROOT / f"{clean_path}.html"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Wiki page not found: {path}")

    # Ensure we're still within WIKI_ROOT
    try:
        file_path = file_path.resolve()
        file_path.relative_to(WIKI_ROOT.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    text = file_path.read_text(encoding="utf-8")
    if file_path.suffix == ".html":
        # Serve HTML files directly as raw content
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=text)
    fm, body = _parse_frontmatter(text)
    title = fm.get("title", file_path.stem)

    # Build children list (files in same directory)
    children = []
    if file_path.parent != WIKI_ROOT:
        for sibling in sorted(file_path.parent.iterdir()):
            if sibling.suffix == ".md" and sibling.name != file_path.name:
                try:
                    stext = sibling.read_text(encoding="utf-8")
                    sfm, _ = _parse_frontmatter(stext)
                    children.append({
                        "name": sfm.get("title", sibling.stem),
                        "path": str(sibling.relative_to(WIKI_ROOT).with_suffix("")),
                    })
                except Exception:
                    pass

    return WikiPageResponse(
        path=clean_path,
        title=title,
        content=body,
        frontmatter=fm,
        children=children,
    )
