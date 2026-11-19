#!/usr/bin/env python3
"""
Backend check functions for the sweep package.

Each function is a zero-argument callable that returns (returncode, output).
"""

import os
from pathlib import Path

import re
import sys
from sweep.shared import run_cmd, BACKEND_DIR, REPO_ROOT

#: THE RAW-OPEN RULE — a `sqlite3.connect(...)` argument that names a locator
#: CLASS ATTRIBUTE (`Paths.shared_db`, `_Paths.data_dir`) or the literals
#: `cogitate.db` / `_shared`.
#:
#: Module level so a test can exercise it directly. A gate whose rules are never
#: exercised keeps reporting clean after the shape it was written for changes —
#: which is precisely what happened here: the rule looked for the literals
#: `cogitate.db` and `_shared`, so it reported clean over
#: `sqlite3.connect(str(_Paths.shared_db))` — the expression that wrote 244 usage
#: rows into the operator's LIVE database from inside the test suite.
#:
#: WHY A CLASS ATTRIBUTE IS THE DEFECT. Every field on `Paths` is a dataclass
#: FIELD DEFAULT: a fixed path under BASE_DIR that ignores settings (DATABASE_URL
#: in the suite, the fork's Postgres). So it is not merely a hardcoded path — it
#: works perfectly on the operator's machine and silently targets their live
#: installation. `(?!from_settings)` is what keeps the sanctioned resolved form
#: (`Paths.from_settings(get_settings()).shared_db`) and the provisioning helper
#: (`_shared_db_path()`) clear.
#:
#: WHAT IT CANNOT SEE, NAMED RATHER THAN LEFT IMPLIED: it reads the argument of a
#: `sqlite3.connect(...)` call, so a locator default handed to something else that
#: opens the database — `ConsistencyAudit(Paths.shared_db)` — is not matched. The
#: wide form (flag EVERY `Paths.<field>` read) is a standing option and was
#: measured before it was declined: 76 sites in backend/app across 22 fields, and
#: the project's ruling on widening (see check_path_arithmetic) is to widen only
#: where a site is found doing something that escapes the installation, because a
#: marker on everything is a marker on nothing.
SHARED_DB_RAW_OPEN = re.compile(
    r"\b(?:_sqlite3|_sqlite|sqlite3)\.connect\("
    r"[^)]*(?:"
    r"(?:Paths|_Paths|CorePaths)\.(?!from_settings)\w+"
    r"|cogitate\.db|_shared\b"
    r")"
)


def check_mypy():
    """Run mypy type checking on backend."""
    return run_cmd(
        ["uv", "run", "mypy", "app/"],
        cwd=BACKEND_DIR,
        label="Backend: mypy",
        timeout=180,
    )


# THE TEST GROUP the sweep runs. A phased sweep, not the whole suite: the
# runner partitions by directory (unit/workflows/api/components/integration/e2e)
# precisely so a full run is never required. Override with
# `sweep.py backend --test-group workflows`.
TEST_GROUP = "unit"


def check_pytest():
    """Run the test RUNNER's group — not pytest directly.

    WHAT THIS REPLACES, and why it matters: the sweep used to call pytest raw
    with `-x` (stop at the FIRST failure), no `--output`, and a 540s timeout. So
    a run that takes 31 minutes could never finish, wrote no report, halted at
    one failure, and silently ignored the runner's QUARANTINE list. The user's
    summary: "the tests were designed to be run separately for precisely this
    reason — to allow partial sweeps rather than run the entire sweep all the
    time." `scripts/testing/run_tests.py` already did that; nothing called it.

    The runner writes a RUN FOLDER (one per run, in the locator's test-runs dir)
    holding report.md — header: group, parallel, file count, backend health;
    footer: ELAPSED and EXIT — plus report.xml and events.jsonl. It emits `-rf`
    so the report carries a greppable FAILED list. The run is left on disk as
    the evidence, and the runner prints its `RUN_DIR:` so a caller does not have
    to guess the run's name.

    No `--output`: a run has ONE name wherever it is started from. The sweep
    used to write the same run under a sweep-specific filename, which put a
    runner's report in the sweep's naming scheme.

    The ORIGIN is stamped into the run lock, so a page (or a person) looking at
    a run in progress can say who started it instead of guessing.
    """
    os.environ["COGITATE_RUN_ORIGIN"] = "sweep"
    return run_cmd(
        [
            "python3", "scripts/testing/run_tests.py",
            "--group", TEST_GROUP,
            "--no-live",          # the sweep captures output itself
            "--timeout", "900",   # the runner's own kill, so it writes a PARTIAL report
        ],
        cwd=REPO_ROOT,
        label=f"Backend: pytest ({TEST_GROUP} group, via run_tests.py)",
        timeout=960,
    )


def check_pytest_all():
    """Run all pytest tests (including slow/integration)."""
    return run_cmd(
        ["uv", "run", "pytest", "--tb=short", "-q"],
        cwd=BACKEND_DIR,
        label="Backend: pytest (all tests)",
        timeout=600,
    )


def check_imports():
    """Check for import errors by trying to import the app package."""
    return run_cmd(
        ["uv", "run", "python3", "-c", "from app.main import app; print('Import OK')"],
        cwd=BACKEND_DIR,
        label="Backend: import check",
        timeout=60,
    )


def check_deprecation_warnings():
    """Run Python with deprecation warnings enabled on a basic import."""
    return run_cmd(
        [
            "uv", "run", "python3", "-W", "error::DeprecationWarning",
            "-c", "import app.main; print('Deprecation check complete')",
        ],
        cwd=BACKEND_DIR,
        label="Backend: deprecation warnings",
        timeout=60,
    )





def check_router_decorators():
    """Detect the refactoring-damage class: a @router.X decorator
    with no handler function (the agent-delete bug — a refactor
    consumed a route's decorator, silently breaking the endpoint).

    Multi-line aware: a decorator whose parens span lines is
    collected whole; the next non-empty line after the decorator
    block must be a function definition. Stacked decorators (the
    dual-route pattern) are handled by the same rule.
    """
    import re

    router_dirs = ["backend/app/api", "backend/app/domain", "backend/app/workflows"]
    files = []
    for d in router_dirs:
        root_d = REPO_ROOT / d
        if not root_d.exists():
            continue
        for root, dirs, fs in os.walk(root_d):
            if "__pycache__" in root:
                continue
            for f in fs:
                if f.endswith("router.py") or f.endswith("_router.py"):
                    files.append(Path(root) / f)

    dangling = []
    for fp in sorted(files):
        lines = fp.read_text(encoding="utf-8", errors="replace").split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            if re.match(r"^@router\.", line.strip()):
                # collect the full decorator (multi-line parens)
                j = i
                depth = line.count("(") - line.count(")")
                while depth > 0 and j + 1 < len(lines):
                    j += 1
                    depth += lines[j].count("(") - lines[j].count(")")
                # next non-empty line after the decorator block:
                # a def (handler), OR another decorator (a stacked
                # route — the dual-route pattern, both valid). A
                # dangling decorator is one followed by neither.
                k = j + 1
                while k < len(lines) and lines[k].strip() in ("", "#"):
                    k += 1
                if k < len(lines) and re.match(r"^@router\.", lines[k].strip()):
                    pass  # stacked decorator — the handler follows it
                elif k >= len(lines) or not re.match(r"^(async )?def ", lines[k].strip()):
                    dangling.append((str(fp.relative_to(REPO_ROOT)), i + 1, line.strip()[:70]))
                i = j + 1
            else:
                i += 1

    if dangling:
        output = "Dangling router decorators (a route lost its handler — the agent-delete bug class):\n"
        for fp, ln, txt in dangling:
            output += f"  {fp}:{ln} {txt}\n"
        output += "\nFix: give each decorator its handler function (or remove the decorator)."
        return 1, output
    else:
        return 0, f"✅ No dangling router decorators ({len(files)} router files checked)"


def check_path_arithmetic():
    """Detect hand-computed path arithmetic (the phantom-DB class).

    The Paths locator (core/config.py) is the ONE resolver for the
    canonical app paths. Modules that re-derive paths from
    __file__ parent-crawls, cwd, or dirname() joins are the
    fragility class — each is a future off-by-one (the workflow
    routers' phantom cogitate.db, Aug 9) or a fork-blocker (the
    industrial version flips the DB via settings, not 15 sites).

    EVERY flag below is a FAILURE (exit 1) — the pre-commit hook and the sweep
    both block on it. An earlier version of this docstring called the flags
    "informational — the check fails on the SHARED-DB sites"; that described a
    mode this function never had.

    The shapes it knows:
    - parent-crawls: Path(__file__).parents[N] / .parent×N (TWO or more hops)
    - dirname(__file__) joins, and the '..' up-crawl
    - cwd-dependent paths (Path.cwd() / os.getcwd())
    - BASE_DIR arithmetic, expanduser(), './x.db'
    - raw sqlite3.connect to the shared db path (app scope; per-agent
      memory/vector DB paths are legitimate and not the shared one)

    WHAT IT CANNOT SEE, NAMED RATHER THAN LEFT IMPLIED (2026-09-26): a
    SINGLE-hop `Path(__file__).parent` join — BOTH .parent patterns require 2+
    hops. `page_map.py`'s `parent / "page_map.json"` is what surfaced it, and
    that shape is a MODULE-ADJACENT read: a different case from a root-crawl,
    and all six in the tree are that shape. Its own success line now says so
    too, so "clean" is never read as "no path arithmetic anywhere".

    WIDENING IS A STANDING OPTION, and this is the reason it was not taken
    (the user's ruling, 2026-09-26): widening forces a `# path-ok:` marker on
    every legitimate module-adjacent read, and a marker on everything is a
    marker on nothing. Widen when one is found doing something root-relative.
    """
    import re

    # THE SCOPE (widened 2026-09-12): backend/app was the SHIPPED surface only,
    # by explicit decision — and that decision is why eleven test files that
    # WROTE INTO PRODUCTION were invisible here. A test that reaches the live
    # database by hand is not a lesser defect than an app module that does: it
    # corrupts real data. So tests are scanned too.
    #
    # tests DO legitimately use tmp_path and copy the real DB to seed an isolated
    # one; those uses are marked inline with `# path-ok:` and skipped below.
    # scripts/core/* keep their stable parents[2]-from-core conventions and stay
    # out of scope as dev tooling — EXCEPT the ones that touch the live DB.
    files = []
    for d in ["backend/app", "backend/tests"]:
        root_d = REPO_ROOT / d
        if not root_d.exists():
            continue
        for root, dirs, fs in os.walk(root_d):
            if "__pycache__" in root or "node_modules" in root:
                continue
            for f in fs:
                if f.endswith(".py"):
                    files.append(Path(root) / f)

    patterns = [
        (r"Path\(__file__\)\.(?:resolve\(\)\.)?parents\[\d+\]", "parent-crawl"),
        # THE COVERAGE GAP (2026-09-12, live): this check ran red for weeks on ONE
        # site while ELEVEN sites in backend/tests/ and three in the macros router
        # were invisible to it — because the shapes they used had no pattern here.
        # A path scanner that knows only some of the shapes reports "clean" over a
        # real leak, which is the same failure as the .resolve() hole noted below.
        (r"BASE_DIR\s*/\s*[\"']", "BASE_DIR-arithmetic"),
        (r"os\.path\.expanduser\(", "home-dir-literal"),
                # NOT quote-anchored: `sqlite:///./data/x.db` has no quote before the
        # `./`, so the anchored form missed the URL-shaped case — which is
        # precisely the shape of the documents-DB fallback fixed 2026-09-12.
        (r"\./[\w./-]*\.db", "cwd-relative-db"),
        # THE RESOLVE-VARIANT FIX (2026-08-25, live): the original
        # pattern required the DIRECT 'Path(__file__).parent' chain —
        # the '.resolve()' prefix (9 sites!) BROKE the match and the
        # sweep reported 'clean' against a real crawl (the doc_index
        # / doc_reader / consult / file_info / macro_manager /
        # skill_reader chains). The optional resolve() closes the hole.
        (r"Path\(__file__\)\.(?:resolve\(\)\.)?parent(?:\.parent)+", "parent-crawl"),
        (r"Path\.cwd\(\)", "cwd-dependent"),
        # the '..' up-crawl — os.path.join(dirname(__file__), '..', '..', ...)
        # (the user's catch, 2026-08-17: AGENTS_DIR used this; 10 sites
        # still do — each crawls to a canonical path the locator owns)
        (r'os\.path\.join\([^)]*dirname\(__file__\)[^)]*"\.\.', "dirname-up-crawl"),
    ]
    # the SHARED-DB raw opens — the rule is module level (`SHARED_DB_RAW_OPEN`)
    # so the tests can exercise it; see its definition for why a locator class
    # attribute counts as a hardcoded path.
    shared_db_pat = SHARED_DB_RAW_OPEN

    flags = []
    for fp in sorted(files):
        try:
            content = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "core/config.py" in str(fp):
            continue  # the locator's home — its own arithmetic is canonical
        # an explicit, greppable exemption — a legitimate use says so in place,
        # so the next reader can tell a deliberate path from an accident.
        # Strip COMMENTS before matching. A gate that trips on prose is a gate
        # people stop reading: this check flagged the very comment explaining the
        # macros-router fix. A path written in a comment is documentation.
        #
        # NOTE for anyone adding `# path-ok:` by hand: the marker must sit on the
        # SAME line as the flagged code, and a comment cannot follow a line
        # continuation. A path written as `X = long / \` + newline + `"y"` will
        # raise SyntaxError once marked. Wrap it in parens first:
        #     X = (
        #         Path(__file__).parents[2]  # path-ok: <why>
        #         / "y"
        #     )
        #
        # `# path-ok:` exempts the LINE it sits on, and only that line. An
        # earlier version skipped the whole file when the marker appeared
        # anywhere in it - so one marker would have hidden every other finding in
        # the file, which is a bigger hole than the one it was closing.
        content = "\n".join(
            "" if ("# path-ok:" in ln or ln.lstrip().startswith("#"))
            else ln.split("  #")[0]
            for ln in content.splitlines()
        )
        for pat, label in patterns:
            for m in re.finditer(pat, content):
                ln = content[:m.start()].count("\n") + 1
                flags.append((str(fp.relative_to(REPO_ROOT)), ln, label, m.group(0)[:50]))
        if "test" not in str(fp):
            for m in shared_db_pat.finditer(content):
                ln = content[:m.start()].count("\n") + 1
                flags.append((str(fp.relative_to(REPO_ROOT)), ln, "shared-db-raw-open", m.group(0)[:50]))

    if flags:
        output = "Hand-computed path arithmetic (the phantom-DB class) — use the Paths locator:\n"
        for fp, ln, label, snip in flags[:25]:
            output += f"  {fp}:{ln} [{label}] {snip}\n"
        output += "\nFix: import Paths from app.core.config; never re-derive paths from __file__/cwd."
        return 1, output
    else:
        return 0, (
            f"✅ No hand-computed path arithmetic in the classes this check knows "
            f"({len(files)} files checked): 2+ hop parent-crawls, dirname up-crawls, "
            f"cwd joins, BASE_DIR/expanduser/./x.db, shared-DB opens.\n"
            f"   NOT COVERED by ruling, 2026-09-26: a SINGLE-hop "
            f"Path(__file__).parent join (module-adjacent reads — six in the tree, all "
            f"that shape). See check_path_arithmetic's docstring before trusting this line.\n"
            f"   NOT COVERED by the raw-open rule: a locator CLASS ATTRIBUTE handed to "
            f"something else that opens the database — `ConsistencyAudit(Paths.shared_db)`. "
            f"The rule reads the argument of a sqlite3.connect(...) call, and a path passed "
            f"to a constructor is not that shape. "
            f"(Widening to EVERY `Paths.<field>` read is a standing option and was measured "
            f"2026-10-06: 76 sites in backend/app across 22 fields — see SHARED_DB_RAW_OPEN.)"
        )


def check_absolute_paths():
    """No absolute paths in the project — they leak private information.

    A DIFFERENT RULE from check_path_arithmetic(). That one asks "does this path
    follow the resolver?"; this one asks "does this file name a specific machine?"
    A literal `/home/<user>/...` satisfies the resolver and still ships a
    username and a directory layout to everyone who reads the repository, the
    tarball, or the published package.

    The damage is not only disclosure: a hardcoded absolute path is also a path
    that works on exactly one machine. The tag-survey nodes carried six, one of
    them a `startswith("<hardcoded absolute root>")` GUARD — so the code could
    only ever run in the directory it was written in.

    Scans every TRACKED file, not just Python: the rule is about any artifact
    that leaves this machine (docs, examples, skills, frontend tests).
    Exempt a line with `# no-abs-ok:` plus the reason.
    """
    import re
    import subprocess as _sp

    # A REAL user is the leak. Generic placeholders are not — a fixture that
    # normalizes "/home/user/x" names nobody.
    _PLACEHOLDER = {"user", "you", "username", "example", "youruser", "someuser"}
    pat = re.compile(r"(?:/home|/media|/Users|/mnt)/([A-Za-z][\w.-]*)")

    def _is_leak(line: str) -> str | None:
        for m in pat.finditer(line):
            if m.group(1).lower() not in _PLACEHOLDER:
                return m.group(0)
        return None
    # The rule itself, and pages that must NAME the shape to explain it.
    allowlist = {
        "scripts/core/sweep/backend.py",       # this check
        "wiki/dev-notes/known-issues.md",      # documents the class
        "wiki/dev-notes/testing/test-isolation.md",
    }
    try:
        files = _sp.run(
            ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True
        ).stdout.splitlines()
    except OSError:
        return 0, "✅ absolute-path check skipped (git unavailable)"

    flags = []
    for rel in files:
        if rel in allowlist or rel.startswith("_archive/"):
            continue
        fp = REPO_ROOT / rel
        try:
            content = fp.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            continue  # binary or unreadable — not a text artifact
        for n, ln in enumerate(content.splitlines(), 1):
            if "no-abs-ok:" in ln:
                continue
            hit = _is_leak(ln)
            if hit:
                flags.append((rel, n, hit))

    if flags:
        out = "Absolute paths — they name a specific machine and leak it:\n"
        for rel, n, hit in flags[:30]:
            out += f"  {rel}:{n}  {hit}\n"
        out += ("\nFix: derive the path from Paths (app code) or make it relative.\n"
                "A hardcoded absolute path also only works on ONE machine.")
        return 1, out
    return 0, f"✅ No absolute paths ({len(files)} tracked files checked)"


def check_stale_cogitate_dbs():
    """
    Check for stale/empty cogitate.db files that should not exist.

    The canonical main application database lives at ``REPO_ROOT / "cogitate.db"``.
    """

    stale_patterns = [
        ("backend/cogitate.db", "Stale partial copy, created by scripts using wrong relative path from backend/ directory"),
        ("backend/cogitate-backup-pre-apikey.db", "Stale 0-byte backup artifact, leftover from API key migration"),
    ]

    issues = []
    for rel_path, description in stale_patterns:
        full_path = REPO_ROOT / rel_path
        if full_path.exists():
            size = full_path.stat().st_size
            issues.append(f"  ❌ {rel_path} ({size} bytes) — {description}")

    if issues:
        output = "Stale cogitate.db files detected:\n" + "\n".join(issues)
        output += f"\n\nTo fix: rm {' '.join(str(REPO_ROOT / p[0]) for p in stale_patterns if (REPO_ROOT / p[0]).exists())}"
        return 1, output
    else:
        return 0, "✅ No stale cogitate.db files found"


def check_ghost_databases():
    """
    Scan for any ``.db`` files under the repo root that are zero or near-zero size
    (< 1 KB) and are NOT one of the known canonical databases.

    A "ghost database" is a stale SQLite file that should not exist — typically
    created by scripts using wrong relative paths, leftover from DB consolidation,
    or accidental copies.  Canonical databases are excluded from the scan.
    """
    # Known canonical databases (absolute paths) — these are allowed to exist
    canonical_dbs = {
        REPO_ROOT / "cogitate.db",
        REPO_ROOT / "checkpoints.db",
        REPO_ROOT / "data" / "cogitate_docs_en.db",
        REPO_ROOT / "backend" / "checkpoints.db",
    }

    # Directories to skip entirely (backups, caches, node_modules, .mypy_cache)
    skip_prefixes = (
        REPO_ROOT / "backups",
        REPO_ROOT / "trash",
        REPO_ROOT / ".mypy_cache",
        REPO_ROOT / "backend" / ".mypy_cache",
        REPO_ROOT / "node_modules",
        REPO_ROOT / "frontend" / "node_modules",
    )

    ghost_size_threshold = 1024  # 1 KB — anything smaller than this is a ghost

    ghosts: list[tuple[Path, int]] = []
    for db_path in REPO_ROOT.rglob("*.db"):
        # Skip directories we don't want to scan
        if any(db_path.is_relative_to(skip) for skip in skip_prefixes):
            continue
        # Skip canonical databases
        if db_path in canonical_dbs:
            continue
        # Skip if it's inside a canonical db's directory (e.g. -wal/-shm files)
        if db_path.stat().st_size >= ghost_size_threshold:
            continue

        ghosts.append((db_path, db_path.stat().st_size))

    if ghosts:
        lines = [f"  ❌ {p.relative_to(REPO_ROOT)} ({size} bytes)" for p, size in sorted(ghosts)]
        output = "Ghost databases detected (zero or near-zero size):\n" + "\n".join(lines)
        output += "\n\nTo fix:"
        for p, _ in sorted(ghosts):
            output += f"\n  rm {p}"
        return 1, output
    else:
        return 0, "✅ No ghost databases found"


def check_atlas_validation():
    """Run the UI Atlas validation gate (wiki/atlas integrity)."""
    script = REPO_ROOT / "scripts" / "core" / "check_atlas_validation.py"
    return run_cmd([sys.executable, str(script)], cwd=REPO_ROOT, label="Atlas validation")


def check_test_catalog():
    """Run the test-catalog checker — the descriptions the testing page renders.

    WHAT IT GUARDS, and why it belongs in a sweep: the user-testing page
    DERIVES each row's description from its test module's docstring FIRST
    LINE, so that line is load-bearing UI copy. Before the 2026-09-14 pass,
    three of every five rows opened with a date. The checker catches the
    classes that made them unreadable: project history (a date, a phase, a
    session number, an incident, a codename), two sentences on one rendered
    line, a missing terminator, an over-long line, no docstring at all.

    WHAT IT DOES NOT CHECK — stated so a green is not over-read: it does NOT
    check that a description is TRUE of the tests in its module. A 20-module
    sample found none false; that is a sample, not a guarantee.

    REPORT-ONLY, and ENDPOINT-FREE: it builds the catalog in-process
    (app.domain.testing.catalog.build_catalog), so it needs no running server.
    DEFAULT mode only — `--strict` adds the BOILERPLATE class, which is
    ADVISORY (a thin description is still true) and must never gate a sweep.
    """
    script = REPO_ROOT / "scripts" / "testing" / "check_test_catalog.py"
    return run_cmd(
        [sys.executable, str(script)],
        cwd=REPO_ROOT,
        label="Test catalog check (the rendered descriptions)",
    )


def check_agent_health():
    """Run the agent provider health scan (broken provider/model configs)."""
    script = REPO_ROOT / "scripts" / "core" / "check_agent_health.py"
    return run_cmd([sys.executable, str(script)], cwd=REPO_ROOT, label="Agent health scan")




def _leftover_bytes(path: str) -> int:
    """The size of a leftover: a file's own, or a whole root's tree."""
    if not os.path.isdir(path):
        return os.path.getsize(path)
    total = 0
    for dirpath, _dirs, names in os.walk(path):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(dirpath, name))
            except OSError:
                continue
    return total


def check_stale_tmp_databases():
    """Scan /tmp for the tests' accumulated leftovers — BOTH families:
    the session engines (`/tmp/tmp*.db`) and the temporary INSTALLATION
    roots (`/tmp/cogitate-test-*`).

    The engines: the 2026-08-27 measurement found 90 leftover tmp*.db
    files — the timeout-killed runs bypass the conftest's teardown and
    the xdist workers each create their own.

    The roots: each is a whole installation — the wiki copy, the skills,
    and (if the run reached the database) a `cogitate.db` and its WAL.
    This is the only surface that sees the KILLED case: conftest removes
    the root at interpreter exit and REPORTS a removal that fails, but
    `atexit` cannot fire on a timeout/SIGKILL. Measured 2026-10-06:
    57 roots, 248 MB — most of them from processes that never called the
    cleanup at all (fixed; see wiki/dev-notes/testing/test-isolation.md).

    SEVERITY IS SPLIT, deliberately. Stale ENGINE files FAIL the sweep —
    the existing contract, unchanged. Stale ROOTS are REPORTED, not
    failed: their commonest cause is a run the operator CANCELLED, where
    the exit cleanup legitimately cannot run, and a gate that goes red
    after every cancel is one nobody reads. Their report is the visible
    event; the removal stays the operator's call.

    Age-based: stale = older than 1h (an ACTIVE run's are minutes old).
    REPORT-ONLY — never auto-deletes (the destructive doctrine)."""
    import glob, time

    def _stale(pattern: str) -> list[tuple[str, int, float]]:
        found: list[tuple[str, int, float]] = []
        for p in glob.glob(pattern):
            try:
                age = time.time() - os.path.getmtime(p)
                if age > 3600:
                    found.append((p, _leftover_bytes(p), age))
            except OSError:
                continue
        return sorted(found, key=lambda x: -x[2])

    def _listed(items: list[tuple[str, int, float]]) -> str:
        lines = [
            f"  ❌ {p} ({s / 1048576:.1f} MB, {a / 3600:.1f}h old)"
            if s > 1048576
            else f"  ❌ {p} ({s} bytes, {a / 3600:.1f}h old)"
            for p, s, a in items[:20]
        ]
        if len(items) > 20:
            lines.append(f"  … and {len(items) - 20} more")
        return "\n".join(lines)

    stale_dbs = _stale("/tmp/tmp*.db")
    stale_roots = _stale("/tmp/cogitate-test-*")
    if not stale_dbs and not stale_roots:
        return 0, "✅ No stale test leftovers in /tmp (engines and installation roots)"

    blocks: list[str] = []
    if stale_dbs:
        blocks.append(
            f"Stale test temp-dbs in /tmp ({len(stale_dbs)} files, "
            f"{sum(s for _, s, _ in stale_dbs) / 1048576:.1f} MB — the tests' session "
            f"engines):\n{_listed(stale_dbs)}"
        )
    if stale_roots:
        blocks.append(
            f"Stale test INSTALLATION roots in /tmp ({len(stale_roots)} roots, "
            f"{sum(s for _, s, _ in stale_roots) / 1048576:.1f} MB — a whole temp "
            f"installation each; ADVISORY, this does not fail the sweep):\n"
            f"{_listed(stale_roots)}\n"
            "  A root over an hour old means its run was KILLED, so conftest's exit\n"
            "  cleanup never ran — or its removal failed, which the run's own report names."
        )

    output = "\n\n".join(blocks) + (
        "\n\nTo fix (only the stale ones — an ACTIVE run's are minutes old):\n"
        "  rm -f /tmp/tmp*.db; rm -rf /tmp/cogitate-test-*"
    )
    return (1 if stale_dbs else 0), output


def check_zombie_processes():
    """Scan for stray test-family processes (the zombie class — the
    leaked pytest/uv children holding db locks, e.g. the 08-26 PID
    531696 that held 4 fds on cogitate.db and blocked every run).
    A process is a zombie if it's test-family AND reparented (ppid 1)
    — a live run's chain terminates at the runner/sweep, never at 1.
    REPORT-ONLY — the kill is the operator's call.
    NOTE (2026-08-27): 'hermes acp' joined the family — the 08-27
    zombie-agent: the old Exa connection's agent survived the
    full-restart (the kill-patterns missed it) and contended with
    the live agent (the talk-to-Exa failures). The LIVE agent is
    the uvicorn's child (never ppid 1); the strays reparent — the
    heuristic catches exactly the zombies."""
    import subprocess

    out = subprocess.run(
        ["ps", "-eo", "pid,ppid,cmd"], capture_output=True, text=True, timeout=15
    ).stdout

    test_family = ("pytest", "run_tests", "runaway_acp", "fake_perm", "fake_acp", "hermes acp")
    zombies = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, ppid, cmd = parts
        if any(t in cmd for t in test_family) and ppid == "1":
            zombies.append((pid, ppid, cmd[:110]))

    if zombies:
        lines = [
            f"  ❌ PID {pid} (ppid {ppid} — REPARENTED, likely leaked): {cmd}"
            for pid, ppid, cmd in zombies
        ]
        output = "Zombie test processes (reparented — the leak class):\n" + "\n".join(lines)
        output += "\n\nTo fix:\n  kill -9 <pid>"
        return 1, output
    return 0, "✅ No zombie test processes"


def check_orphaned_backends():
    """Scan for LEFTOVER backend/reloader processes from restart churn.

    The class: `fuser -k` kills the PORT OWNER, but the reloader's children can
    linger. They then hold the database, fight the new instance for the port, and
    produce the "talk-to-Exa failures" / blocked-run symptoms.

    WHY NOT ppid == 1 (the test-family heuristic): a LEGITIMATELY started server
    also reparents to 1 the moment `./cogitate.sh` exits. Measured live: the
    healthy uvicorn pair both carry ppid 1. The test-family check can use ppid
    because a live test run's chain terminates at the runner; a server's does not.

    THE SIGNAL THAT DOES WORK: PORT OWNERSHIP. A live server owns the port it was
    started for -- with --reload that is TWO pids (the reloader and the spawned
    worker). Any backend-family process NOT in the owner set is a leftover.

    REPORT-ONLY. The kill is the operator's call.
    """
    import subprocess

    # BOTH halves of the app, because a "backend-only" scan misses half the leak.
    # The frontend is separately supervised (vite-supervisor.sh -> npm exec vite
    # -> sh -c vite -> node vite -> esbuild) and vite zombies are a real class --
    # the user has hit them ("kill all application processes ... especially vite").
    ports = {
        os.environ.get("COGITATE_BACKEND_PORT", "8000"): "backend",
        os.environ.get("COGITATE_FRONTEND_PORT", "5173"): "frontend",
    }

    # Who owns each port right now? Every pid listed there is legitimate.
    owners: set[str] = set()
    try:
        ss = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True, timeout=15).stdout
    except Exception:
        return 0, "⚠️  ss unavailable — the orphaned-backend scan was skipped"
    for line in ss.splitlines():
        if not any(f":{p} " in line for p in ports):
            continue
        for chunk in line.split("pid=")[1:]:
            pid = chunk.split(",")[0].strip()
            if pid.isdigit():
                owners.add(pid)

    # The families: the servers, their reloader children, their helpers, and the
    # frontend's supervisor chain. `hermes acp` is deliberately NOT here -- the
    # live ACP agent is the uvicorn's child and is covered by the test-family
    # scan instead.
    family = (
        "uvicorn",
        "multiprocessing.spawn",
        "multiprocessing.resource_tracker",
        "vite-supervisor",
        "npm exec vite",
        "node_modules/.bin/vite",
        "esbuild",
    )
    try:
        out = subprocess.run(
            ["ps", "-eo", "pid,ppid,etime,cmd"], capture_output=True, text=True, timeout=15
        ).stdout
    except Exception:
        return 0, "⚠️  ps unavailable — the orphaned-backend scan was skipped"

    # Every pid alive right now -- a family member whose PARENT is alive is a
    # legitimate helper (the resource_tracker, the reloader's worker), never a
    # WHO IS LEGITIMATE — three rules, and each was found by getting it wrong
    # first. Together they define "the live instance" precisely:
    #
    #   1. it OWNS the port (the server itself); or
    #   2. it is an ANCESTOR of a port owner (the supervisor chain — measured
    #      live: vite-supervisor -> npm exec vite -> sh -c vite -> node vite, and
    #      only the LAST owns the port. Without this rule the supervisor itself
    #      was flagged as a stray on a perfectly healthy app); or
    #   3. its PARENT IS ALIVE (the helpers — the resource_tracker owns no port
    #      and is nobody's ancestor, but its parent is the running uvicorn.
    #      Port ownership alone flagged it).
    #
    # PID 1 is EXCLUDED from "alive" deliberately: it is where orphans GO, not a
    # real parent. Including it made every reparented process look legitimate and
    # the check reported clean WITH A STRAY RUNNING — caught by provoking it.
    parent_of: dict[str, str] = {}
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2:
            parent_of[parts[0]] = parts[1]

    legitimate: set[str] = set(owners)
    for owner in owners:
        ancestor = parent_of.get(owner)
        while ancestor and ancestor != "1" and ancestor not in legitimate:
            legitimate.add(ancestor)
            ancestor = parent_of.get(ancestor)
    for pid, ppid in parent_of.items():
        if ppid != "1" and ppid in parent_of:
            legitimate.add(pid)  # its parent is running — it is that parent's helper

    strays = []
    for line in out.splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, ppid, age, cmd = parts
        if not any(f in cmd for f in family):
            continue
        if pid in legitimate:
            continue
        strays.append((pid, ppid, age, cmd[:110]))

    if strays:
        lines = [
            f"  ❌ PID {pid} (ppid {ppid}, up {age}): {cmd}" for pid, ppid, age, cmd in strays
        ]
        output = (
            f"Leftover app processes (ports {sorted(f':{p}' for p in ports)} owned by "
            f"{sorted(owners) or 'nobody'}):\n" + "\n".join(lines)
        )
        output += "\n\nThese are restart-churn leftovers — they hold the DB and can\n"
        output += "fight the live instance. To fix:\n  kill -9 " + " ".join(p for p, _, _, _ in strays)
        return 1, output
    return 0, (
        "✅ No orphaned app processes "
        f"(ports {sorted(f':{p}' for p in ports)} owned by {sorted(owners) or 'nobody'})"
    )


def check_ghost_session_rows():
    """Scan for ghost chat history — rows that belong to no session, or predate it.

    THE CLASS (the session-3 collision): a message whose `created_at` precedes the
    session it is attached to, or whose session no longer exists. Both mean history
    is attached to the wrong session — the session id was reused, or a session was
    replaced while its messages survived.

    DISTINCT from `check_ghost_databases`, which scans for zero-size .db FILES on
    disk. This is about ROWS.

    REPORT-ONLY.
    """
    import sqlite3

    # Overridable so the check can be PROVEN to fire against a synthetic case --
    # a gate never seen to fire is this project's recurring defect.
    db = Path(os.environ.get("COGITATE_SWEEP_DB", str(REPO_ROOT / "cogitate.db")))
    if not db.exists():
        return 0, f"⚠️  {db.name} absent — the ghost-session-row scan was skipped"

    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except Exception as exc:
        return 0, f"⚠️  could not open cogitate.db ({exc}) — scan skipped"

    try:
        orphans = con.execute(
            """SELECT m.session_id, COUNT(*) FROM chat_messages m
               LEFT JOIN chat_sessions s ON m.session_id = s.id
               WHERE s.id IS NULL GROUP BY m.session_id"""
        ).fetchall()

        predating = con.execute(
            """SELECT m.session_id, COUNT(*), MIN(m.created_at), s.created_at
               FROM chat_messages m JOIN chat_sessions s ON m.session_id = s.id
               WHERE m.created_at < s.created_at
               GROUP BY m.session_id"""
        ).fetchall()
    except sqlite3.OperationalError as exc:
        return 0, f"⚠️  chat tables not present ({exc}) — scan skipped"
    finally:
        con.close()

    if not orphans and not predating:
        return 0, "✅ No ghost chat rows (every message belongs to its session, none predating)"

    lines = []
    for sid, n in orphans:
        lines.append(f"  ❌ session_id {sid}: {n} message(s) with NO session row (orphaned)")
    for sid, n, oldest, session_start in predating:
        lines.append(
            f"  ❌ session_id {sid}: {n} message(s) PREDATE the session "
            f"(oldest {oldest} < session {session_start})"
        )
    output = "Ghost chat rows (history attached to the wrong session):\n" + "\n".join(lines)
    output += "\n\nReport only — decide with the user before removing any history."
    return 1, output


def get_all_checks(include_slow=False):
    """Return a list of (check_fn, label) tuples for all backend checks."""
    checks = [
        (check_mypy, "Backend: mypy"),
        (check_imports, "Backend: import check"),
        (check_deprecation_warnings, "Backend: deprecation warnings"),
    ]
    if include_slow:
        checks.append((check_pytest_all, "Backend: pytest (all tests)"))
    else:
        checks.append((check_pytest, "Backend: pytest (fast tests)"))
    checks.append((check_router_decorators, "Router decorator check (dangling handlers)"))
    checks.append((check_path_arithmetic, "Path arithmetic check (the Paths locator discipline)"))
    checks.append((check_absolute_paths, "Absolute-path check (private info must not ship)"))
    checks.append((check_stale_cogitate_dbs, "Stale cogitate.db check"))
    checks.append((check_ghost_databases, "Ghost database scan"))
    checks.append((check_stale_tmp_databases, "Stale /tmp test-leftover scan (temp-dbs + installation roots)"))
    checks.append((check_zombie_processes, "Zombie test-process scan"))
    checks.append((check_orphaned_backends, "Orphaned-backend scan (restart churn)"))
    checks.append((check_ghost_session_rows, "Ghost chat-row scan (history on the wrong session)"))
    checks.append((check_atlas_validation, "Atlas validation (wiki/atlas)"))
    checks.append((check_test_catalog, "Test catalog check (the rendered descriptions)"))
    checks.append((check_agent_health, "Agent health scan (providers/models)"))
    return checks


def get_parallel_checks(include_slow=False):
    """Return a list of (check_fn, label) tuples for checks that can run in parallel.

    pytest is excluded because it needs exclusive DB access.
    """
    quick_checks = [
        (check_mypy, "Backend: mypy"),
        (check_imports, "Backend: import check"),
        (check_deprecation_warnings, "Backend: deprecation warnings"),
        (check_router_decorators, "Router decorator check (dangling handlers)"),
        (check_path_arithmetic, "Path arithmetic check (the Paths locator discipline)"),
        (check_absolute_paths, "Absolute-path check (private info must not ship)"),
        (check_atlas_validation, "Atlas validation (wiki/atlas)"),
        (check_test_catalog, "Test catalog check (the rendered descriptions)"),
        (check_agent_health, "Agent health scan (providers/models)"),
        (check_stale_tmp_databases, "Stale /tmp test-leftover scan (temp-dbs + installation roots)"),
        (check_zombie_processes, "Zombie test-process scan"),
        (check_orphaned_backends, "Orphaned-backend scan (restart churn)"),
        (check_ghost_session_rows, "Ghost chat-row scan (history on the wrong session)"),
    ]
    return quick_checks


def get_pytest_check(include_slow=False):
    """Return the (check_fn, label) tuple for the pytest check (runs alone)."""
    if include_slow:
        return (check_pytest_all, "Backend: pytest (all tests)")
    return (check_pytest, "Backend: pytest (fast tests)")
