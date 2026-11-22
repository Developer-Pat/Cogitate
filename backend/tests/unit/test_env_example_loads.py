"""A fresh `.env` must never stop the backend from loading.

Measured 2026-11-22 on a *release* install — the first time the flow ran from a tarball rather than
this author's working tree. Every earlier install copied `.env` once, and `.env` is never overwritten,
so the defect could not appear on any machine that had installed before it was introduced:

    `INPUT_TOKEN_BUDGET=` in `.env.example`
      → `int("")` at import
      → `pydantic_core.ValidationError`
      → the backend cannot import
      → `install` stops at its own verification step.

Two independent causes, and both are pinned here because either alone reproduces the failure:

1. The env-example generator treated the KEY NAME as proof of a secret (`_TOKEN`) and wrote an empty
   placeholder for a NUMBER. A non-string field cannot be a secret.
2. The setting itself accepted no empty value, so a hand-edited `.env` (or any other generator) could
   reintroduce the same crash. Empty means "use the default".
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import Paths

PROJECT_ROOT = Path(str(Paths.root))


def _load_generator():
    """The env-example generator, imported by path — it is a script, not a package."""
    path = PROJECT_ROOT / "scripts" / "dev" / "generate_env_example.py"
    spec = importlib.util.spec_from_file_location("generate_env_example", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_an_empty_input_budget_uses_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """`INPUT_TOKEN_BUDGET=` (empty) loads as the shipped default rather than raising."""
    monkeypatch.setenv("INPUT_TOKEN_BUDGET", "")
    from app.core.config import Settings

    assert Settings().input_token_budget == 100_000


def test_a_set_input_budget_is_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """The override still works — the empty case must not swallow a real number."""
    monkeypatch.setenv("INPUT_TOKEN_BUDGET", "50000")
    from app.core.config import Settings

    assert Settings().input_token_budget == 50_000


def test_a_numeric_setting_is_never_written_as_an_empty_secret() -> None:
    """The generator's `_TOKEN` heuristic must not empty a NUMBER.

    This is the defect exactly: the name matched a secret hint, so the line was written as
    `INPUT_TOKEN_BUDGET=` with no value, and the value that arrived was `""`.
    """
    module = _load_generator()
    fields = module._settings().model_fields

    for name, field in fields.items():
        if isinstance(field.default, str) or field.default is None:
            continue
        entry = "\n".join(module._entry(name, field))
        assert "secret:" not in entry, f"{name} is numeric but was written as a secret placeholder"
        assert not entry.rstrip().endswith("="), f"{name} would be written with an empty value"


def test_the_shipped_env_example_carries_a_value_for_every_numeric_setting() -> None:
    """The committed `.env.example` agrees with the rule, not just the generator's code.

    A stale file is how this reaches a user: `install` copies it verbatim and never rewrites a value.
    """
    module = _load_generator()
    text = (PROJECT_ROOT / ".env.example").read_text()
    for name, field in module._settings().model_fields.items():
        if isinstance(field.default, str) or field.default is None:
            continue
        env_name = name.upper()
        line = next(
            (ln for ln in text.splitlines() if ln.startswith(f"{env_name}=")),
            None,
        )
        assert line is not None, f"{env_name} is missing from .env.example"
        assert line.split("=", 1)[1].strip() != "", f"{env_name}= is empty — it would fail to parse"


def test_a_fresh_env_copies_and_imports(tmp_path: Path) -> None:
    """End to end: copy `.env.example` to `.env`, then load the settings with it.

    This is the install's own verification step, reproduced without a full install — the exact
    situation that failed: a directory whose `.env` came straight from the template.
    """
    (tmp_path / ".env").write_text((PROJECT_ROOT / ".env.example").read_text())

    env = {**os.environ, "PYTHONPATH": str(PROJECT_ROOT / "backend")}
    for key in ("INPUT_TOKEN_BUDGET",):
        env.pop(key, None)  # the file is the source under test, not this shell

    result = subprocess.run(
        [sys.executable, "-c", "from app.core.config import Settings; print(Settings().input_token_budget)"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert result.stdout.strip() == "100000"

