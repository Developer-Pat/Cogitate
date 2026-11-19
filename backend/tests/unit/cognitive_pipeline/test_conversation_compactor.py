"""Conversation compaction — the trigger threshold and the token counting."""

import pytest
from app.services.cognitive_pipeline.conversation_compactor import (
    count_message_tokens,
    should_compact,
    _split_messages,
    compact_messages,
)


class TestCountTokens:
    """Token counting."""

    def test_empty_messages(self):
        assert count_message_tokens([]) == 0

    def test_simple_message(self):
        msgs = [{"role": "user", "content": "Hello world"}]
        count = count_message_tokens(msgs)
        assert count > 0
        assert isinstance(count, int)

    def test_multiple_messages(self):
        msgs = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
        ]
        count = count_message_tokens(msgs)
        assert count > 5


class TestShouldCompact:
    """Compaction decision logic."""

    def test_below_threshold(self):
        msgs = [{"role": "user", "content": "Hi"}]
        needs, count = should_compact(msgs, max_tokens=10000)
        assert needs is False

    def test_above_threshold(self):
        msgs = [{"role": "user", "content": "x" * 50000}]
        needs, count = should_compact(msgs, max_tokens=1000)
        assert needs is True

    def test_custom_threshold(self):
        msgs = [{"role": "user", "content": "Hello" * 100}]
        needs, count = should_compact(msgs, max_tokens=1)
        assert needs is True


class TestSplitMessages:
    """Message splitting logic."""

    def test_preserves_system_prompt(self):
        msgs = [
            {"role": "system", "content": "You are a bot."},
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
            {"role": "assistant", "content": "D"},
            {"role": "user", "content": "E"},
        ]
        old, recent = _split_messages(msgs, keep_last=2)
        assert len(old) > 0
        assert old[0]["role"] == "system"
        assert len(recent) == 2

    def test_below_keep_threshold(self):
        msgs = [{"role": "user", "content": "A"}, {"role": "assistant", "content": "B"}]
        old, recent = _split_messages(msgs, keep_last=4)
        assert len(old) == 0
        assert len(recent) == 2

    def test_system_prompt_in_old(self):
        msgs = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "A"},
            {"role": "assistant", "content": "B"},
            {"role": "user", "content": "C"},
            {"role": "assistant", "content": "D"},
            {"role": "user", "content": "E"},
        ]
        old, recent = _split_messages(msgs, keep_last=2)
        # System prompt stays in old for preservation during compaction
        assert any(m.get("role") == "system" for m in old)
        assert len(recent) == 2


@pytest.mark.asyncio
async def test_compact_below_threshold():
    """Messages under threshold are returned unchanged."""
    msgs = [{"role": "user", "content": "Hello"}]
    result = await compact_messages(msgs, max_tokens=100000)
    assert result == msgs


@pytest.mark.asyncio
async def test_compact_empty_messages():
    """Empty messages return empty."""
    result = await compact_messages([], max_tokens=1000)
    assert result == []


def _a_long_conversation() -> list[dict]:
    """Enough body messages for `_split_messages` to have something to compact."""
    return [{"role": "system", "content": "You are a bot."}] + [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i} " + "x" * 40}
        for i in range(8)
    ]


class TestTheChainIsWhatAnswers:
    """The summarizer's service comes from the `summary` capability's RESOLVED chain.

    These pin the phase-8 change. The module used to carry `summarization_model="llama3.2"` and
    `summarization_provider="ollama"` as DEFAULTS — a service written in code, aimed at a local engine
    that need not be running — which is why the `summary` capability had no consumer at all.
    """

    @pytest.mark.asyncio
    async def test_the_primary_answers_when_it_can(self, monkeypatch):
        from app.domain.providers.capabilities import ServiceCandidate
        from app.services.cognitive_pipeline import conversation_compactor as mod

        tried: list[str] = []

        async def fake(candidate: ServiceCandidate, prompt: str) -> str:
            tried.append(candidate.describe())
            return "THE PRIMARY SUMMARY"

        monkeypatch.setattr(mod, "_summarize_with", fake)

        result = await mod.compact_messages(
            _a_long_conversation(),
            max_tokens=10,
            candidates=(
                ServiceCandidate(ordinal=0, provider="deepseek", model="deepseek-v4-flash"),
                ServiceCandidate(ordinal=1, provider="llama", model="Bonsai-27B-Q1_0.gguf"),
            ),
        )

        # the primary only — a chain is not a fan-out
        assert tried == ["deepseek/deepseek-v4-flash"]
        assert any("THE PRIMARY SUMMARY" in m.get("content", "") for m in result)

    @pytest.mark.asyncio
    async def test_a_lost_primary_falls_to_the_backup(self, monkeypatch):
        from app.domain.providers.capabilities import ServiceCandidate
        from app.services.cognitive_pipeline import conversation_compactor as mod

        tried: list[str] = []

        async def fake(candidate: ServiceCandidate, prompt: str) -> str:
            tried.append(candidate.describe())
            if candidate.provider == "deepseek":
                raise RuntimeError("connection refused")
            return "THE BACKUP SUMMARY"

        monkeypatch.setattr(mod, "_summarize_with", fake)

        result = await mod.compact_messages(
            _a_long_conversation(),
            max_tokens=10,
            candidates=(
                ServiceCandidate(ordinal=0, provider="deepseek", model="deepseek-v4-flash"),
                ServiceCandidate(ordinal=1, provider="llama", model="Bonsai-27B-Q1_0.gguf"),
            ),
        )

        # tried IN ORDER, and the backup is what answered
        assert tried == ["deepseek/deepseek-v4-flash", "llama/Bonsai-27B-Q1_0.gguf"]
        assert any("THE BACKUP SUMMARY" in m.get("content", "") for m in result)

    @pytest.mark.asyncio
    async def test_an_empty_chain_calls_nothing_and_never_invents_a_service(self, monkeypatch):
        """No candidates = no call at all. The old default was `ollama/llama3.2`; there is none now."""
        from app.services.cognitive_pipeline import conversation_compactor as mod

        called: list[str] = []

        async def fake(candidate, prompt: str) -> str:
            called.append(candidate.describe())
            return "SHOULD NEVER BE USED"

        monkeypatch.setattr(mod, "_summarize_with", fake)

        result = await mod.compact_messages(_a_long_conversation(), max_tokens=10, candidates=())

        assert called == []
        # the last resort still compacts, so the caller is not left with an over-long context
        assert any("[truncated]" in m.get("content", "") for m in result)
