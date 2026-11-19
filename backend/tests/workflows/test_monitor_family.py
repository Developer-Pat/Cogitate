"""Tests for the monitor workflow family (RSS digest + market watch).

The monitor family is the system's first REAL user-facing
workflows — the tests verify:
- RSS: fetch → dedup (state file) → summarize → deliver
- Market: fetch → threshold/trend → deliver
- Dedup survives across invocations (state file, not thread-bound)
"""

import sys
from pathlib import Path

import json

import pytest

ROOT = Path(__file__).resolve().parents[4]  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root
sys.path.insert(0, str(ROOT / "backend"))

from app.workflows.nodes import monitor_nodes as mn

# THE QUARANTINE IS LIFTED (2026-09-25). This file was parked as "the ordering-flake
# (the known issue)" — the same family as the suite's cross-group interference, which
# turned out to be a POISONED SETTINGS CACHE: `test_provisioning.py` pointed
# `DATABASE_URL` at a throwaway database and left the `lru_cache`d settings object
# naming it, so every later test in that xdist worker resolved the shared DB from a
# database without the migration-only tables. With that fixed the file
# passes alone (18) and in the group runs. Parking a test hides it from EVERY group —
# the suite's job is to be a signal, so it comes back in.



@pytest.fixture(autouse=True)
def _isolated_state(monkeypatch, tmp_path):
    """Point the monitor state file at a tmp dir for each test."""
    monkeypatch.setattr(mn, "_digest_dir", lambda: tmp_path)
    yield


class TestRssFetchNode:
    def test_fetch_parses_rss_xml(self):
        """XML RSS feeds parse into items with stable ids (URLs)."""
        xml = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>T</title>
<item><title>First</title><link>https://a.com/1</link></item>
<item><title>Second</title><link>https://a.com/2</link></item>
<item><title>First dup</title><link>https://a.com/1</link></item>
</channel></rss>"""
        items = mn._parse_markdown_items(xml, "https://feed.example/rss", 5)
        assert len(items) == 2  # dedup by URL
        assert items[0]["title"] == "First"
        assert items[0]["id"] == "https://a.com/1"

    def test_fetch_marks_new_vs_seen(self):
        """Items already in state are excluded (new_items), state updates."""
        state = {
            "inputs": {"feeds": ["https://feed.example/rss"], "max_items": 5},
        }
        # prime state with the first item id
        mn._save_state({"last_seen": {"https://feed.example/rss": ["https://a.com/1"]}})
        xml = """<rss><channel>
        <item><title>A</title><link>https://a.com/1</link></item>
        <item><title>B</title><link>https://a.com/2</link></item>
        </channel></rss>"""
        mn._fetch_url = lambda url, timeout=20: xml  # type: ignore[assignment]

        out = mn.rss_fetch_node(state)
        assert [it["title"] for it in out["new_items"]] == ["B"]  # A deduped
        assert len(out["last_seen"]["https://feed.example/rss"]) == 2

    def test_fetch_error_never_fails_workflow(self):
        """A dead feed records an error but the workflow continues."""
        state = {"inputs": {"feeds": ["https://dead.example/rss"], "max_items": 3}}
        mn._fetch_url = lambda url, timeout=20: (_ for _ in ()).throw(  # type: ignore[assignment]
            Exception("connection refused")
        )
        out = mn.rss_fetch_node(state)
        assert out["new_items"] == []
        assert any("dead.example" in e for e in out["errors"])


class TestMonitorReset:
    """The user-facing checkpoint reset (2026-08-18): clearing the
    last_seen state makes the next run a FULL run."""

    def test_reset_clears_only_the_named_feeds(self, monkeypatch, tmp_path):
        # isolate the state file into tmp_path
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps({
            "last_seen": {
                "https://arstechnica.com/feed/": ["a1"],
                "https://hnrss.org/frontpage": ["h1"],
                "https://coingecko.com/": ["p1"],  # the other monitor's feed
            }
        }), encoding="utf-8")
        monkeypatch.setattr(
            "app.workflows.nodes.monitor_nodes._state_file",
            lambda: state_file,
        )

        from app.workflows.api.workflow_router import reset_monitor_checkpoint
        # the endpoint resolves the template's feeds from the DB — the
        # rss-monitor config has arstechnica + hnrss
        import asyncio
        out = asyncio.get_event_loop().run_until_complete(
            reset_monitor_checkpoint({"template_id": "rss-monitor"})
        )
        assert out["cleared_count"] == 2
        assert "https://coingecko.com/" not in out["cleared_feeds"]  # market's feed survives

        state = json.loads(state_file.read_text(encoding="utf-8"))
        remaining = list(state["last_seen"].keys())
        assert remaining == ["https://coingecko.com/"]

    def test_reset_rejects_non_monitor(self, monkeypatch, tmp_path):
        from app.workflows.api.workflow_router import reset_monitor_checkpoint
        import asyncio
        from fastapi import HTTPException
        try:
            asyncio.get_event_loop().run_until_complete(
                reset_monitor_checkpoint({"template_id": "agent-task"})
            )
            assert False, "should raise"
        except HTTPException as e:
            assert e.status_code == 400


class TestRssSummarizeAndDeliver:
    def test_no_items_yields_no_new_message(self):
        out = mn.rss_summarize_node({"new_items": []})
        assert out["report_text"] == "No new items this cycle."

    def test_format_builds_linked_list(self):
        # the 2026-08-18 add: the format node GUARANTEES the links
        # (the LLM summary path dropped them)
        out = mn.rss_format_node({
            "new_items": [
                {"title": "T1", "url": "https://a.com/1", "source": "https://feed/"},
                {"title": "T2", "url": "https://a.com/2", "source": "https://feed/"},
            ],
            "report_text": "• a summary bullet",
        })
        body = out["report_text"]
        assert "## At a glance" in body
        assert "## New items" in body
        assert "[T1](https://a.com/1)" in body
        assert "[T2](https://a.com/2)" in body

    def test_format_no_items_no_summary(self):
        out = mn.rss_format_node({"new_items": [], "report_text": ""})
        assert out["report_text"] == "No new items this cycle."

    def test_format_items_without_summary_still_linked(self):
        # no LLM summary (fallback path) — the links must still be there
        out = mn.rss_format_node({
            "new_items": [
                {"title": "T1", "url": "https://a.com/1", "source": "s"},
            ],
            "report_text": "",
        })
        assert "[T1](https://a.com/1)" in out["report_text"]
        assert "## At a glance" not in out["report_text"]

    def test_deliver_writes_digest_file(self, monkeypatch, tmp_path):
        # ISOLATE from the live store (data/monitor/) — a real write
        # pollutes products.json/toasts.json on every suite run.
        monkeypatch.setattr(
            "app.workflows.distribution.distributors._products_dir",
            lambda: tmp_path,
        )
        state = {
            "new_items": [{"title": "T", "url": "https://a.com/1", "source": "s"}],
            "report_text": "## Digest",
        }
        out = mn.rss_deliver_node(state)
        path = Path(out["digest_path"])
        assert path.exists()
        assert "## Digest" in path.read_text(encoding="utf-8")


class TestMarketWatch:
    def test_fetch_records_price(self):
        mn._fetch_url = lambda url, timeout=15: '{"bitcoin": {"usd": 65000}}'  # type: ignore[assignment]
        out = mn.market_fetch_node({"inputs": {"symbol": "bitcoin"}})
        assert out["last_price"] == 65000.0
        assert "bitcoin" in out["report_text"]

    def test_threshold_alert_on_move(self):
        mn._fetch_url = lambda url, timeout=15: '{"bitcoin": {"usd": 66300}}'  # type: ignore[assignment]
        out = mn.market_fetch_node(
            {"inputs": {"symbol": "bitcoin", "threshold_pct": 2.0}, "last_price": 65000.0}
        )
        assert "▲" in out["report_text"] or "▼" in out["report_text"]
        assert "2.00%" in out["report_text"]

    def test_within_threshold_no_alert(self):
        mn._fetch_url = lambda url, timeout=15: '{"bitcoin": {"usd": 65100}}'  # type: ignore[assignment]
        out = mn.market_fetch_node(
            {"inputs": {"symbol": "bitcoin", "threshold_pct": 2.0}, "last_price": 65000.0}
        )
        assert "within threshold" in out["report_text"]

    def test_fetch_error_records_error(self):
        mn._fetch_url = lambda url, timeout=15: (_ for _ in ()).throw(  # type: ignore[assignment]
            Exception("rate limited")
        )
        out = mn.market_fetch_node({"inputs": {"symbol": "bitcoin"}})
        assert out["last_price"] == 0.0
        assert any("market fetch" in e for e in out["errors"])


class TestReadinessCheck:
    def test_probe_runs_post_and_reports(self, tmp_path, monkeypatch):
        """The probe runs the POST suite + provider/env checks and
        produces a report (errors never fail it)."""
        # Isolate digest dir
        monkeypatch.setattr(mn, "_digest_dir", lambda: tmp_path)

        # Fake the POST suite + DB to keep the test hermetic
        class FakePost:
            async def execute(self, config, checks="all", **kw):
                return {
                    "checks": [
                        {"name": "llm", "status": "pass", "detail": "ok"},
                        {"name": "database", "status": "fail", "detail": "locked"},
                    ],
                    "overall": "warn",
                }

        monkeypatch.setattr("app.domain.tools.builtin.run_post.RunPostTool", FakePost)

        # Fake the main DB (no real cogitate.db in unit tests)
        import sqlite3 as _sqlite3

        class FakeConn:
            def execute(self, q):
                class Cur:
                    def fetchall(self):
                        return [("openrouter", "openrouter", 1), ("ollama", "ollama", 1)]

                    def fetchone(self):
                        return (2,)

                return Cur()

            def close(self):
                pass

        monkeypatch.setattr(
            "app.workflows.nodes.monitor_nodes._main_db",
            lambda: FakeConn(),
        )

        out = mn.readiness_probe_node({})
        assert "Readiness Report" in out["report_text"]
        assert "1 passed / 1 failed" in out["report_text"]
        assert "FAIL database" in out["report_text"]

    def test_readiness_deliver_writes_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mn, "_digest_dir", lambda: tmp_path)
        # isolate from the live store (data/monitor/) — same pollution
        # guard as the rss deliver test
        monkeypatch.setattr(
            "app.workflows.distribution.distributors._products_dir",
            lambda: tmp_path,
        )
        out = mn.readiness_deliver_node({"report_text": "## Ready"})
        path = Path(out["digest_path"])
        assert path.exists()
        assert "## Ready" in path.read_text(encoding="utf-8")


class TestLlmSummarize:
    """The _llm_summarize path — regression for the 2026-08-10 bug.

    _llm_summarize called handler.execute() on a plain function
    (AttributeError → silent fallback); then the arg was 'text' not
    'content'. The digest ALWAYS used the plain-text fallback until
    live verification caught it. These tests pin the invocation.
    """

    def test_summarize_uses_registry_handler(self, monkeypatch):
        """_llm_summarize must call the registry handler as a callable."""
        from app.workflows.nodes import monitor_nodes

        calls: list[dict] = []

        async def fake_handler(config: dict, **kwargs):
            calls.append({"config": config, **kwargs})
            return {"success": True, "summary": "• Fake summary line."}

        fake_registry = type("_R", (), {"get_handler": lambda self, slug: fake_handler})()
        monkeypatch.setattr("app.domain.tools.registry.init_default_registry", lambda: fake_registry)

        items = [{"title": "Headline", "url": "https://example.com"}]
        result = monitor_nodes._llm_summarize(items)

        assert result == "• Fake summary line."
        assert len(calls) == 1
        call = calls[0]
        # the content kwarg is the joined headlines (the handler contract)
        assert "Headline" in call["content"]
        assert "style" in call
        assert call["config"]["model"].startswith("ollama/")

    def test_summarize_falls_back_cleanly_on_error(self, monkeypatch):
        """A failed summarize must return None (digest falls back)."""
        from app.workflows.nodes import monitor_nodes

        async def broken_handler(config: dict, **kwargs):
            raise RuntimeError("ollama down")

        fake_registry = type("_R", (), {"get_handler": lambda self, slug: broken_handler})()
        monkeypatch.setattr("app.domain.tools.registry.init_default_registry", lambda: fake_registry)

        result = monitor_nodes._llm_summarize([{"title": "H", "url": "https://e.com"}])
        assert result is None


class TestTheSeededConfig:
    """The seam, 2026-10-13: a run's config must not depend on which door it came through.

    A run's initial state is built TWICE — the API's `POST /execute` and the scheduler's trigger
    path. The API loaded the template's config and seeded it on `state.config`; the scheduler
    seeded `"config": None`. The monitor family reads its FEEDS out of that channel, so every
    SCHEDULED run resolved zero feeds, fetched nothing, and reported a clean cycle
    (`Items: 0 · Errors: 0`) — for weeks, because a monitor's failures are declared *tolerant* and
    never mark a run. Two of these tests fail on the pre-fix code: the node crashed
    (`None.get` → AttributeError) and the empty list was silent.
    """

    def test_the_scheduler_seeds_the_template_config_and_not_none(self):
        from app.workflows.triggers.scheduler import _build_trigger_state

        config = {"feeds": ["https://a.example/rss"], "max_items": 3}
        state = _build_trigger_state("wf-1", "rss-monitor", "monitor-rss-hourly", config)

        assert state["config"] == config, "the channel the monitors read must carry the template"
        assert state["config"] is not config, "copied, never aliased: the graph mutates state"

    def test_the_scheduler_with_no_template_config_seeds_an_empty_mapping(self):
        """An unreadable template is empty, never None — the type the nodes dereference."""
        from app.workflows.triggers.scheduler import _build_trigger_state

        state = _build_trigger_state("wf-2", "rss-monitor", "t", None)
        assert state["config"] == {}
        assert state["inputs"] == {"trigger_id": "t"}

    def test_a_config_less_run_does_not_crash(self):
        """THE OLD SCHEDULER SHAPE, exactly: `config: None` used to raise AttributeError here."""
        out = mn.rss_fetch_node(
            {
                "workflow_id": "wf-old",
                "template_id": "rss-monitor",
                "inputs": {"trigger_id": "monitor-rss-hourly"},
                "config": None,
                "errors": [],
            }
        )
        assert out["new_items"] == []
        assert out["errors"], "and it must not stay quiet either (see the next test)"

    def test_a_run_with_no_feeds_says_so_instead_of_reporting_a_clean_cycle(self):
        out = mn.rss_fetch_node({"inputs": {"trigger_id": "t"}, "config": None})
        assert out["new_items"] == []
        assert any("no feeds resolved" in e for e in out["errors"])
        assert any("state.config.feeds" in e for e in out["errors"]), (
            "the message names the channels it checked — a reader has to know where to look"
        )

    def test_the_four_channels_that_can_carry_feeds_all_work(self):
        """metadata.config (the API's channel), state.feeds, inputs.feeds and state.config."""
        xml = '<rss><channel><item><title>A</title><link>https://a.com/1</link></item></channel></rss>'
        mn._fetch_url = lambda url, timeout=20: xml  # type: ignore[assignment]
        feed = ["https://feed.example/rss"]

        class Meta:
            def __init__(self, config):
                self.config = config

        for state in (
            {"metadata": Meta({"feeds": feed}), "inputs": {}},
            {"feeds": feed, "inputs": {}},
            {"inputs": {"feeds": feed}},
            {"config": {"feeds": feed}, "inputs": {}},
        ):
            # each channel is a separate run: clear the dedupe state so a previous case's item
            # is not mistaken for a dedupe miss
            mn._save_state({"last_seen": {}})
            out = mn.rss_fetch_node(dict(state))
            assert len(out["new_items"]) == 1, f"did not resolve from {sorted(state)}"
            assert not out["errors"]

    def test_no_new_items_is_not_claimed_when_the_run_failed(self):
        """"No new items this cycle." is a claim; with errors on the state it is a false one."""
        quiet = mn.rss_format_node({"new_items": [], "report_text": "No new items this cycle."})
        assert quiet["report_text"] == "No new items this cycle."

        failed = mn.rss_format_node(
            {
                "new_items": [],
                "report_text": "No new items this cycle.",
                "errors": ["no feeds resolved for this run"],
            }
        )
        assert "No new items" not in failed["report_text"]
        assert "Nothing gathered" in failed["report_text"]

    def test_load_template_config_reads_a_row_and_never_raises(self, tmp_path):
        """One reader, both doors: the helper itself, against a database of its own."""
        import sqlite3

        from app.workflows.template_config import load_template_config

        db = tmp_path / "shared.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE workflow_templates (id TEXT, config TEXT, tags TEXT)")
        conn.execute(
            "INSERT INTO workflow_templates VALUES (?, ?, ?)",
            ("rss-monitor", json.dumps({"feeds": ["https://a.example/rss"], "max_items": 5}), json.dumps(["monitor"])),
        )
        conn.commit()
        conn.close()

        config, tags = load_template_config("rss-monitor", db_path=db)
        assert config == {"feeds": ["https://a.example/rss"], "max_items": 5}
        assert tags == ["monitor"]

        # a missing row, a missing file and unreadable JSON are all ({}, []) — never an exception
        assert load_template_config("nope", db_path=db) == ({}, [])
        assert load_template_config("rss-monitor", db_path=tmp_path / "absent.db") == ({}, [])
