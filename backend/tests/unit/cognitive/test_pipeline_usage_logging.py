"""The pipeline usage-logging tests — local-Ollama tracking."""

import sqlite3

from app.services.cognitive_pipeline.executor import log_usage
from app.services.cognitive_pipeline.models import AgentDescriptor


class _Usage:
    def __init__(self, p, c):
        self.prompt_tokens = p
        self.completion_tokens = c


class _Resp:
    def __init__(self, p, c):
        self.usage = _Usage(p, c)


def test_log_usage_writes_the_worker_row(tmp_path, monkeypatch):
    # point the app's RESOLVER at the temp DB. `log_usage` reads
    # `Paths.from_settings`; the class attribute is a dataclass FIELD DEFAULT that
    # ignores DATABASE_URL — reading it is how the suite once wrote usage rows
    # into the operator's live database.
    from app.core.config import Paths as _Paths
    # Resolved BEFORE the patch: `rooted_at` derives through `from_settings`, which
    # the next line replaces — calling it afterwards would recurse into the mock.
    sandbox = _Paths.rooted_at(tmp_path / "t.db")
    monkeypatch.setattr(_Paths, "from_settings", classmethod(lambda cls, _settings: sandbox))

    # the schema (a minimal usage_logs)
    con = sqlite3.connect(tmp_path / "t.db")
    con.execute(
        "CREATE TABLE usage_logs (id INTEGER PRIMARY KEY, session_id INTEGER,"
        " agent_id INTEGER, provider TEXT, model TEXT, prompt_tokens INTEGER,"
        " completion_tokens INTEGER, total_tokens INTEGER, cost_usd REAL,"
        " response_time_ms INTEGER, success INTEGER, error_message TEXT)"
    )
    con.commit()

    agent = AgentDescriptor(id=7, name="w", provider="ollama", model="granite4:3b")
    log_usage(agent, "ollama/granite4:3b", _Resp(100, 50), 1234, True)

    row = con.execute("SELECT * FROM usage_logs").fetchone()
    assert row is not None
    assert row[1] is None  # session_id NULL (no chat session)
    assert row[2] == 7     # agent_id = the worker
    assert row[3] == "ollama" and row[4] == "granite4:3b"
    assert row[5] == 100 and row[6] == 50 and row[7] == 150
    assert row[9] == 1234 and row[10] == 1
    con.close()


def test_log_usage_never_raises(tmp_path, monkeypatch):
    from app.core.config import Paths as _Paths
    # no such table — the INSERT fails; the logger must swallow it
    sandbox = _Paths.rooted_at(tmp_path / "missing.db")
    monkeypatch.setattr(_Paths, "from_settings", classmethod(lambda cls, _settings: sandbox))

    agent = AgentDescriptor(id=1, name="w", provider="ollama", model="granite4:3b")
    log_usage(agent, "ollama/granite4:3b", None, 0, False, "boom")  # must not raise
