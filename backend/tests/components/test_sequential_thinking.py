"""The sequential-thinking tool and its thought store — numbering and history."""

import pytest
from app.domain.tools.builtin.sequential_thinking_handler import (
    SequentialThinkingTool,
    ThoughtStore,
    clear_thought_store,
)


class TestThoughtStore:
    """Unit tests for the ThoughtStore data structure."""

    def test_add_thought_returns_incremented_number(self):
        """First thought is #1, second is #2."""
        store = ThoughtStore()
        t1 = store.add_thought("first thought")
        assert t1.number == 1
        t2 = store.add_thought("second thought")
        assert t2.number == 2

    def test_get_history_returns_all_thoughts(self):
        """get_history returns all added thoughts in order."""
        store = ThoughtStore()
        store.add_thought("thought A")
        store.add_thought("thought B")
        history = store.get_history()
        assert len(history) == 2
        assert history[0].thought == "thought A"
        assert history[1].thought == "thought B"

    def test_format_history_returns_numbered_list(self):
        """format_history produces a readable numbered chain."""
        store = ThoughtStore()
        store.add_thought("[intent: test] first step")
        store.add_thought("[intent: test] second step")
        formatted = store.format_history()
        assert "[Your reasoning chain so far:]" in formatted
        assert "1. [intent: test] first step" in formatted
        assert "2. [intent: test] second step" in formatted

    def test_format_history_empty_returns_empty_string(self):
        """Empty store returns empty string."""
        store = ThoughtStore()
        assert store.format_history() == ""

    def test_clear_removes_all_thoughts(self):
        """Clear resets the store."""
        store = ThoughtStore()
        store.add_thought("something")
        store.clear()
        assert len(store) == 0

    def test_intent_anchor_persists_across_multiple_thoughts(self):
        """Intent anchor [intent: ...] appears in each thought."""
        store = ThoughtStore()
        store.add_thought("[intent: test_intent] step one")
        store.add_thought("[intent: test_intent] step two")
        for t in store.get_history():
            assert t.thought.startswith("[intent: test_intent]")


class TestSequentialThinkingTool:
    """Tests for the SequentialThinkingTool execute method."""

    @pytest.fixture(autouse=True)
    def cleanup(self):
        """Clear thought stores between tests."""
        yield
        clear_thought_store("test_session")

    async def test_execute_records_thought(self):
        """Calling execute with a thought records and returns it."""
        tool = SequentialThinkingTool()
        result = await tool.execute(
            {},
            thought="[intent: test] my first thought",
            _session_id="test_session",
        )
        assert result["success"] is True
        assert result["thought_number"] == 1
        assert result["total_thoughts"] == 1
        assert "[intent: test] my first thought" in result["history"]

    async def test_execute_accumulates_multiple_thoughts(self):
        """Multiple execute calls accumulate sequentially."""
        tool = SequentialThinkingTool()
        await tool.execute({}, thought="[intent: test] first", _session_id="test_session")
        await tool.execute({}, thought="[intent: test] second", _session_id="test_session")
        result = await tool.execute({}, thought="[intent: test] third", _session_id="test_session")
        assert result["thought_number"] == 3
        assert result["total_thoughts"] == 3

    async def test_empty_thought_returns_error(self):
        """Empty thought text returns a validation error."""
        tool = SequentialThinkingTool()
        result = await tool.execute({}, thought="", _session_id="test_session")
        assert result["success"] is False
        assert result["error_type"] == "ValidationError"

    async def test_blank_thought_returns_error(self):
        """Whitespace-only thought returns a validation error."""
        tool = SequentialThinkingTool()
        result = await tool.execute({}, thought="   ", _session_id="test_session")
        assert result["success"] is False

    async def test_next_thought_needed_defaults_to_true(self):
        """Default next_thought_needed is True."""
        tool = SequentialThinkingTool()
        result = await tool.execute({}, thought="thinking...", _session_id="test_session")
        assert result["next_thought_needed"] is True

    async def test_next_thought_needed_can_be_false(self):
        """Can signal reasoning is complete."""
        tool = SequentialThinkingTool()
        result = await tool.execute(
            {},
            thought="done thinking",
            next_thought_needed=False,
            _session_id="test_session",
        )
        assert result["next_thought_needed"] is False

    async def test_session_isolation(self):
        """Two sessions do not share thought stores."""
        tool = SequentialThinkingTool()
        await tool.execute({}, thought="session A thought", _session_id="session_a")
        await tool.execute({}, thought="session B thought", _session_id="session_b")
        result_a = await tool.execute({}, thought="another A", _session_id="session_a")
        result_b = await tool.execute({}, thought="another B", _session_id="session_b")
        assert result_a["total_thoughts"] == 2  # session_a has 2
        assert result_b["total_thoughts"] == 2  # session_b has 2

    async def test_default_session_id(self):
        """Missing _session_id falls back to 'default'."""
        tool = SequentialThinkingTool()
        result = await tool.execute({}, thought="no session id")
        assert result["success"] is True
        assert result["thought_number"] == 1


class TestThoughtStoreInjection:
    """Test the thought history injection format (used in stream_service.py)."""

    def test_injection_format_after_tool_result(self):
        """Simulate the injection that stream_service.py performs."""
        store = ThoughtStore()
        store.add_thought("[intent: test_inject] first step")
        store.add_thought("[intent: test_inject] second step")

        # This is what stream_engine.py does:
        thought_history = store.format_history()
        injected_message = {
            "role": "system",
            "content": thought_history,
        }

        assert injected_message["role"] == "system"
        assert "1. [intent: test_inject] first step" in injected_message["content"]
        assert "2. [intent: test_inject] second step" in injected_message["content"]

    def test_injection_empty_store(self):
        """Empty store should not inject anything."""
        store = ThoughtStore()
        assert store.format_history() == ""
        # stream_service should skip injection if format_history returns empty
