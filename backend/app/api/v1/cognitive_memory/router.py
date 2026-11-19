"""REST endpoints for cognitive memory management.

Provides clear/reset operations for KVStoreMemoryManager.
"""
import json
import logging
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.cognitive_pipeline.memory_manager import KVStoreMemoryManager
from app.services.cognitive_pipeline.models import AgentDescriptor

logger = logging.getLogger(__name__)
memory_router = APIRouter(prefix="/cognitive/memory", tags=["cognitive-memory"])


class PruneRequest(BaseModel):
    max_days: int = 30


class MemoryStatusResponse(BaseModel):
    agent_folder: str
    has_cognitive_memory_db: bool
    session_count: int
    turn_count: int
    has_summaries: bool
    summary_count: int
    fact_count: int
    has_vector_index: bool
    vector_turn_count: int


class ClearSessionRequest(BaseModel):
    agent_id: int
    session_id: str


class ClearAgentRequest(BaseModel):
    agent_id: int


def _get_manager() -> KVStoreMemoryManager:
    """Get the default KVStoreMemoryManager instance."""
    return KVStoreMemoryManager()


@memory_router.delete("/session/{agent_id}/{session_id}")
async def clear_session(agent_id: int, session_id: str):
    """Clear memory for a single agent session."""
    manager = _get_manager()
    agent = AgentDescriptor(id=agent_id, name="", system_prompt="")
    await manager.clear_session(agent, session_id)
    return {"message": f"Session {session_id} cleared for agent {agent_id}"}


@memory_router.delete("/agent/{agent_id}")
async def clear_agent(agent_id: int):
    """Clear ALL memory for an agent (all sessions).

    Also clears per-agent cognitive_memory.db if it exists
    (for deep agents like Researcher).
    """
    # 1. Clear shared memory
    manager = _get_manager()
    agent = AgentDescriptor(id=agent_id, name="", system_prompt="")
    await manager.clear_agent(agent)

    # 2. Also clear per-agent DB if it exists
    import os as _os

    from app.core.config import Paths, get_settings
    per_agent_dbs = [
        str(Paths.from_settings(get_settings()).agents_dir / "researcher" / "cognitive_memory.db"),
    ]
    for db_path in per_agent_dbs:
        if _os.path.exists(db_path):
            import sqlite3 as _sqlite3
            try:
                conn = _sqlite3.connect(db_path)
                conn.execute("DELETE FROM cognitive_memory")
                conn.commit()
                conn.close()
                logger.info("Cleared per-agent DB %s", db_path)
            except Exception as e:
                logger.error("Failed to clear per-agent DB %s: %s", db_path, e)

    return {"message": f"All memory cleared for agent {agent_id}"}


@memory_router.delete("/all")
async def clear_all():
    """Clear ALL memory for all agents."""
    manager = _get_manager()
    await manager.clear_all()
    return {"message": "All cognitive memory cleared"}


@memory_router.post("/prune")
async def prune_memory(req: PruneRequest):
    """Delete entries older than N days."""
    manager = _get_manager()
    count = await manager.prune_old(req.max_days)
    return {"message": f"Pruned {count} entries older than {req.max_days} days"}


@memory_router.get("/{agent_folder}/status")
async def memory_status(agent_folder: str):
    """Get memory status for a deep agent."""
    import sqlite3 as _sqlite3
    import os as _os


    from app.core.config import Paths, get_settings
    base = str(Paths.from_settings(get_settings()).agents_dir / agent_folder)

    mem_db = _os.path.join(base, "cognitive_memory.db")
    vec_dir = _os.path.join(base, "vector_index")
    vec_db = _os.path.join(vec_dir, "chunks.db") if _os.path.exists(vec_dir) else None

    status = {
        "agent_folder": agent_folder,
        "has_cognitive_memory_db": _os.path.exists(mem_db),
        "session_count": 0,
        "turn_count": 0,
        "has_summaries": False,
        "summary_count": 0,
        "fact_count": 0,
        "has_vector_index": _os.path.exists(vec_db) if vec_db else False,
        "vector_turn_count": 0,
    }

    if status["has_cognitive_memory_db"]:
        try:
            conn = _sqlite3.connect(mem_db)
            cursor = conn.execute("SELECT COUNT(*) FROM cognitive_memory")
            total = cursor.fetchone()[0]
            # Count sessions (keys that don't start with 'summary:' or are 'facts')
            cursor = conn.execute(
                "SELECT key FROM cognitive_memory"
            )
            summaries = 0
            facts = 0
            sessions = set()
            turns = 0
            for row in cursor.fetchall():
                key = row[0]
                if key.startswith("summary:"):
                    summaries += 1
                elif key == "facts":
                    facts += 1
                else:
                    sessions.add(key)
                    turns += 1
            status["session_count"] = len(sessions)
            status["turn_count"] = turns
            status["summary_count"] = summaries
            status["fact_count"] = facts
            status["has_summaries"] = summaries > 0
            conn.close()
        except Exception:
            pass

    if status["has_vector_index"] and vec_db:
        try:
            conn = _sqlite3.connect(vec_db)
            cursor = conn.execute("SELECT COUNT(*) FROM turn_chunks")
            status["vector_turn_count"] = cursor.fetchone()[0]
            conn.close()
        except Exception:
            pass

    return status


@memory_router.get("/agents")
async def list_deep_agents():
    """List all deep agent folders that have an agent.json."""
    import os as _list_os
    import json as _json
    from app.core.config import Paths, get_settings
    agents_dir = str(Paths.from_settings(get_settings()).agents_dir)
    result = []
    for f in sorted(_list_os.listdir(agents_dir)):
        aj = _list_os.path.join(agents_dir, f, "agent.json")
        if _list_os.path.isfile(aj):
            try:
                with open(aj) as _fh:
                    data = _json.load(_fh)
                result.append({
                    "folder": f,
                    "name": data.get("name", f),
                    "description": data.get("description", ""),
                })
            except Exception:
                result.append({"folder": f, "name": f, "description": ""})
    return result

@memory_router.get("/{agent_folder}/export")
async def export_memory(agent_folder: str):
    """Export agent memory as JSON."""
    import sqlite3 as _sqlite3
    import os as _os

    from app.core.config import Paths, get_settings
    base = str(Paths.from_settings(get_settings()).agents_dir / agent_folder)
    mem_db = _os.path.join(base, "cognitive_memory.db")

    export = {
        "agent_folder": agent_folder,
        "exported_at": __import__("datetime").datetime.now().isoformat(),
        "format_version": "1.0",
        "sessions": {},
        "summaries": [],
        "facts": [],
        "vector_sessions": [],
    }

    if _os.path.exists(mem_db):
        conn = _sqlite3.connect(mem_db)
        cursor = conn.execute("SELECT key, value, turn_count, updated_at FROM cognitive_memory ORDER BY key")
        for row in cursor.fetchall():
            key, value, turn_count, updated_at = row
            if key.startswith("summary:"):
                export["summaries"].append({"session_id": key.replace("summary:", ""), "value": value, "updated_at": updated_at})
            elif key == "facts":
                try:
                    export["facts"] = json.loads(value)
                except Exception:
                    export["facts"] = [value]
            else:
                export["sessions"][key] = {"value": value, "turn_count": turn_count, "updated_at": updated_at}
        conn.close()

    # Vector index summary
    vec_db = _os.path.join(base, "vector_index", "chunks.db")
    if _os.path.exists(vec_db):
        conn = _sqlite3.connect(vec_db)
        cursor = conn.execute("SELECT DISTINCT session_id FROM turn_chunks ORDER BY session_id")
        for row in cursor.fetchall():
            export["vector_sessions"].append(row[0])
        conn.close()

    return export


@memory_router.delete("/{agent_folder}/clear/all")
async def clear_agent_folder(agent_folder: str):
    """Clear ALL memory for a deep agent folder."""
    import os as _os
    from app.core.config import Paths, get_settings
    base = str(Paths.from_settings(get_settings()).agents_dir / agent_folder)
    mem_db = _os.path.join(base, "cognitive_memory.db")
    if _os.path.exists(mem_db):
        _os.unlink(mem_db)
    # Also clear vector index
    vec_db = _os.path.join(base, "vector_index", "chunks.db")
    if _os.path.exists(vec_db):
        _os.unlink(vec_db)
    return {"message": f"All memory cleared for deep agent '{agent_folder}'"}


@memory_router.delete("/{agent_folder}/clear/sessions")
async def clear_agent_sessions(agent_folder: str):
    """Clear session entries but keep summaries and facts."""
    import os as _os, sqlite3 as _sqlite3
    from app.core.config import Paths, get_settings
    base = str(Paths.from_settings(get_settings()).agents_dir / agent_folder)
    mem_db = _os.path.join(base, "cognitive_memory.db")
    count = 0
    if _os.path.exists(mem_db):
        conn = _sqlite3.connect(mem_db)
        cursor = conn.execute("SELECT key FROM cognitive_memory")
        session_keys = [r[0] for r in cursor.fetchall() if not r[0].startswith("summary:") and r[0] != "facts"]
        for key in session_keys:
            conn.execute("DELETE FROM cognitive_memory WHERE key = ?", (key,))
            count += 1
        conn.commit()
        conn.close()
    return {"message": f"Cleared {count} session entries for '{agent_folder}'"}
