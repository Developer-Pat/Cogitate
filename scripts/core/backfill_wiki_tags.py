#!/usr/bin/env python3
"""Backfill tags: for every wiki .md WITHOUT tags, derive from
frontmatter + path and append a flow-style tags: line.

Scheme (Obsidian testbed):
  type/<t>          — from frontmatter type: (atlas-component → type/component)
  domain/<d>        — from top-level wiki dir (atlas/ui → domain/ui-atlas;
                      dev-notes → domain/dev-notes; root files → domain/root)
  status/<v>        — ONLY when a real verdict exists in frontmatter
                      (status: active|dormant|orphaned|dead|...). No
                      status/unknown noise.
  (confidence/* is deliberately absent — it is a property, not a classification, and it cliques the
   Obsidian graph across domains)

Idempotent: files with a tags: line are skipped.
"""

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
WIKI = REPO_ROOT / "wiki"

TYPE_STRIP = {
    "atlas-component": "component",
    "atlas-service": "service",
    "atlas-index": "index",
    "atlas-devnote": "devnote",
    "atlas-api": "api",
    "atlas-hook": "hook",
    "atlas-page": "page",
    "atlas-store": "store",
    "atlas-entity": "entity",
    "atlas-architecture": "architecture",
    "atlas-docs": "docs",
    "atlas-example": "example",
    "wiki-index": "wiki-index",
}

# top-level dir → domain tag (deeper api-atlas pages keep their own domain/)
DOMAIN_BY_DIR = {
    "atlas/ui": "domain/ui-atlas",
    "atlas/api": "domain/api-atlas",
    "dev-notes": "domain/dev-notes",
    "help": "domain/help",
    "entities": "domain/entities",
    "docs": "domain/docs",
    "concepts": "domain/concepts",
    "display-tests": "domain/display-tests",
    "scripts": "domain/scripts",
}


def parse_fm(text: str) -> dict:
    fm = {}
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return fm
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"\'"')
    return fm


def main() -> int:
    changed = 0
    skipped = 0
    for md in sorted(WIKI.rglob("*.md")):
        rel = md.relative_to(WIKI).as_posix()
        if "/_archive/" in rel:
            continue
        text = md.read_text(encoding="utf-8")
        fm = parse_fm(text)
        if "tags" in fm:
            skipped += 1
            continue
        if not fm:
            skipped += 1
            continue

        tags = []
        # type/
        t = fm.get("type", "")
        if t in TYPE_STRIP:
            tags.append(f"type/{TYPE_STRIP[t]}")
        # domain/ — first meaningful segment:
        #   atlas/... → atlas-ui / atlas-api
        #   dev-notes/<section>/... → the section (agents, api, ...)
        #   other top dirs (entities, help, docs, ...) → the dir
        parts = rel.split("/")
        if len(parts) == 1:
            tags.append("domain/root")
        elif parts[0] == "atlas" and len(parts) > 2:
            tags.append(f"domain/atlas-{parts[1]}")
        elif parts[0] == "dev-notes" and len(parts) > 2:
            tags.append(f"domain/{parts[1]}")
        else:
            tags.append(f"domain/{parts[0]}")
        # status/ — only when a real verdict exists (no unknown noise)
        real_status = {"active", "dormant", "superseded", "orphaned", "dead", "legacy-data"}
        if "status:" in text and fm.get("status", "").lower() in real_status:
            tags.append(f"status/{fm['status'].lower()}")
        # confidence is a property, not a tag (kept in frontmatter only)

        # Insert tags: line before the closing --- of frontmatter
        lines = text.split("\n")
        # find closing ---
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        if end_idx is None:
            skipped += 1
            continue
        tag_line = "tags: [" + ", ".join(tags) + "]"
        lines.insert(end_idx, tag_line)
        md.write_text("\n".join(lines), encoding="utf-8")
        changed += 1

    print(f"Backfilled {changed} files (skipped {skipped})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
