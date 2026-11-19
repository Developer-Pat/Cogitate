"""One writer: no path decides a chat turn's budget for itself.

The point of the arc's C.1, pinned by reading the source rather than by sampling
numbers.

Before this phase seven writers decided one turn's output budget and nothing said
which was authoritative (the study, §3). The resolver is the decision now, and
the tests in this arc's other files check the NUMBERS. This file checks the thing
that makes the numbers stay true: that no writer goes back to deciding for
itself.

Two shapes are refused, in the modules that decide a chat turn's budget:

* an assignment into a key named ``max_tokens`` whose right-hand side is not the
  resolver's own call (`_budget`, `apply_output_budget(...)`);
* a lookup that supplies its OWN default (``.get("max_tokens", 2000)``) — the
  form the caps and the old node default used.

A third check keeps the floor single: ``REASONING_MAX_TOKENS_FLOOR`` may be
referenced in exactly two modules — its own (`reasoning_support`, where the VALUE
lives) and the resolver (`output_budget`, which applies it in `floor_budget`).
F.2/F-B retired the separate floor helper and folded the executor's numbers onto
the shared constants, so `executor.py` is a checked writer too: the run path
`/agent-chat` uses no longer decides a budget for itself.

The modules are read through `Paths.root` — never a path derived from
`__file__` (the repo's own guard refuses those, in tests too).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.core.config import Paths

REPO = Path(str(Paths.root))

# The modules that decide a chat turn's budget (the study's writers C.1 folded
# in, plus the two live ones the phase ruling added, plus `/agent-chat` — which
# decides a budget since G-F and must stay unable to type one).
WRITER_MODULES = {
    "chat/router.py": REPO / "backend/app/api/v1/chat/router.py",
    "chat/context.py": REPO / "backend/app/api/v1/chat/context.py",
    "domain/chat/services.py": REPO / "backend/app/domain/chat/services.py",
    "workflows/nodes/agent_nodes.py": REPO / "backend/app/workflows/nodes/agent_nodes.py",
    "services/cognitive_pipeline/executor.py": REPO / "backend/app/services/cognitive_pipeline/executor.py",
    "agent_chat/router.py": REPO / "backend/app/api/v1/agent_chat/router.py",
}

# An assignment into a request/params mapping: `request_kwargs["max_tokens"] = …`
SUBSCRIPT = re.compile(r"""^\s*[\w.]+\[["']max_tokens["']\]\s*=\s*(?P<rhs>.+)$""")
# A bare local assignment to a literal — `max_tokens = 4096`. The spaces around
# `=` matter: a keyword argument inside a multi-line call is written
# `max_tokens=max_tokens_arg,` and is not a decision.
BARE_LITERAL = re.compile(r"""^\s*max_tokens\s+=\s+\d""")
# A lookup that supplies its own default: .get("max_tokens", <something>) —
# the shape of every retired cap and of the workflow node's old 2000.
OWN_DEFAULT = re.compile(r"""\.get\(\s*["']max_tokens["']\s*,""")

# The only right-hand sides allowed where a budget is written.
ALLOWED_RHS = ("_budget", "apply_output_budget(")


def _sources() -> dict[str, str]:
    return {name: path.read_text() for name, path in WRITER_MODULES.items()}


@pytest.mark.parametrize("name", sorted(WRITER_MODULES))
def test_the_module_exists(name: str):
    """A moved file must fail loudly here, not silently stop being checked."""
    assert WRITER_MODULES[name].is_file(), f"{name} is gone — update this guard"


@pytest.mark.parametrize("name", sorted(WRITER_MODULES))
def test_no_writer_decides_a_budget_for_itself(name: str):
    offenders = []
    for number, line in enumerate(_sources()[name].splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        match = SUBSCRIPT.search(line)
        if match and not match.group("rhs").startswith(ALLOWED_RHS):
            offenders.append(f"{name}:{number}: {stripped}")
        if BARE_LITERAL.search(line):
            offenders.append(f"{name}:{number}: {stripped}")
    assert not offenders, (
        "a budget is written without the resolver — every writer calls "
        "`apply_output_budget`/`resolve_output_budget`:\n" + "\n".join(offenders)
    )


@pytest.mark.parametrize("name", sorted(WRITER_MODULES))
def test_no_writer_supplies_its_own_default(name: str):
    offenders = [
        f"{name}:{number}: {line.strip()}"
        for number, line in enumerate(_sources()[name].splitlines(), start=1)
        if OWN_DEFAULT.search(line) and not line.strip().startswith("#")
    ]
    assert not offenders, (
        "a `max_tokens` lookup carries its own default — undeclared budgets are "
        "the resolver's fallback, not a literal at the call site:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize("name", sorted(WRITER_MODULES))
def test_no_path_applies_the_thinking_floor_itself(name: str):
    """C.5 + F-B: one floor, applied in the resolver's `floor_budget`."""
    assert "REASONING_MAX_TOKENS_FLOOR" not in _sources()[name], (
        f"{name} applies the thinking floor itself — "
        "`output_budget.floor_budget` is the one application"
    )


def test_only_the_resolver_defines_the_ladder():
    """The fast policy, the deep minimum and the fallback have one home."""
    defined = set()
    for path in (REPO / "backend/app").rglob("*.py"):
        source = path.read_text()
        for constant in ("FAST_POLICY_BUDGET", "DEEP_MIN_BUDGET", "FALLBACK_BUDGET"):
            if re.search(rf"^{constant}\s*=", source, flags=re.MULTILINE):
                defined.add((constant, path.name))
    assert defined == {
        ("FAST_POLICY_BUDGET", "output_budget.py"),
        ("DEEP_MIN_BUDGET", "output_budget.py"),
        ("FALLBACK_BUDGET", "output_budget.py"),
    }, f"a ladder constant has a second home: {sorted(defined)}"
