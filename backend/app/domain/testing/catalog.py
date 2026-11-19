"""
The test CATALOG — what tests exist, what they protect, and what they need.

THE USER-TESTING PAGE, Phase A. The page's data substrate.

**The governing idea: the catalog is DERIVED, not authored.** Every fact here
is read from the test tree, so there is nothing to keep in sync by hand and
nothing to rot:

  - the DESCRIPTION is the module docstring's first line. The prose already
    lives beside each test, which is where a maintainer will keep it. 166 of
    169 files had a usable one-liner when this was written.
  - the CLUSTER is the file's directory, or the leading token of its filename
    for the flat `unit/` set.
  - the TIME CLASS is a DEPENDENCY CLASS, never a stopwatch reading. A duration
    measured on one machine is a lie on another; a test's dependencies are not.
    `short` = no I/O, `medium` = local I/O, `variable` = an external service.

WHY DERIVE: 169 files x 1402 tests is too much to describe by hand, and a
hand-written description is a claim that nothing checks. A derived one is
anchored to the file it describes — change the docstring and the entry changes
with it.

WHAT THIS CANNOT DO YET, stated plainly so it is not mistaken for done:

  - **The `live`/`backend` markers are barely applied** (`live` on 1 file,
    `backend` on 2, against ~32 files that mention an external service). So
    `CONDITIONAL_FILES` below is a marker read, NOT a claim that everything
    needing a service is marked. Grepping for `ollama` over-reports — a mention
    is not a call. **The honest signal is behaviour: which tests fail when the
    service is absent.** Until that triage is run, this under-reports.
  - Time classes are inferred from imports and markers, so they are a GUIDE to
    the ordering, not a measurement.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.config import Paths


# ── the vocabularies ────────────────────────────────────────────────────────

#: The time classes. Driven by DEPENDENCIES, never by a stopwatch.
SHORT = "short"       # no I/O — pure logic
MEDIUM = "medium"     # local I/O — db, filesystem, the app in-process
VARIABLE = "variable"  # an external service; the network dominates

#: The tabs the page shows. Ordered least-dependent first, so the order is
#: also the diagnosis (the tier doctrine, wiki/dev-notes/testing/test-tiers.md).
TAB_RUNNABLE = "runnable"
TAB_CONDITIONAL = "conditional"
TAB_QUARANTINE = "quarantine"
#: The page's OWN exercise (backend/selftest/). Its own tab because it is not a
#: class of test in the suite — it is the page's instrument, and it is red when
#: it is working.
TAB_SELFTEST = "selftest"

#: Why the Self-test tab is red, said once and shown on the row like every other
#: condition. A deliberately failing suite that does not SAY it is deliberately
#: failing reads as a broken app. What it does NOT say is how the page arranges
#: it (groups, sweeps, selection by name) — that is developer documentation and
#: lives in wiki/dev-notes/testing/README.md and the fixture's own docstring.
SELFTEST_CONDITION = "the page's own check — deliberately failing tests"

#: The module-level name a self-test file declares its PASS CONDITION in
#: (`EXPECTED_SHAPE = "2 passed, 1 failed, …"`). Read out of the file so the page
#: shows the fixture's own sentence rather than a copy that drifts from it.
EXPECTED_SHAPE_CONST = "EXPECTED_SHAPE"

#: Marker -> (tab, condition text). The condition is what the user is told
#: when the test does not run, so it names the DEPENDENCY, not the marker.
CONDITION_MARKERS: dict[str, tuple[str, str]] = {
    "backend": (TAB_CONDITIONAL, "needs the backend running"),
    "quarantine": (TAB_QUARANTINE, "quarantined — the suite's ordering defect"),
}

#: THE EXTERNAL CLASS. `external` carries its dependency as an
#: ARGUMENT — `@pytest.mark.external("ollama")` — so the tab can say WHICH
#: service is missing rather than a generic "something external". That is the
#: whole point of the rename: the class is generic, the dependency is data.
#: `live` (which named one instance) is retired.
EXTERNAL_MARKER = "external"

#: What each dependency is, for the row and the modal — the user must be able to
#: act on it, and "external unavailable" is not actionable.
DEPENDENCY_LABELS: dict[str, str] = {
    "ollama": "needs local Ollama",
    "llama-cpp": "needs the local llama.cpp server",
    "embeddings": "needs an embedding provider (local Ollama)",
}

#: Import/reference signals that raise a file above `short`.
#:
#: These name EVIDENCE OF THE WORK, not merely an import. `pathlib` is NOT a
#: signal: nearly every test imports it without doing file I/O, and including
#: it made 122 of 169 files `medium` — a class that says nothing. The evidence
#: for file work is the FIXTURE (`tmp_path`), which only appears when a test
#: really touches the filesystem.
_DB_SIGNALS = ("sqlalchemy", "aiosqlite", "sqlite3", "AsyncSession", "app.infrastructure.database")
_APP_SIGNALS = ("fastapi.testclient", "TestClient", "app.main", "app.api")
_FS_SIGNALS = ("tmp_path", "tmpdir")

#: `unit/` is the catch-all: 81 files directly in it, no subdirectory, each
#: carrying its domain in its NAME (`test_agent_kits.py` -> `unit/agent`). The
#: other groups are already coherent domains, so for them the directory IS the
#: cluster. Without this rule the whole flat set collapses into one 81-file
#: cluster, which groups nothing.
FLAT_GROUPS = {"unit"}

#: Markers are read from the AST, never from the text. A regex over the source
#: matched marker LOOKALIKES inside strings — this project's own gate test
#: carries `'@pytest.mark.external("nonsense-service")'` as test DATA, and the
#: catalog duly reported that file as needing a service called
#: "nonsense-service". Same over-reporting class as classifying by grep, caught
#: by the catalog itself. Only real decorators and real `pytestmark`
#: assignments count.
_MARKER_ATTR_RE = re.compile(r"^mark\.([a-z_]+)$")


@dataclass
class CatalogEntry:
    """One test FILE — the catalog's unit of description."""

    path: str              # tests-relative, e.g. "unit/tools/test_declarative_tools.py"
    #: THE PATH A RUN TAKES, as the runner wants it (`--file tests/unit/x.py`).
    #: Derivation, not assembly: the page must never join "tests" onto `path`
    #: itself — that is the drift class the locator exists to end, and it is how
    #: a run silently selects nothing when the tree moves.
    run_path: str = ""
    filename: str = ""
    group: str = ""        # "unit" | "workflows" | "api" | "components" | …
    cluster: str = ""      # the domain key, e.g. "unit/tools"
    description: str = ""  # the docstring's first line, or "" if there is none
    test_count: int = 0    # how many `def test_` it holds
    time_class: str = ""   # SHORT | MEDIUM | VARIABLE
    tab: str = ""          # TAB_RUNNABLE | TAB_CONDITIONAL | TAB_QUARANTINE
    condition: str | None = None
    #: The PASS CONDITION a self-test file declares — the fixture's own
    #: sentence, shown beside the Self-test tab. Empty for the whole suite.
    expectation: str = ""
    markers: list[str] = field(default_factory=list)
    has_suite: bool = False  # carries an @pytest.mark.asyncio/suite marker


@dataclass
class Cluster:
    """A named group of test files — the table's grouping column."""

    key: str
    label: str
    files: int
    tests: int
    time_class: str


# ── the derivation ──────────────────────────────────────────────────────────


def _first_line(docstring: str | None) -> str:
    """The docstring's first non-empty line, trimmed to a one-liner."""
    if not docstring:
        return ""
    for line in docstring.strip().splitlines():
        line = line.strip()
        if line:
            return line if len(line) <= 120 else line[:117] + "…"
    return ""


def _cluster_for(rel_parts: tuple[str, ...], filename: str) -> str:
    """The cluster key: the directory, or the filename's leading token.

    The flat `unit/` set is 81 files with no subdirectory, so its cluster has
    to come from the name — `test_agent_kits.py` -> `unit/agent`. That is the
    derivation the whole catalog leans on, and it is deliberately mechanical so
    it cannot silently disagree with the tree.
    """
    # A file sitting directly in tests/ has no directory to name it, and
    # `"/".join(())` is the empty string — which produced an unnamed cluster
    # holding two files. Name it instead of leaving it blank.
    if len(rel_parts) == 1:
        return "tests (root)"
    if rel_parts[0] in FLAT_GROUPS and len(rel_parts) == 2:
        m = re.match(r"test_([a-z0-9]+)", filename)
        return f"{rel_parts[0]}/{m.group(1)}" if m else f"{rel_parts[0]}/misc"
    return "/".join(rel_parts[:-1])


def _time_class_for(source: str, markers: list[str]) -> str:
    """Infer the dependency class from what the file references.

    A GUIDE to the ordering, not a measurement. An `external` dependency beats
    everything: a file that talks to a service is variable no matter what else
    it imports, because the network dominates and our CPU is irrelevant.
    """
    if EXTERNAL_MARKER in markers:
        return VARIABLE
    for signal in _APP_SIGNALS:
        if signal in source:
            return MEDIUM
    for signal in _DB_SIGNALS:
        if signal in source:
            return MEDIUM
    for signal in _FS_SIGNALS:
        if signal in source:
            return MEDIUM
    return SHORT


def _label_for(key: str) -> str:
    """`unit/cognitive_pipeline` -> `Cognitive Pipeline`. Mechanical on purpose."""
    leaf = key.split("/")[-1]
    return leaf.replace("_", " ").title()


def _markers_from_ast(tree: ast.AST) -> tuple[set[str], set[str]]:
    """The REAL markers a file carries: `(names, external_dependencies)`.

    Only two shapes count, because those are the only two pytest honours:
      - a decorator:            `@pytest.mark.backend`
      - the module assignment:  `pytestmark = pytest.mark.external("ollama")`

    Read from the AST rather than the text on purpose. A regex matched
    lookalikes inside STRING LITERALS — this project's own gate test holds
    `'@pytest.mark.external("nonsense-service")'` as test data, and the catalog
    reported that file as needing a service named "nonsense-service".
    """
    names: set[str] = set()
    deps: set[str] = set()

    def read(node: ast.AST) -> None:
        # Unwrap a call first: `@pytest.mark.external("ollama")` is a Call whose
        # func is the Attribute, and whose args carry the DEPENDENCY.
        if isinstance(node, ast.Call):
            read(node.func)
            if _is_external_attr(node.func):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        deps.add(arg.value)
            return
        # `pytest.mark.<name>` — the only attribute chain pytest reads.
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Attribute)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id == "pytest"
            and node.value.attr == "mark"
        ):
            names.add(node.attr)

    def _is_external_attr(n: ast.AST) -> bool:
        return (
            isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Attribute)
            and isinstance(n.value.value, ast.Name)
            and n.value.value.id == "pytest"
            and n.value.attr == "mark"
            and n.attr == EXTERNAL_MARKER
        )

    for node in ast.walk(tree):
        # decorators
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            for dec in node.decorator_list:
                read(dec)
        # the module-level assignment
        if isinstance(node, ast.Assign):
            if any(
                isinstance(t, ast.Name) and t.id == "pytestmark"
                for t in node.targets
            ):
                read(node.value)
    return names, deps


def _run_path_for(path: Path, tests_dir: Path) -> str:
    """The path a RUN takes for this file — backend-relative, e.g. `tests/unit/x.py`.

    The runner accepts `--file tests/unit/foo.py`, and the catalog's own `path` is
    tests-relative. Those two are one string apart, which is exactly the kind of
    near-miss that ends in a renamed tree and a run that selects nothing, so the
    mapping is derived here, in one place, and sent to the page as data.

    Falls back to the tests-relative form when the tree is not where the layout
    says it is — a wrong-but-visible path beats an exception in a catalog build.
    """
    backend = tests_dir.parent
    try:
        return path.resolve().relative_to(backend.resolve()).as_posix()
    except ValueError:
        return path.relative_to(tests_dir).as_posix()


def _string_constant(node: ast.AST) -> str | None:
    """The string a declaration holds, or None if it is not one.

    Adjacent literals are folded by the parser into one Constant; an explicit
    `+` chain is joined here. Both spellings are legal Python for the same
    declaration, and the reader should not care which one a fixture used.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _string_constant(node.left), _string_constant(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _expected_shape_from_ast(tree: ast.AST) -> str:
    """The self-test file's own `EXPECTED_SHAPE`, or "" when it declares none.

    Read from the file rather than kept in the page: the pass condition of a
    deliberately red suite is a fact about that suite, and the moment it is
    copied into the frontend the two can disagree.
    """
    body = tree.body if isinstance(tree, ast.Module) else []
    for node in body:
        if not isinstance(node, ast.Assign):
            continue
        named = any(
            isinstance(t, ast.Name) and t.id == EXPECTED_SHAPE_CONST
            for t in node.targets
        )
        if named:
            return _string_constant(node.value) or ""
    return ""


def _parse(
    path_str: str,
    rel: str,
    run_path: str,
    *,
    selftest: bool = False,
) -> CatalogEntry | None:
    """Derive one entry. Returns None if the file cannot be parsed.

    `selftest` marks a file from the page's OWN exercise (`backend/selftest/`).
    Such a file carries no marker — its tab comes from where it lives, and its
    declared pass condition comes with it, because a suite that is red on
    purpose has to say so where the page can read it.
    """
    try:
        source = path_str
        tree = ast.parse(source)
    except (SyntaxError, OSError, UnicodeDecodeError):
        return None

    rel_parts = tuple(rel.split("/"))
    filename = rel_parts[-1]
    raw_names, raw_deps = _markers_from_ast(tree)
    known = set(CONDITION_MARKERS) | {EXTERNAL_MARKER}
    markers = sorted(raw_names & known)
    external_deps = sorted(raw_deps)

    tab, condition = TAB_RUNNABLE, None
    # `external` first: it names the SPECIFIC dependency, so its condition is
    # the useful one ("needs local Ollama", not "needs something external").
    if EXTERNAL_MARKER in markers:
        # A file may declare several; name them all rather than the first, so a
        # test needing two services does not read as needing one.
        deps = [DEPENDENCY_LABELS.get(d, f"needs {d}")
                for d in external_deps] or ["needs an external service"]
        tab, condition = TAB_CONDITIONAL, " · ".join(deps)
    else:
        for marker in markers:
            if marker in CONDITION_MARKERS:
                m_tab, m_cond = CONDITION_MARKERS[marker]
                if m_tab != TAB_RUNNABLE:
                    tab, condition = m_tab, m_cond
                    break

    # The page's own exercise outranks the markers: it carries none, and its
    # tab belongs to the page rather than to a tier of the suite.
    expectation = ""
    if selftest:
        tab, condition = TAB_SELFTEST, SELFTEST_CONDITION
        expectation = _expected_shape_from_ast(tree)

    return CatalogEntry(
        path=rel,
        run_path=run_path,
        filename=filename,
        group=rel_parts[0],
        cluster=_cluster_for(rel_parts, filename),
        description=_first_line(ast.get_docstring(tree)),
        test_count=sum(
            1 for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and n.name.startswith("test_")
        ),
        time_class=_time_class_for(source, markers),
        tab=tab,
        condition=condition,
        expectation=expectation,
        markers=markers,
    )


def build_catalog() -> dict[str, Any]:
    """Build the whole catalog from the test tree.

    Returns a plain dict so it can be serialised straight to the API. If there
    is no test tree — an installed build, not a checkout — this returns an
    EMPTY catalog WITH A REASON rather than raising or pretending. A page that
    says "no test tree here" is honest; one that shows an empty table is not.
    """
    tests_dir = Paths.tests_dir
    if not tests_dir.is_dir():
        return {
            "available": False,
            "reason": "no test tree — this is an installed build, not a checkout",
            "totals": {"files": 0, "tests": 0, "clusters": 0},
            "clusters": [],
            "tests": [],
        }

    entries: list[CatalogEntry] = []
    for path in sorted(tests_dir.rglob("test_*.py")):
        rel = path.relative_to(tests_dir).as_posix()
        # The path the RUNNER takes is derived HERE, from the same tree walk —
        # the page sends it back verbatim instead of rebuilding it.
        run_path = _run_path_for(path, tests_dir)
        entry = _parse(path.read_text(encoding="utf-8", errors="replace"), rel, run_path)
        if entry is not None:
            entries.append(entry)

    # THE PAGE'S OWN EXERCISE, from its own dir. It is separated by PATH rather
    # than by a marker so that nothing can collect it by accident: it sits
    # outside tests/, and tests/ is what `testpaths` and every runner group
    # select. A red fixture inside the tree would redden every full run.
    selftest_dir = Paths.selftest_dir
    if selftest_dir.is_dir():
        for path in sorted(selftest_dir.rglob("test_*.py")):
            rel = f"{selftest_dir.name}/{path.relative_to(selftest_dir).as_posix()}"
            entry = _parse(
                path.read_text(encoding="utf-8", errors="replace"),
                rel,
                _run_path_for(path, selftest_dir),
                selftest=True,
            )
            if entry is not None:
                entries.append(entry)

    totals_by_cluster: dict[str, list[CatalogEntry]] = {}
    for e in entries:
        totals_by_cluster.setdefault(e.cluster, []).append(e)

    clusters = [
        Cluster(
            key=key,
            label=_label_for(key),
            files=len(members),
            tests=sum(m.test_count for m in members),
            # The cluster's class is its heaviest member: a group is only as
            # fast as its slowest part, and saying otherwise would mislead.
            time_class=max((m.time_class for m in members),
                           key=lambda c: [SHORT, MEDIUM, VARIABLE].index(c)),
        )
        for key, members in sorted(totals_by_cluster.items())
    ]

    return {
        "available": True,
        "reason": None,
        "totals": {
            "files": len(entries),
            "tests": sum(e.test_count for e in entries),
            "clusters": len(clusters),
        },
        "clusters": [c.__dict__ for c in clusters],
        "tests": [e.__dict__ for e in sorted(entries, key=lambda e: e.path)],
    }
