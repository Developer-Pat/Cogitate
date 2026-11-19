"""REST endpoints for deep agent provisioning.

Provides create, archive, and status operations for the agents/{name}/ structure.
"""
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agents", tags=["agents-provisioning"])

from app.core.config import Paths, get_settings as _get_settings

def _agents_dir() -> str:
    """The agents root, resolved PER CALL.

    This was a module-level constant — `AGENTS_DIR = Paths.from_settings(...)` —
    which freezes the value at import. Anything that redirects the installation
    (the test harness, a packaged fork, a second profile) imports the app before
    the redirect applies, so the constant kept pointing at the ORIGINAL root and
    agent folders were written there. Resolving per call makes it follow the
    resolver, which is the entire point of having one.
    """
    return str(Paths.from_settings(_get_settings()).agents_dir)


def _shared_db_path() -> str:
    """The shared cogitate.db path — derived from the app's settings
    (the same pattern as trigger_service), so tests can point it at a
    test DB via DATABASE_URL instead of the hardcoded absolute path
    (the TestAgent resurrection root-cause, 2026-08-17: this router
    wrote directly to the production DB during test runs)."""
    from app.core.config import get_settings
    return urlparse(get_settings().database_url).path


class AgentProvisionRequest(BaseModel):
    name: str
    description: str = ""
    # THE SERVICE IS NOT NAMED HERE (2026-10-09). These two used to default to
    # "openrouter" and "deepseek/deepseek-v4-flash" — a service and a model written into the
    # code that creates the row, so the operator's configured default provider was never
    # consulted for a NEW agent (and the two defaults disagreed with the row they named: the
    # default row is `deepseek` / `deepseek-v4-flash`). Left unset they resolve from the
    # DEFAULT PROVIDER ROW — see `_resolve_service`. A caller that states them still wins.
    provider: str | None = None
    model: str | None = None
    system_prompt: str = "You are a helpful assistant."
    cognitive_profile_id: int | None = None
    tools: list[str] = []
    tags: list[str] = []


def _validate_folder_name(name: str) -> str:
    """Validate and normalize a folder name."""
    import re
    if not re.match(r"^[a-z][a-z0-9-]{0,63}$", name):
        raise HTTPException(400, f"Invalid folder name '{name}'. Use lowercase, hyphens, max 64 chars.")
    return name


def _agent_dir(name: str) -> str:
    return os.path.join(_agents_dir(), name)


def _agent_json_path(name: str) -> str:
    return os.path.join(_agent_dir(name), "agent.json")


async def _resolve_service(
    db: AsyncSession, req: "AgentProvisionRequest | None"
) -> tuple[str, str]:
    """The provider and model for a NEW agent: what the caller STATED, else the default row's.

    Nothing here names a service. A provision request that supplies both halves is taken at
    its word; anything else falls to the row marked `is_default` — the same answer every
    other service choice in the app resolves through, so flipping the default provider in
    the UI moves new agents with it.

    The session is the CALLER's (the request's own), because the answer lives in the
    database and this is where a session exists.
    """
    stated_provider = (req.provider if req else None) or ""
    stated_model = (req.model if req else None) or ""
    if stated_provider and stated_model:
        return stated_provider, stated_model

    from app.domain.providers.config_service import DefaultProviderService

    cfg = await DefaultProviderService().get_default_provider(db)
    if cfg is None:
        # Nothing configured — name no service rather than invent one. The agent is still
        # created, and its service is set from its profile like any other.
        return stated_provider, stated_model
    return stated_provider or cfg.name, stated_model or cfg.default_model


@router.post("/{name}/provision")
async def provision_agent(
    name: str,
    req: AgentProvisionRequest | None = None,
    db: AsyncSession = Depends(get_db_session),
):
    """Create a deep agent folder with template databases and agent.json."""
    name = _validate_folder_name(name.replace("_", "-"))
    agent_dir = _agent_dir(name)
    agent_json = _agent_json_path(name)

    if os.path.exists(agent_dir):
        raise HTTPException(409, f"Agent folder already exists: agents/{name}/")

    service_provider, service_model = await _resolve_service(db, req)

    os.makedirs(agent_dir, exist_ok=True)
    os.makedirs(os.path.join(agent_dir, "skills"), exist_ok=True)

    # Write agent.json
    now = datetime.now(timezone.utc).isoformat()
    agent_data = {
        "format_version": "1.0",
        "folder": name,
        "name": req.name if req else name,
        "description": req.description if req else "",
        "provider": service_provider,
        "model": service_model,
        "system_prompt": req.system_prompt if req else "You are a helpful assistant.",
        "cognitive_profile_id": req.cognitive_profile_id if req else None,
        "tools": req.tools if req else [],
        "tags": req.tags if req else [],
        "created_at": now,
        "updated_at": now,
        "is_active": True,
    }
    with open(agent_json, "w") as f:
        json.dump(agent_data, f, indent=2)

    # Register in shared cogitate.db so the agent appears in the chat UI
    try:
        _shared_db = _shared_db_path()
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(_shared_db)
        # Check if agent with this folder name already exists
        existing = conn.execute(
            "SELECT id FROM agents WHERE name = ?", (agent_data["name"],)
        ).fetchone()
        if not existing:
            # workspace_key = the folder name — the stable key so
            # archive/restore can find the workspace (the lifecycle
            # unification, probe 4 finding: provisioning agents had
            # NULL workspace_key → restore couldn't move the folder)
            ws_key = agent_data.get("folder") or name
            conn.execute(
                "INSERT INTO agents (name, description, provider, model, system_prompt, cognitive_profile_id, is_active, workspace_key) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                (
                    agent_data["name"],
                    agent_data["description"],
                    agent_data["provider"],
                    agent_data["model"],
                    agent_data["system_prompt"],
                    agent_data.get("cognitive_profile_id"),
                    ws_key,
                ),
            )
            conn.commit()
            # Get the DB id and store it in agent.json
            db_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            agent_data["db_id"] = db_id
            with open(agent_json, "w") as f:
                json.dump(agent_data, f, indent=2)
            logger.info("Registered deep agent '%s' in shared DB (id=%d)", name, db_id)
        conn.close()
    except Exception as exc:
        logger.warning("Could not register deep agent in shared DB: %s", exc)
        # Non-fatal — agent is still usable via direct API

    # Assign tools from the request if tool names are provided
    if req and req.tools:
        try:
            import uuid as _uuid
            _shared_db = _shared_db_path()
            conn = _sqlite3.connect(_shared_db)
            # Map tool names to tool IDs
            tool_name_to_id = {}
            for trow in conn.execute("SELECT id, name FROM tools").fetchall():
                tool_name_to_id[trow[1].lower()] = trow[0]
            priority = 1
            for tool_name in req.tools:
                tname = tool_name.lower()
                # Try exact name match, then partial
                tool_id = tool_name_to_id.get(tname)
                if not tool_id:
                    for db_name, db_id in tool_name_to_id.items():
                        if tname in db_name or db_name in tname:
                            tool_id = db_id
                            break
                if tool_id:
                    existing = conn.execute(
                        "SELECT id FROM agent_tools WHERE agent_id = ? AND tool_id = ?",
                        (str(agent_data["db_id"]), tool_id),
                    ).fetchone()
                    if not existing:
                        new_id = _uuid.uuid4().hex[:32]
                        conn.execute(
                            "INSERT INTO agent_tools (id, agent_id, tool_id, is_enabled, priority) VALUES (?, ?, ?, 1, ?)",
                            (new_id, str(agent_data["db_id"]), tool_id, priority),
                        )
                        priority += 1
                else:
                    logger.warning("Tool '%s' not found in registry, skipping", tool_name)
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.warning("Could not assign tools: %s", exc)

    logger.info("Provisioned deep agent: agents/%s/", name)
    return {"message": f"Agent '{name}' provisioned", "folder": f"agents/{name}/", "agent": agent_data}


@router.get("/{name}/status")
async def get_agent_status(name: str):
    """Get the status of a deep agent folder."""
    name = _validate_folder_name(name)
    agent_dir = _agent_dir(name)
    agent_json = _agent_json_path(name)

    if not os.path.exists(agent_json):
        raise HTTPException(404, f"Agent not found: agents/{name}/")

    with open(agent_json) as f:
        agent_data = json.load(f)

    # Collect folder stats
    mem_db = os.path.join(agent_dir, "cognitive_memory.db")
    skills_dir = os.path.join(agent_dir, "skills")
    vec_dir = os.path.join(agent_dir, "vector_index")

    vec_db_path = os.path.join(vec_dir, "chunks.db") if os.path.exists(vec_dir) else None
    status_data = {
        "folder": f"agents/{name}/",
        "agent": agent_data,
        "exists": True,
        "databases": {
            "cognitive_memory.db": os.path.getsize(mem_db) if os.path.exists(mem_db) else 0,
        },
        "skills_count": len(os.listdir(skills_dir)) if os.path.exists(skills_dir) else 0,
        "has_vector_index": os.path.exists(vec_db_path) if vec_db_path else False,
        "has_vector_turns": 0,
    }
    # Count vector turns
    if vec_db_path and os.path.exists(vec_db_path):
        try:
            import sqlite3 as _s
            conn = _s.connect(vec_db_path)
            cursor = conn.execute("SELECT COUNT(*) FROM turn_chunks")
            status_data["has_vector_turns"] = cursor.fetchone()[0]
            conn.close()
        except Exception:
            pass
    return status_data


@router.delete("/{name}/archive")
async def archive_agent(name: str):
    """Archive a deep agent by MOVING its folder onto the trash's agents shelf.

    ONE DESTINATION. The shelf (`trash/agents/`) is the same one the repository's
    recoverable delete uses, so an archived deep agent lands where the trash
    page, the API and Exa can all read it — instead of a second, hidden archive
    that no surface lists.
    """
    name = _validate_folder_name(name)
    agent_dir = _agent_dir(name)
    agent_json = _agent_json_path(name)

    if not os.path.exists(agent_json):
        raise HTTPException(404, f"Agent not found: agents/{name}/")

    from app.domain.agents import trash as agent_trash

    archive_path = str(agent_trash.move_to_shelf(Path(agent_dir), name))

    # Mark inactive in agent.json copy
    archive_json = os.path.join(archive_path, "agent.json")
    if os.path.exists(archive_json):
        with open(archive_json) as f:
            data = json.load(f)
        data["is_active"] = False
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(archive_json, "w") as f:
            json.dump(data, f, indent=2)

    # UNIFY the lifecycle (probe 4 finding, 2026-08-17): soft-delete
    # the DB row too — the folder-only archive left the agent ACTIVE
    # in /agents, never in /deleted, and restore always 400'd (a
    # zombie). Now archive == the repo delete semantics: deleted_at +
    # archived_path + is_active=0, so /deleted lists it and
    # /{id}/restore can recover it.
    try:
        _shared_db = _shared_db_path()
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(_shared_db)
        now_iso = datetime.now(timezone.utc).isoformat()
        # THE PATH THE MOVE ACTUALLY USED. The row must name the same place the
        # folder landed — a second composition here is how a row comes to point
        # at a folder that is not there.
        abs_archive = archive_path
        conn.execute(
            "UPDATE agents SET deleted_at = ?, archived_path = ?, is_active = 0 "
            "WHERE name = ? AND deleted_at IS NULL",
            (now_iso, abs_archive, data.get("name", name)),
        )
        conn.commit()
        conn.close()
        logger.info("Soft-deleted deep agent '%s' in shared DB (lifecycle unified)", name)
    except Exception as exc:
        logger.warning("Could not soft-delete deep agent in shared DB: %s", exc)

    logger.info("Archived deep agent: agents/%s/ → the trash's agents shelf (%s)", name, archive_path)
    return {"message": f"Agent '{name}' archived", "archived_to": archive_path}
