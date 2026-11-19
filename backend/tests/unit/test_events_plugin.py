"""The events plugin's COLLECT event — the run's total, and where it comes from.

`scripts/testing/events_plugin.py` rule 4: the collected total has TWO sources,
and the parts worth pinning are the ones that are easy to get subtly wrong.

- It is INERT without `COGITATE_EVENTS_FILE`, like every other event.
- A WORKER stays silent, so the total cannot be written once per xdist worker.
- The parallel source takes the LARGEST report, **never the sum**: every worker
  collects the whole session, so a sum would report a 13× run to the page.
- A repeated report does not append a second identical line.

The measurement behind the two-source design is in the plugin's docstring (the
controller holds no items under `-n auto` — its `session.items` is empty even at
`sessionfinish`). These tests pin the CONTRACT that measurement produced.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

from app.core.config import Paths

#: The plugin the runner loads — resolved through the LOCATOR, never re-derived
#: from `__file__` (the project's path rule: one place knows where things live).
PLUGIN_PATH = Path(Paths.root) / "scripts" / "testing" / "events_plugin.py"


def load_plugin() -> Any:
    """A FRESH module per test — the plugin keeps a module-level high-water mark."""
    spec = importlib.util.spec_from_file_location("cogitate_events_plugin_under_test",
                                                  PLUGIN_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture
def plugin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """The plugin, pointed at a temp events file."""
    module = load_plugin()
    monkeypatch.setenv("COGITATE_EVENTS_FILE", str(tmp_path / "events.jsonl"))
    return module


def events_file(tmp_path: Path) -> Path:
    return tmp_path / "events.jsonl"


def test_it_is_INERT_without_the_environment_variable(tmp_path: Path,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    """A plain `pytest` call — a developer, CI, the sweep — writes nothing."""
    module = load_plugin()
    monkeypatch.delenv("COGITATE_EVENTS_FILE", raising=False)
    module.pytest_collection_modifyitems(None, None, [1, 2, 3])
    module.pytest_xdist_node_collection_finished(None, ["a", "b"])
    assert lines(events_file(tmp_path)) == []


def test_a_WORKER_stays_silent(plugin: Any, tmp_path: Path,
                              monkeypatch: pytest.MonkeyPatch) -> None:
    """Rule 2 — a worker's report is a fragment, and N workers would write N lines."""
    monkeypatch.setattr(plugin, "_SILENT", True)
    plugin.pytest_collection_modifyitems(None, None, [1, 2, 3])
    assert lines(events_file(tmp_path)) == []


def test_the_SERIAL_report_is_the_whole_session(plugin: Any, tmp_path: Path) -> None:
    """In serial the process running the tests IS the collector."""
    plugin.pytest_collection_modifyitems(None, None, [object() for _ in range(26)])
    assert lines(events_file(tmp_path)) == [{"t": "collect", "count": 26, "via": "session"}]


def test_a_repeated_report_does_not_append_a_second_line(plugin: Any, tmp_path: Path) -> None:
    plugin.pytest_collection_modifyitems(None, None, [1, 2, 3])
    plugin.pytest_collection_modifyitems(None, None, [1, 2, 3])
    assert lines(events_file(tmp_path)) == [{"t": "collect", "count": 3, "via": "session"}]


def test_the_PARALLEL_source_takes_the_LARGEST_report_not_the_sum(plugin: Any,
                                                                 tmp_path: Path) -> None:
    """The trap the source exists to avoid.

    Every xdist worker collects the WHOLE session before the controller assigns
    work, so 12 nodes × 26 ids is 26 tests — not 312. Taking the sum here would
    make the page claim a run thirteen times its real size.
    """
    ids = [f"tests/unit/x.py::test_{i}" for i in range(26)]
    for _ in range(12):
        plugin.pytest_xdist_node_collection_finished(None, ids)
    assert lines(events_file(tmp_path)) == [{"t": "collect", "count": 26, "via": "xdist"}]


def test_a_BIGGER_report_is_appended_never_dropped(plugin: Any, tmp_path: Path) -> None:
    """Reports can arrive out of order; the page reads the latest, not the first."""
    plugin.pytest_xdist_node_collection_finished(None, ["a"])
    plugin.pytest_xdist_node_collection_finished(None, ["a", "b", "c"])
    assert [e["count"] for e in lines(events_file(tmp_path))] == [1, 3]


def test_a_FAILED_write_is_retried_rather_than_remembered(plugin: Any, tmp_path: Path,
                                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """The mark moves only when the line LANDED.

    A telemetry write must never fail the run (rule 3) — and it must not swallow
    the total either: the next report gets another go.
    """
    monkeypatch.setenv("COGITATE_EVENTS_FILE", str(tmp_path / "nope" / "events.jsonl"))
    plugin.pytest_collection_modifyitems(None, None, [1, 2, 3])   # directory absent
    monkeypatch.setenv("COGITATE_EVENTS_FILE", str(events_file(tmp_path)))
    plugin.pytest_collection_modifyitems(None, None, [1, 2, 3])
    assert [e["count"] for e in lines(events_file(tmp_path))] == [3]


def test_the_hook_names_are_the_ones_pytest_knows(plugin: Any) -> None:
    """`pytest_xdist_node_collection_finished` must be DEFINED here.

    pytest REFUSES a hook whose hookspec is absent (`PluginValidationError`), so
    the plugin defines it only where xdist provides the spec — if xdist is
    installed (it is, wherever `-n auto` works), the hook has to exist, or the
    parallel total silently disappears.
    """
    assert callable(getattr(plugin, "pytest_xdist_node_collection_finished", None))
    assert callable(plugin.pytest_collection_modifyitems)
