#!/usr/bin/env python3
"""Measure the dependency backlog the way an auditor would, not the way a badge does.

`npm audit` answers for the frontend. This answers for the Python side by asking OSV — the same advisory
database Dependabot ingests — about the EXACT versions the lockfiles resolve to, and it says which are DIRECT
dependencies (ours to bump) and which are transitive (the parent's decision). Stdlib only, no token.

    python3 scripts/diagnostics/audit_dependencies.py                    # the workspace lockfile, severity summary
    python3 scripts/diagnostics/audit_dependencies.py --json /tmp/audit.json
    python3 scripts/diagnostics/audit_dependencies.py --requirements /tmp/req.txt

Why not `pip-audit -r`: it builds a throwaway environment to resolve the file, and this project pins Python 3.14
plus duplicate transitive pins, so it dies before it reports. OSV needs neither, and its `querybatch` answers ids
only — the details (severity, fixed version) come from one cached GET per advisory.

The number this prints is ALERTS PER PACKAGE, which is what the work is; GitHub's badge counts alerts per manifest
and will read higher.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

OSV_BATCH = "https://api.osv.dev/v1/querybatch"
OSV_VULN = "https://api.osv.dev/v1/vulns/"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE = Path("/tmp/osv-vuln-cache.json")
PIN = re.compile(r"^([A-Za-z0-9_.\-]+)==([^\s;]+)")
VIA = re.compile(r"^#\s*via\s+(.*)$")
RANK = {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2, "MEDIUM": 2, "LOW": 3, "": 4}


def _export(project_dir: Path, dest: Path) -> Path | None:
    if not (project_dir / "pyproject.toml").exists():
        return None
    proc = subprocess.run(
        ["uv", "export", "--format", "requirements-txt", "--no-hashes", "-o", str(dest)],
        cwd=project_dir, capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(f"  ! uv export failed in {project_dir}: {proc.stderr.strip()[:200]}", file=sys.stderr)
        return None
    return dest


def _pins(path: Path) -> dict[str, dict]:
    """{package: {"version": ..., "via": [parents]}} — `via` is the export's own provenance comment."""
    out: dict[str, dict] = {}
    current: str | None = None
    in_via = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        m = PIN.match(line.strip())
        if m:
            pkg = m.group(1).lower()
            current = pkg
            out[pkg] = {"version": m.group(2), "via": []}
            in_via = False
            continue
        v = VIA.match(line.strip())
        if v and current is not None:
            in_via = True
            rest = v.group(1).strip()
            if rest:
                out[current]["via"] = [p.strip() for p in rest.split(",") if p.strip()]
            continue
        if in_via and current is not None and line.startswith("    #   "):
            out[current]["via"].append(line.strip("# ").strip())
    return out


def _batch(pins: dict[str, dict]) -> dict[str, list[str]]:
    names = sorted(pins)
    queries = [{"package": {"name": n, "ecosystem": "PyPI"}, "version": pins[n]["version"]} for n in names]
    req = urllib.request.Request(
        OSV_BATCH, data=json.dumps({"queries": queries}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "cogitate-audit"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        results = json.loads(resp.read()).get("results", [])
    return {n: [v.get("id", "?") for v in (r.get("vulns") or [])] for n, r in zip(names, results) if r.get("vulns")}


def _details(ids: list[str]) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}
    for i in ids:
        if i in cache:
            continue
        try:
            req = urllib.request.Request(OSV_VULN + i, headers={"User-Agent": "cogitate-audit"})
            with urllib.request.urlopen(req, timeout=60) as r:
                v = json.loads(r.read())
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  ! {i}: {exc}", file=sys.stderr)
            continue
        fixes: set[str] = set()
        for affected in v.get("affected", []):
            for rng in affected.get("ranges", []):
                for event in rng.get("events", []):
                    if "fixed" in event:
                        fixes.add(event["fixed"])
        cache[i] = {
            "severity": ((v.get("database_specific") or {}).get("severity") or "").upper(),
            "summary": (v.get("summary") or "")[:140],
            "fixed_in": sorted(fixes),
            "aliases": [a for a in v.get("aliases", []) if a.startswith("CVE-")],
        }
    CACHE.write_text(json.dumps(cache), encoding="utf-8")
    return cache


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--requirements", help="audit this requirements file instead of exporting the lockfiles")
    ap.add_argument("--json", help="also write the full result here")
    args = ap.parse_args()

    targets: list[tuple[str, Path]] = []
    if args.requirements:
        targets.append((Path(args.requirements).name, Path(args.requirements)))
    else:
        # ONE export, from the workspace root. The root pyproject declares a uv workspace whose
        # member is `backend`, and a workspace has exactly one lockfile — exporting per member
        # just repeats the same resolution under a different label.
        exported = _export(PROJECT_ROOT, Path("/tmp/cogitate-req-workspace.txt"))
        if exported is not None:
            targets.append(("workspace", exported))

    report: dict[str, dict] = {}
    for label, reqs in targets:
        pins = _pins(reqs)
        hits = _batch(pins)
        ids = sorted({i for v in hits.values() for i in v})
        details = _details(ids)

        rows = []
        for pkg, vuln_ids in hits.items():
            sev = [details.get(i, {}).get("severity", "") for i in vuln_ids]
            worst = min(sev, key=lambda s: RANK.get(s, 4)) if sev else ""
            fixes = sorted({f for i in vuln_ids for f in details.get(i, {}).get("fixed_in", [])})
            via = pins[pkg]["via"]
            # `uv export` names the project itself for a direct dependency ("via cogitate"/"via backend").
            direct = any(p.lower() in {"cogitate", "backend"} for p in via)
            rows.append({
                "package": pkg, "version": pins[pkg]["version"], "alerts": len(vuln_ids),
                "worst": worst or "UNKNOWN", "direct": direct, "via": via[:4],
                "fixed_in": fixes, "advisories": sorted(vuln_ids),
                "top": details.get(vuln_ids[0], {}).get("summary", "") if vuln_ids else "",
            })
        rows.sort(key=lambda r: (RANK.get(r["worst"], 4), not r["direct"], -r["alerts"], r["package"]))

        counts: dict[str, int] = {}
        for r in rows:
            counts[r["worst"]] = counts.get(r["worst"], 0) + r["alerts"]
        report[label] = {"packages": len(pins), "flagged_packages": len(rows), "alerts": sum(r["alerts"] for r in rows),
                         "by_severity": counts, "rows": rows}

        print(f"== {label}: {len(pins)} pinned · {len(rows)} flagged · {report[label]['alerts']} alerts "
              f"({', '.join(f'{k} {v}' for k, v in sorted(counts.items(), key=lambda kv: RANK.get(kv[0], 4)))})")
        for r in rows:
            fix = ", ".join(r["fixed_in"][:2]) or "no fix published"
            kind = "DIRECT" if r["direct"] else f"via {r['via'][0] if r['via'] else '?'}"
            print(f"  {r['worst']:<9} {r['package']:<30} {r['version']:<12} {r['alerts']:>2} alert(s) "
                  f"{kind:<22} fix→ {fix}")

    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
