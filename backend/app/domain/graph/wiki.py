"""The wiki graph provider (Phase 5, 2026-08-19).

Option C from the study: the wiki's pages + hard wikilinks +
categories as the KNOWLEDGE graph. The house convention: wikilinks
are HARD links (the atlas validator enforces broken-link checks) —
so the link graph is real. Complements the derived FK graph
(a graph of DOCS, not of the system).

Parsing mirrors the atlas validator (scripts/core/
check_atlas_validation.py): frontmatter + iter_docs + wikilink
extraction.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import Paths
from app.domain.graph import GraphProvider

WIKI_ROOT = Paths.wiki_dir

WIKILINK_RE = re.compile(r"\[\[([^|\]]+)(?:\|[^\]]+)?\]\]")


def _parse_frontmatter(text: str) -> dict:
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"\'')
    return fm


class WikiGraphProvider(GraphProvider):
    """The wiki pages + wikilinks + categories as nodes/edges."""

    def _docs(self) -> List[Dict[str, Any]]:
        """Every page: {id (rel path), title, category, links}."""
        out = []
        for root, _dirs, files in os_walk(WIKI_ROOT):
            for f in sorted(files):
                if not f.endswith(".md"):
                    continue
                path = Path(root) / f
                rel = path.relative_to(WIKI_ROOT).as_posix()
                try:
                    content = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                fm = _parse_frontmatter(content)
                links = sorted({t.strip() for t in WIKILINK_RE.findall(content)})
                out.append({
                    "id": rel,
                    "title": fm.get("title") or path.stem,
                    "category": fm.get("category", ""),
                    "links": links,
                })
        return out

    def get_entity(self, entity_id: str) -> Dict[str, Any] | None:
        # the entity id is a page path, a bare basename, OR a title
        # ('workflow-system' -> wiki/entities/workflow-system.md;
        #  'Workflow System' -> the title) — Phase 5, 2026-08-19.
        target = entity_id.strip()
        if not target.endswith(".md"):
            target = target + ".md"
        for d in self._docs():
            if (
                d["id"] == target
                or d["title"] == entity_id.strip()
                or Path(d["id"]).name == target
                or Path(d["id"]).stem == entity_id.strip()
            ):
                return {
                    "id": d["id"],
                    "kind": "wiki-page",
                    "name": d["title"],
                    "category": d["category"],
                }
        return None

    def get_neighbors(self, entity_id: str, depth: int = 1) -> Dict[str, Any]:
        docs = self._docs()
        entity = self.get_entity(entity_id)
        if entity is None:
            return {"entity": entity_id, "edges": []}
        page_id = entity["id"]
        edges: List[Dict[str, Any]] = []
        by_id = {d["id"]: d for d in docs}
        # outgoing: the page's wikilinks
        for link in by_id.get(page_id, {}).get("links", []):
            resolved = _resolve_link(link, docs)
            if resolved:
                edges.append({
                    "kind": "links-to",
                    "direction": "out",
                    "to": resolved["id"],
                    "to_kind": "wiki-page",
                })
        # incoming: pages that link to this one
        for d in docs:
            incoming_ids = [
                resolved["id"]
                for l in d.get("links", [])
                if (resolved := _resolve_link(l, docs)) is not None
            ]
            if page_id in incoming_ids:
                edges.append({
                    "kind": "linked-by",
                    "direction": "in",
                    "to": d["id"],
                    "to_kind": "wiki-page",
                })
        return {"entity": entity_id, "edges": edges}

    def get_topology(self, kind: str | None = None) -> Dict[str, Any]:
        if kind and kind != "wiki-page":
            return {"nodes": [], "edges": []}
        docs = self._docs()
        nodes = [
            {"id": d["id"], "kind": "wiki-page", "name": d["title"]}
            for d in docs
        ]
        edges: List[Dict[str, Any]] = []
        for d in docs:
            for link in d["links"]:
                resolved = _resolve_link(link, docs)
                if resolved:
                    edges.append({
                        "kind": "links-to",
                        "from": d["id"],
                        "to": resolved["id"],
                    })
        return {"nodes": nodes, "edges": edges}


def _resolve_link(target: str, docs: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    """Resolve a wikilink to a page (exact -> title -> dir index)."""
    clean = target.strip()
    for d in docs:
        if d["id"] == clean or d["id"] == clean + ".md":
            return d
    for d in docs:
        if d["title"] == clean:
            return d
    # dir index: clean/index.md or clean/README.md
    for suffix in ("index.md", "README.md"):
        for d in docs:
            if d["id"] == f"{clean}/{suffix}":
                return d
    return None


def os_walk(root: Path):
    """os.walk wrapper (import at module top for clarity)."""
    import os as _os
    for r, dirs, fs in _os.walk(root):
        if ".obsidian" in r or "__pycache__" in r:
            dirs[:] = [d for d in dirs if d not in (".obsidian", "__pycache__")]
        yield r, dirs, fs
