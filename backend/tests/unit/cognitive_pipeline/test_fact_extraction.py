"""Tests for fact extraction (extract_facts → cognitive_memory).

Regression: the base-class extract_facts had an undefined facts_key
(NameError swallowed by the bare except) so facts were never stored.
KVStoreMemoryManager overrides the path; this test verifies the full
extract→store→recall cycle with a mocked LLM.

Run standalone:  uv run pytest tests/unit/cognitive_pipeline/test_fact_extraction.py -v
"""

import asyncio
import json
import logging
import os
import sqlite3
import tempfile
from types import SimpleNamespace

import pytest
import pytest_asyncio

from app.services.cognitive_pipeline.memory_manager import KVStoreMemoryManager
from app.services.cognitive_pipeline.models import AgentDescriptor


def _chain() -> tuple:
    """The `memory` capability's resolved chain as the resolver hands it over — primary first.

    A chain is what the manager is GIVEN now: it used to name `ollama`/`llama3.2` in its own
    constructor, which is why the `memory` capability had no consumer at all (phase-8's audit).
    """
    from app.domain.providers.capabilities import ServiceCandidate

    return (
        ServiceCandidate(ordinal=0, provider="deepseek", model="deepseek-v4-flash"),
        ServiceCandidate(ordinal=1, provider="llama", model="Bonsai-27B-Q1_0.gguf"),
    )


@pytest.fixture
def temp_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def agent():
    return AgentDescriptor(id=99, name="TestAgent")


@pytest_asyncio.fixture
async def manager(temp_db):
    mgr = KVStoreMemoryManager(db_path=temp_db)
    yield mgr


class TestFactExtraction:
    """extract_facts stores extracted facts retrievable via recall_facts."""

    @pytest.mark.asyncio
    async def test_extract_facts_stores_and_recalls(self, manager, agent, monkeypatch):
        """Mocked LLM returns facts; they persist under agent_99:facts."""
        async def fake_acompletion(**kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content=json.dumps(["User likes concise answers.", "User writes Python."])
                ))]
            )
        monkeypatch.setattr("litellm.acompletion", fake_acompletion)

        turns = [
            {"role": "user", "content": "I prefer short answers."},
            {"role": "assistant", "content": "Got it."},
        ]
        await manager.extract_facts(agent, turns, candidates=_chain())

        # Stored in DB under the canonical key
        conn = sqlite3.connect(manager._db_path)
        row = conn.execute(
            "SELECT value FROM cognitive_memory WHERE key = ?", ("agent_99:facts",)
        ).fetchone()
        conn.close()
        assert row is not None, "facts row should exist after extract_facts"
        facts = json.loads(row[0])
        assert "User likes concise answers." in facts

        # recall_facts round-trips
        recalled = await manager.recall_facts(agent)
        assert recalled == facts

    @pytest.mark.asyncio
    async def test_extract_facts_merges_existing(self, manager, agent, monkeypatch):
        """New facts merge with existing (dedup, preserve order)."""
        # Seed existing facts
        ts = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        conn = sqlite3.connect(manager._db_path)
        conn.execute(
            "INSERT OR REPLACE INTO cognitive_memory (key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ("agent_99:facts", json.dumps(["Existing fact"]), ts, ts),
        )
        conn.commit()
        conn.close()

        async def fake_acompletion(**kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(
                    content=json.dumps(["Existing fact", "New fact"])
                ))]
            )
        monkeypatch.setattr("litellm.acompletion", fake_acompletion)

        await manager.extract_facts(agent, [{"role": "user", "content": "hi"}], candidates=_chain())

        conn = sqlite3.connect(manager._db_path)
        row = conn.execute(
            "SELECT value FROM cognitive_memory WHERE key = ?", ("agent_99:facts",)
        ).fetchone()
        conn.close()
        facts = json.loads(row[0])
        assert "Existing fact" in facts
        assert "New fact" in facts
        assert len(facts) == 2, f"expected deduped merge, got {facts}"


class TestTheMemoryChainIsWhatAnswers:
    """The extraction's service comes from the `memory` capability's RESOLVED chain.

    These pin the phase-8 change. `KVStoreMemoryManager` used to carry
    `summarization_model="llama3.2"` / `summarization_provider="ollama"` and call that pair directly —
    a service written in code, aimed at a local engine that need not be running, which is why the
    `memory` capability had **no consumer at all**.
    """

    @pytest.mark.asyncio
    async def test_the_primary_answers_when_it_can(self, manager, agent, monkeypatch):
        from app.services.cognitive_pipeline import memory_manager as mod

        tried: list[str] = []

        async def fake(candidate, messages, max_tokens):
            tried.append(candidate.describe())
            return json.dumps(["User writes Python."])

        monkeypatch.setattr(mod, "_ask_service", fake)

        await manager.extract_facts(agent, [{"role": "user", "content": "hi"}], candidates=_chain())

        # the primary only — a chain is not a fan-out
        assert tried == ["deepseek/deepseek-v4-flash"]
        assert await manager.recall_facts(agent) == ["User writes Python."]

    @pytest.mark.asyncio
    async def test_a_lost_primary_falls_to_the_backup_in_order(self, manager, agent, monkeypatch):
        from app.services.cognitive_pipeline import memory_manager as mod

        tried: list[str] = []

        async def fake(candidate, messages, max_tokens):
            tried.append(candidate.describe())
            if candidate.provider == "deepseek":
                raise RuntimeError("connection refused")
            return json.dumps(["User prefers concise answers."])

        monkeypatch.setattr(mod, "_ask_service", fake)

        await manager.extract_facts(agent, [{"role": "user", "content": "hi"}], candidates=_chain())

        # tried IN ORDER, and the backup is what answered
        assert tried == ["deepseek/deepseek-v4-flash", "llama/Bonsai-27B-Q1_0.gguf"]
        assert await manager.recall_facts(agent) == ["User prefers concise answers."]

    @pytest.mark.asyncio
    async def test_an_empty_chain_calls_nothing_and_skips(self, manager, agent, monkeypatch, caplog):
        """No candidates = no call, and NOTHING is stored. There is no `ollama` default to fall to."""
        from app.services.cognitive_pipeline import memory_manager as mod

        called: list[str] = []

        async def fake(candidate, messages, max_tokens):
            called.append(candidate.describe())
            return json.dumps(["SHOULD NEVER BE STORED"])

        monkeypatch.setattr(mod, "_ask_service", fake)

        with caplog.at_level(logging.WARNING, logger=mod.__name__):
            await manager.extract_facts(agent, [{"role": "user", "content": "hi"}], candidates=())

        assert called == []
        assert await manager.recall_facts(agent) == []
        # the SKIP is said out loud — this is the assertion that fails if the skip is removed and the
        # empty chain is handed to the walk (which raises rather than logging the reason)
        assert any("resolved no service" in r.getMessage() for r in caplog.records)


class TestTheTurnSummaryComesFromTheChainToo:
    """`remember`'s summarization reads the SAME carried chain — off the turn's `Context`."""

    async def _remember_with(self, manager, agent, chain):
        from app.services.cognitive_pipeline.models import Context

        manager._summarization_enabled = True
        manager.summarization_threshold = 1
        context = Context(user_message="Hello", agent_name=agent.name)
        context.capability_chains = {"memory": chain}
        return await manager.remember(
            context=context,
            response="Hi there!",
            agent=agent,
            session_id="s1",
        )

    @pytest.mark.asyncio
    async def test_the_service_the_chain_names_produces_the_summary(self, manager, agent, monkeypatch):
        from app.services.cognitive_pipeline import memory_manager as mod

        asked: list[str] = []

        async def fake(candidate, messages, max_tokens):
            asked.append(candidate.describe())
            return "SUMMARY VIA THE CHAIN"

        monkeypatch.setattr(mod, "_ask_service", fake)

        delta = await self._remember_with(manager, agent, _chain())

        assert asked[0] == "deepseek/deepseek-v4-flash"
        assert delta.summary == "SUMMARY VIA THE CHAIN"
        assert await manager.recall_summaries(agent) == ["SUMMARY VIA THE CHAIN"]

    @pytest.mark.asyncio
    async def test_no_chain_calls_nothing_and_stores_the_turn_count(self, manager, agent, monkeypatch, caplog):
        """The last resort asks NO service — it is the turn count, not a name moved into config."""
        from app.services.cognitive_pipeline import memory_manager as mod

        called: list[str] = []

        async def fake(candidate, messages, max_tokens):
            called.append(candidate.describe())
            return "SHOULD NEVER BE USED"

        monkeypatch.setattr(mod, "_ask_service", fake)

        with caplog.at_level(logging.WARNING, logger=mod.__name__):
            delta = await self._remember_with(manager, agent, ())

        assert called == []
        assert delta.summary == "Conversation reached 1 turns"
        assert any("resolved no service" in r.getMessage() for r in caplog.records)
