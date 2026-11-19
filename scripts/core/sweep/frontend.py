#!/usr/bin/env python3
"""
Frontend check functions for the sweep package.

Each function is a zero-argument callable that returns (returncode, output).
"""

from sweep.shared import run_cmd, FRONTEND_DIR

import re
from pathlib import Path


def check_tsc():
    """Run TypeScript compiler check (no emit)."""
    return run_cmd(
        ["npx", "tsc", "--noEmit"],
        cwd=FRONTEND_DIR,
        label="Frontend: tsc --noEmit",
        timeout=180,
    )


def check_eslint():
    """Run ESLint on frontend source."""
    return run_cmd(
        ["npx", "eslint", "."],
        cwd=FRONTEND_DIR,
        label="Frontend: ESLint",
        timeout=180,
    )


def check_vitest():
    """Run vitest tests."""
    return run_cmd(
        ["npx", "vitest", "run", "--reporter=verbose"],
        cwd=FRONTEND_DIR,
        label="Frontend: vitest",
        timeout=180,
    )


def check_build():
    """Run full TypeScript build (tsc -b)."""
    return run_cmd(
        ["npx", "tsc", "-b"],
        cwd=FRONTEND_DIR,
        label="Frontend: tsc -b (full build check)",
        timeout=180,
    )




def check_dev_servers():
    """Probe the dev servers' health (the 2026-08-27 lesson: the vite
    died silently and the UI's live-ness went with it — the backend
    stayed healthy, so nothing looked down). The backend's health
    endpoint + the vite's root. REPORT-ONLY — the restart is the
    operator's call."""
    from urllib.request import urlopen
    from urllib.error import URLError

    findings = []
    probes = [
        ("backend", "http://127.0.0.1:8000/api/v1/health"),
        ("vite (the frontend)", "http://localhost:5173/"),
    ]
    for name, url in probes:
        try:
            with urlopen(url, timeout=4) as resp:
                findings.append((name, resp.status == 200, f"HTTP {resp.status}"))
        except URLError as e:
            findings.append((name, False, f"unreachable ({e.reason})"))
        except Exception as e:
            findings.append((name, False, f"error ({type(e).__name__})"))

    bad = [f for f in findings if not f[1]]
    if bad:
        lines = [f"  ❌ {name}: {detail}" for name, ok, detail in bad]
        output = "Dev servers down:\n" + "\n".join(lines)
        output += ("\n\nTo fix:\n  cd frontend && npx vite --host 0.0.0.0 --port 5173"
                  "   (the --host 0.0.0.0 matters — the IPv6-only default refuses the"
                  "   panel's IPv4 ws-connections, the 08-27 offline bug;"
                  "   the backend: the no-reload uvicorn launch)")
        return 1, output
    lines = [f"  ✅ {name}: {detail}" for name, ok, detail in findings]
    return 0, "Dev servers healthy:\n" + "\n".join(lines)



# ── The module-specifier gate ────────────────────────────────────────────────

#: Every place a module is named by a path. Bare package specifiers ('react', 'node:fs') are not
#: this gate's business and are skipped by the leading-character test in `_specifier_resolves`.
_SPECIFIER_PATTERNS = (
    re.compile(r"""\bfrom\s*(?P<q>['"])(?P<spec>[^'"]+)(?P=q)"""),
    re.compile(r"""\bimport\s*\(\s*(?P<q>['"])(?P<spec>[^'"]+)(?P=q)"""),
    re.compile(
        r"""\b(?:vi|jest)\.(?:mock|unmock|doMock|deepMock|requireActual|importActual)\s*\(\s*"""
        r"""(?P<q>['"])(?P<spec>[^'"]+)(?P=q)"""
    ),
)

#: What a path may point at. Vite serves css/svg/json through the same graph, so they resolve too.
_RESOLVE_SUFFIXES = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".css", ".svg")
_INDEX_FILES = ("index.ts", "index.tsx", "index.js")


def _specifier_resolves(src, importer, spec):
    """Does ``spec``, written in ``importer``, name something real?

    Only RELATIVE and ALIASED specifiers are judged: a bare specifier is a package, and which
    packages exist is npm's question, not this gate's.
    """
    if spec.startswith("@/"):
        target = src / spec[2:]
    elif spec.startswith("."):
        target = (importer.parent / spec).resolve()
    else:
        return True

    if any((Path(str(target) + suffix)).exists() for suffix in _RESOLVE_SUFFIXES):
        return True
    return any((target / index).exists() for index in _INDEX_FILES)


def module_specifier_findings(src):
    """(findings, checked) — every module specifier under ``src`` that names nothing.

    Findings are ``file:line  spec`` strings, relative to the frontend root, so a reader can open
    the line the message names.
    """
    findings = []
    checked = 0
    for path in sorted(list(src.rglob("*.ts")) + list(src.rglob("*.tsx"))):
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in _SPECIFIER_PATTERNS:
            for match in pattern.finditer(text):
                # Vite's query suffixes ('./style.css?inline', '?raw') are not part of the path.
                spec = match.group("spec").split("?", 1)[0].split("#", 1)[0]
                checked += 1
                if _specifier_resolves(src, path, spec):
                    continue
                line_no = text.count("\n", 0, match.start()) + 1
                findings.append(f"  {path.relative_to(src.parent)}:{line_no}  {spec}")
    return findings, checked


def check_module_specifiers():
    """Every module specifier in `frontend/src` must RESOLVE.

    WHY THIS EXISTS — a specifier that names nothing is never right, and it fails in the worst
    available way. When the sweep converted 534 hand-computed climbs to the `@/` alias, three test
    files (and a fourth, a one-level `vi.mock('./TraceService')`) turned out to mock a module at a
    path that did not exist: **the mock silently did not apply, the real service ran inside the
    tests, and vitest said nothing at all** — no error, no warning. That is the failure the
    path-locator item had described as a hypothetical ("the mock silently did not apply, and the
    real service ran instead"), caught live.

    The climb sweep could not see the fourth one: its rule was `(\\.\\./){2,}`, and a `./` reference is
    not a climb. This gate asks the question that covers all of them — *does it resolve?* — which is
    also the question `tsc` will not answer for a string argument and runtime answers too late.
    """
    src = FRONTEND_DIR / "src"
    if not src.is_dir():
        return 0, f"  ⚠️  no frontend source tree at {src} — nothing to check"

    findings, checked = module_specifier_findings(src)
    if not findings:
        return 0, f"  ✅ all {checked} module specifier(s) in frontend/src resolve"

    output = (
        f"Specifiers naming no module ({len(findings)} of {checked}):\n"
        + "\n".join(findings)
        + "\n\nTo fix: name it by the alias (`@/…`) or by the path that actually exists. A test"
        "\n  double that resolves nowhere does not fail — it silently applies nothing, and the real"
        "\n  module runs instead."
    )
    return 1, output


def get_all_checks():
    """Return a list of (check_fn, label) tuples for all frontend checks."""
    return [
        (check_module_specifiers, "Frontend: module specifiers resolve"),
        (check_tsc, "Frontend: tsc --noEmit"),
        (check_eslint, "Frontend: ESLint"),
        (check_vitest, "Frontend: vitest"),
        (check_build, "Frontend: tsc -b (full build)"),
        (check_dev_servers, "Dev servers' health (backend + vite)"),
    ]
