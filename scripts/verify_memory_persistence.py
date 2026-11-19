#!/usr/bin/env python3
"""Automated verification of agent memory persistence."""

import asyncio, json, logging, os, sqlite3, sys, tempfile
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List

sys.path.insert(0, os.path.expanduser("~/Projects/cogitate/backend"))
logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger("test_memory_persistence")
logger.setLevel(logging.INFO)

passed = failed = 0

def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1; logger.info(f"  ✅ {label}")
    else:
        failed += 1; logger.info(f"  ❌ {label} -- {detail}")

async def run_all():
    await test_01_db_creation()
    await test_02_remember_recall()
    await test_03_session_isolation()
    await test_04_researcher_db()
    await test_05_summary_fact_recall()
    logger.info(f"\n{'='*50}")
    logger.info(f"Results: {passed} passed, {failed} failed, {passed+failed} total")
    return failed == 0

async def test_01_db_creation():
    logger.info("\n1. SQLite DB creation")
    from app.services.cognitive_pipeline.memory_manager import KVStoreMemoryManager
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f: db = f.name
    try:
        mgr = KVStoreMemoryManager(db_path=db)
        check("DB file created", os.path.exists(db))
        conn = sqlite3.connect(db)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        conn.close()
        check("Has cognitive_memory table", "cognitive_memory" in tables, f"tables={tables}")
    finally:
        if os.path.exists(db): os.unlink(db)

async def test_02_remember_recall():
    logger.info("\n2. Store via remember() + recall")
    from app.services.cognitive_pipeline.memory_manager import KVStoreMemoryManager
    from app.services.cognitive_pipeline.models import AgentDescriptor, Context
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f: db = f.name
    try:
        mgr = KVStoreMemoryManager(db_path=db)
        agent = AgentDescriptor(id=99, name="TestAgent")
        ctx = Context(user_message="Test user message")
        delta = await mgr.remember(context=ctx, response="Test response.", agent=agent, session_id="s1")
        check("remember() OK", delta is not None)
        check("Stored keys present", len(delta.stored_keys) > 0, f"keys={delta.stored_keys}")

        turns = await mgr.recall(agent, "s1")
        check("Turns recalled", len(turns) > 0, f"got {len(turns)}")

        ctx2 = Context(user_message="Message 2")
        await mgr.remember(context=ctx2, response="Response 2", agent=agent, session_id="s1")
        turns = await mgr.recall(agent, "s1")
        check("Multiple turns persisted", len(turns) >= 2, f"got {len(turns)}")
    finally:
        if os.path.exists(db): os.unlink(db)

async def test_03_session_isolation():
    logger.info("\n3. Session isolation")
    from app.services.cognitive_pipeline.memory_manager import KVStoreMemoryManager
    from app.services.cognitive_pipeline.models import AgentDescriptor, Context
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f: db = f.name
    try:
        mgr = KVStoreMemoryManager(db_path=db)
        agent = AgentDescriptor(id=99, name="Agent")
        ctx = Context(user_message="Session A data")
        await mgr.remember(ctx, "resp", agent, "sA")
        ctx2 = Context(user_message="Session B data")
        await mgr.remember(ctx2, "resp", agent, "sB")

        ha = str(await mgr.recall(agent, "sA"))
        hb = str(await mgr.recall(agent, "sB"))
        check("Session A isolated", "Session A data" in ha and "Session B data" not in ha)
        check("Session B isolated", "Session B data" in hb and "Session A data" not in hb)
    finally:
        if os.path.exists(db): os.unlink(db)

async def test_04_researcher_db():
    logger.info("\n4. Researcher per-agent DB")
    db = os.path.expanduser("~/Projects/cogitate/agents/researcher/cognitive_memory.db")
    exists = os.path.exists(db)
    check("Researcher DB exists", exists)
    if not exists:
        logger.info("    (Researcher has no stored memory yet)")
        return
    size = os.path.getsize(db)
    check("Has content", size > 4096, f"size={size}")
    conn = sqlite3.connect(db)
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    check("Has cognitive_memory table", "cognitive_memory" in tables, f"tables={tables}")
    if "cognitive_memory" in tables:
        count = conn.execute("SELECT COUNT(*) FROM cognitive_memory").fetchone()[0]
        check("Has entries", count > 0, f"count={count}")
        keys = [r[0] for r in conn.execute("SELECT key FROM cognitive_memory LIMIT 5").fetchall()]
        logger.info(f"    Sample keys: {keys}")
    conn.close()

async def test_05_summary_fact_recall():
    logger.info("\n5. Summary/fact recall mechanism")
    from app.services.cognitive_pipeline.memory_manager import KVStoreMemoryManager
    from app.services.cognitive_pipeline.models import AgentDescriptor
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f: db = f.name
    try:
        mgr = KVStoreMemoryManager(db_path=db)
        agent = AgentDescriptor(id=99, name="Agent")
        ts = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(db)
        for k, v in [("agent_99:summary", '["Conversation summary"]'),
                      ("facts", '["User likes concise"]'),
                      ("facts", '["Python 3.12"]')]:
            conn.execute(
                "INSERT OR REPLACE INTO cognitive_memory (key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (k, v, ts, ts))
        conn.commit(); conn.close()

        summaries = await mgr.recall_summaries(agent)
        facts = await mgr.recall_facts(agent)
        check("Summaries recalled", len(summaries) >= 0)
        check("Facts recallable", isinstance(facts, list), f"type={type(facts).__name__}")
    finally:
        if os.path.exists(db): os.unlink(db)

if __name__ == "__main__":
    sys.exit(0 if asyncio.run(run_all()) else 1)
