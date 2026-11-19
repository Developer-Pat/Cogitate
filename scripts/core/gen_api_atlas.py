#!/usr/bin/env python3
"""Generate API-Atlas skeleton pages from the live OpenAPI spec.

Reads /openapi.json (or a cached copy), groups paths by domain
(after /api/v1/), and writes wiki/api-atlas/routers/<domain>.md
skeleton pages with frontmatter + endpoint tables.

Tags (Obsidian testbed): flow-style single-line frontmatter list —
type/api + domain/<n> + status/<verdict> + confidence/stub.
Status filled during annotation (generator defaults to
status/unknown; annotators set active/dormant/...).

Usage:
    python3 scripts/core/gen_api_atlas.py            # live spec
    python3 scripts/core/gen_api_atlas.py --from cache.json
"""

import argparse
import json
import os
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ATLAS_DIR = REPO_ROOT / "wiki" / "api-atlas"
ROUTERS_DIR = ATLAS_DIR / "routers"

# Domains removed from the app (stale in a running spec) — skipped
SKIP_PREFIXES = ("cheat-sheets",)

# Human labels for domains (fallback: the domain slug)
DOMAIN_LABELS = {
    "agent-chat": "Agent Chat",
    "agent-lists": "Agent Lists",
    "agent-registry": "Agent Registry",
    "cognitive": "Cognitive",
    "curated-models": "Curated Models",
    "multi-agent": "Multi-Agent",
    "runtime-config": "Runtime Config",
    "workflow-lists": "Workflow Lists",
    "memory-profiles": "Memory Profiles",
    "cognitive-profiles": "Cognitive Profiles",
}


def fetch_spec(url: str = "http://localhost:8000/openapi.json") -> dict:
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


def domain_of(path: str) -> str:
    segs = path.strip("/").split("/")
    # /api/v1/<domain>/... — index 2; fall back to index 1
    if len(segs) > 2 and segs[1] == "v1":
        return segs[2]
    if len(segs) > 1:
        return segs[1]
    return "root"


def method_order(m: str) -> int:
    return ["get", "post", "put", "delete", "patch"].index(m) if m in ["get", "post", "put", "delete", "patch"] else 99


def frontmatter(domain: str, title: str) -> str:
    return f"""---
title: {title}
type: atlas-api
path: wiki/api-atlas/routers/{domain}.md
category: api-atlas
order: 1
confidence: stub
updated: 2026-08-07
tags: [type/api, domain/{domain}, status/unknown, confidence/stub]
---
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", help="read spec from a JSON file instead of live")
    args = ap.parse_args()

    spec = fetch_spec() if not args.src else json.loads(Path(args.src).read_text())
    paths = spec.get("paths", {})

    # Group paths by domain
    by_domain: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for p, methods in paths.items():
        d = domain_of(p)
        if any(p.startswith("/api/v1/" + skip) for skip in SKIP_PREFIXES):
            continue
        by_domain[d].append((p, methods))

    ROUTERS_DIR.mkdir(parents=True, exist_ok=True)
    written = 0
    for domain in sorted(by_domain):
        title = DOMAIN_LABELS.get(domain, domain.replace("-", " ").title())
        fm = frontmatter(domain, title)

        # Endpoint table
        rows = []
        for p, methods in sorted(by_domain[domain]):
            for m, op in sorted(methods.items(), key=lambda kv: method_order(kv[0])):
                if m not in ("get", "post", "put", "delete", "patch"):
                    continue
                summary = op.get("summary") or op.get("operationId", "").replace("_", " ")
                rows.append(f"| `{m.upper()}` | `{p}` | {summary} |")

        body = f"""# {title} — API

> Routers: `backend/app/api/v1/{domain}/` (or `{domain}_router.py`).
> Generated skeleton — annotate: purpose, auth, status tag.

## Endpoints

| Method | Path | Summary |
|--------|------|---------|
{chr(10).join(rows)}

## Notes

> /todo: annotate — purpose per endpoint, auth requirements,
> request/response specifics, status verdict (tags: status/...).
"""
        out = ROUTERS_DIR / f"{domain}.md"
        out.write_text(fm + "\n" + body, encoding="utf-8")
        written += 1

    print(f"Generated {written} router pages in {ROUTERS_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
