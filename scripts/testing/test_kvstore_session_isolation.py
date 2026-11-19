#!/usr/bin/env python3
"""Verify KVStoreMemoryManager session isolation.

Tests that session_id scoping works correctly:
- Turns stored under session A are NOT visible when recalling session B
- Turns stored under session B are NOT visible when recalling session A
- Turns stored with session_id=None are NOT visible when recalling a named session

Usage:
    cd backend && uv run python3 ../scripts/testing/test_kvstore_session_isolation.py
"""

import sys
import os
import json
import tempfile

# Ensure we can import from the project
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from app.services.cognitive_pipeline.memory_manager import KVStoreMemoryManager
from app.services.cognitive_pipeline.models import AgentDescriptor, Context


def make_context(user_message: str) -> Context:
    return Context(
        user_message=user_message,
        system_prompt="You are a test assistant.",
        agent_name="TestBot",
    )


async def test_session_isolation() -> int:
    """Run all session isolation tests. Returns exit code (0 = pass)."""
    passed = 0
    failed = 0

    def check(condition: bool, message: str):
        nonlocal passed, failed
        if condition:
            print(f"  ✅ {message}")
            passed += 1
        else:
            print(f"  ❌ {message}")
            failed += 1

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = tmp.name

    try:
        manager = KVStoreMemoryManager(db_path=db_path)
        agent = AgentDescriptor(id=1, name="TestBot", system_prompt="Assistant.")

        print(f"\nTest database: {db_path}\n")

        # ── Test 1: Store in session A, recall from session A ──
        ctx_a = make_context("Hello from session A")
        await manager.remember(context=ctx_a, response="Hi A!", agent=agent, session_id="session_a")
        turns_a = await manager.recall(agent=agent, session_id="session_a")
        check(len(turns_a) == 2, "Session A remembers its own turn")
        check(turns_a[0]["content"] == "Hello from session A", "Session A has correct user message")
        check(turns_a[1]["content"] == "Hi A!", "Session A has correct assistant response")

        # ── Test 2: Store in session B, recall from session B ──
        ctx_b = make_context("Hello from session B")
        await manager.remember(context=ctx_b, response="Hi B!", agent=agent, session_id="session_b")
        turns_b = await manager.recall(agent=agent, session_id="session_b")
        check(len(turns_b) == 2, "Session B remembers its own turn")
        check(turns_b[0]["content"] == "Hello from session B", "Session B has correct user message")

        # ── Test 3: No leakage between sessions ──
        turns_a_again = await manager.recall(agent=agent, session_id="session_a")
        check(len(turns_a_again) == 2, "Session A still has only 2 turns (not polluted by session B)")
        # Session A should NOT contain session B's message
        session_b_visible = any("Hello from session B" in t["content"] for t in turns_a_again)
        check(not session_b_visible, "Session B's content is NOT visible in session A")

        # ── Test 4: Default (no session) is isolated too ──
        ctx_default = make_context("Hello from default session")
        await manager.remember(context=ctx_default, response="Hi default!", agent=agent)
        turns_default = await manager.recall(agent=agent)
        check(len(turns_default) == 2, "Default session (None) stores independently")
        check(turns_default[0]["content"] == "Hello from default session", "Default has correct content")

        # ── Test 5: Named sessions don't see default ──
        turns_a_final = await manager.recall(agent=agent, session_id="session_a")
        default_visible_in_a = any("Hello from default" in t["content"] for t in turns_a_final)
        check(not default_visible_in_a, "Default session content is NOT visible in session A")

        # ── Test 6: Different agents are isolated ──
        agent2 = AgentDescriptor(id=2, name="OtherBot", system_prompt="Assistant.")
        ctx_other = make_context("Other agent message")
        await manager.remember(context=ctx_other, response="Hi other!", agent=agent2, session_id="session_a")
        turns_a_original = await manager.recall(agent=agent, session_id="session_a")
        other_visible = any("Other agent" in t["content"] for t in turns_a_original)
        check(not other_visible, "Different agents' session A is isolated from each other")

    finally:
        os.unlink(db_path)
        print(f"\nCleaned up: {db_path}")

    # ── Summary ──
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed}")
    print(f"{'='*50}")
    return 1 if failed else 0


if __name__ == "__main__":
    import asyncio
    sys.exit(asyncio.run(test_session_isolation()))
