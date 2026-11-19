"""
Agent export/import service.

Exports an agent's configuration, cognitive memory, and skill files
as a JSON bundle. Imports a bundle to create a new agent with the
same configuration and memory.
"""

from __future__ import annotations

import json
import logging
import os as _os
import sqlite3
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


async def _agent_folder_path(
    agent_id: int, db_session
) -> Optional[str]:
    """Return the per-agent workspace folder, or None.

    The repository seam (agent-lifecycle Phase A): the folder is
    found by the workspace_key COLUMN — no filesystem scan. The
    DB-first lens: the disk is the manifestation of the row.
    """
    from app.domain.agents.repository import get_agent_repository
    repo = get_agent_repository(db_session)
    return await repo.agent_workspace(agent_id)


async def export_agent(agent_id: int, db_session) -> Dict[str, Any]:
    """Export an agent's full configuration and memory as a JSON bundle.

    Returns a dict with:
    - agent_config: the agent record from the DB
    - agent_json: the agents/{name}/agent.json contents (if exists)
    - cognitive_memory: all entries from cognitive_memory.db (if exists)
    - skills: list of skill files with their contents
    """
    from sqlalchemy import select
    from app.infrastructure.database.models import Agent

    # 1. Get agent config from DB
    query = select(Agent).where(Agent.id == agent_id)
    result = await db_session.execute(query)
    agent = result.scalar_one_or_none()

    if not agent:
        raise ValueError(f"Agent {agent_id} not found")

    # Convert to dict, excluding SQLAlchemy internals
    agent_config = {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "provider": agent.provider,
        "model": agent.model,
        "system_prompt": agent.system_prompt,
        "cognitive_profile_id": agent.cognitive_profile_id,
        "is_active": agent.is_active,
        "parameters": agent.parameters,
        "tools": [],  # tools are linked via agent_tools table
    }

    bundle: Dict[str, Any] = {
        "format_version": "1.0",
        "agent_config": agent_config,
    }

    # 2. Get per-agent folder contents
    folder_path = await _agent_folder_path(agent_id, db_session)
    if folder_path:
        # agent.json
        json_path = _os.path.join(folder_path, "agent.json")
        if _os.path.exists(json_path):
            with open(json_path) as f:
                bundle["agent_json"] = json.load(f)

        # Skills
        skills_dir = _os.path.join(folder_path, "skills")
        skills: List[Dict[str, str]] = []
        if _os.path.exists(skills_dir):
            for fname in sorted(_os.listdir(skills_dir)):
                if fname.endswith(".md") or fname.endswith(".skill.md"):
                    with open(_os.path.join(skills_dir, fname)) as f:
                        skills.append({"filename": fname, "content": f.read()})
        if skills:
            bundle["skills"] = skills

        # Cognitive memory
        mem_db = _os.path.join(folder_path, "cognitive_memory.db")
        if _os.path.exists(mem_db):
            try:
                conn = sqlite3.connect(mem_db)
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT key, value, created_at, updated_at FROM cognitive_memory").fetchall()
                bundle["cognitive_memory"] = [dict(r) for r in rows]
                conn.close()
            except sqlite3.Error as e:
                logger.warning("Failed to read cognitive_memory.db: %s", e)

    return bundle


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

# ── WHERE AN IMPORTED AGENT'S SERVICE COMES FROM ───────────────────────────────────────────────
#
# **RULED 2026-10-11 (the user) — `wiki/issues/resolved/embedded-service-literals/agent-import-service.md`, option A**: *"the import
# always yields a working agent; the only refusal is for an install that has no default row to
# answer with."*
#
# This used to fall back to `provider="ollama"` / `model="llama3.2"` — two service literals deciding
# for a bundle that named nothing, which on the live install meant an address nobody is listening on
# (`localhost:11434`, measured refused) and a model id that exists nowhere (0 curated rows, 0
# agents, not the model the running server mounts). A service is a DECISION (see
# `provider_endpoints`' ruling), so it resolves; the rule is the one every other service choice in
# this app already follows — `#2`'s (`api/v1/agents/provisioning_router._resolve_service`): what the
# caller STATES wins, a silent half resolves from the `is_default` provider row, and an install with
# no default row REFUSES rather than inventing a service.
#
# BOTH doors to a service-less agent are closed, because they were two doors to the same hole: a
# MISSING key, and an empty string — the empty one bypassed the literal entirely and reached a
# `nullable=False` column.
#
# And the resolution is REPORTED, never silent: the returned `ImportedAgent` carries what the
# service is and where it came from, so the route can say it in the response and this module says it
# in the log. The arc's own rule — a configuration gap must not pass for an address somebody chose —
# applies here to a service.

SERVICE_FROM_BUNDLE = "the bundle"
SERVICE_FROM_DEFAULT_ROW = "the install's default provider row"


def stated_service(agent_config: Dict[str, Any]) -> tuple[str, str]:
    """What the bundle NAMES. A missing key and `""` are the same answer: each half comes back empty.

    The two were not the same answer before — the missing key reached the literal, the empty string
    reached the column. Silence is silence, so one helper reads both.
    """
    return (
        str(agent_config.get("provider") or "").strip(),
        str(agent_config.get("model") or "").strip(),
    )


@dataclass(frozen=True)
class ImportedAgent:
    """An import's result: the new row, the service it got, and WHERE that service came from."""

    agent_id: int
    provider: str
    model: str
    service_source: str


async def resolve_imported_service(
    db_session, agent_config: Dict[str, Any]
) -> tuple[str, str, str]:
    """THE RULE for an imported agent's service: stated → else the default row → else REFUSE.

    Returns ``(provider, model, source)``. Raises ``ValueError`` when the bundle names nothing **and**
    this install has no default provider row to answer with: the import refuses, because an agent row
    with no service is a hole every consumer would have to tolerate, and an import is a COPY of an
    agent that already had one (whereas a provision creates an agent whose service its profile goes on
    to supply — the distinction the ruling was made on).
    """
    stated_provider, stated_model = stated_service(agent_config)
    if stated_provider and stated_model:
        return stated_provider, stated_model, SERVICE_FROM_BUNDLE

    from app.domain.providers.config_service import DefaultProviderService

    cfg = await DefaultProviderService().get_default_provider(db_session)
    if cfg is None:
        raise ValueError(
            "This bundle names no provider and no model, and this install has no default provider "
            "row to resolve them from — set a default provider, or name both halves in the bundle."
        )

    missing = (
        "provider and model"
        if not stated_provider and not stated_model
        else ("model" if stated_provider else "provider")
    )
    logger.warning(
        "Agent import: the bundle names no %s — resolved from this install's default provider row "
        "'%s' (%s/%s).",
        missing,
        cfg.name,
        stated_provider or cfg.name,
        stated_model or cfg.default_model,
    )
    return stated_provider or cfg.name, stated_model or cfg.default_model, SERVICE_FROM_DEFAULT_ROW


async def import_agent(bundle: Dict[str, Any], db_session) -> ImportedAgent:
    """Import an agent from an export bundle.

    Creates a new agent in the database, writes per-agent files, and restores cognitive memory.

    The new agent's SERVICE resolves through `resolve_imported_service` — never a literal — and a
    bundle that states it is copied through untouched. The returned `ImportedAgent` carries the
    service and its source, so a caller can REPORT a substitution instead of leaving it silent.

    The WORKSPACE is the workspace module's, not this function's: a minted key on the row, and the
    folder scaffolded from the row — so the disk manifests the row and every folder-side reader
    (export, archive, restore, delete) can find it. Both halves were hand-rolled here before, and
    both were wrong: no `workspace_key` at all, and a folder named straight from the bundle's own
    name — which is data, and could aim the write anywhere on disk.
    """
    from app.infrastructure.database.models import Agent
    from sqlalchemy import select

    from app.domain.agents.workspace import make_workspace_key, scaffold

    # Validate bundle format
    if bundle.get("format_version") != "1.0":
        raise ValueError("Unsupported export format version")

    agent_config = bundle.get("agent_config", {})
    if not agent_config.get("name"):
        raise ValueError("Agent name is required")

    # 0. The SERVICE, before anything is written: a refusal must leave no row and no folder behind.
    service_provider, service_model, service_source = await resolve_imported_service(
        db_session, agent_config
    )

    # 1. The row — WITH its workspace key, which is the folder's identity (the DB-first lens: the row
    # carries the key and the folder is what it points at). The key is minted through the workspace
    # module, which SLUGIFIES the name: the bundle's name is data, so it must not be able to decide
    # where the folder goes.
    import uuid
    suffix = uuid.uuid4().hex[:6]
    new_name = f"{agent_config['name']}-imported-{suffix}"
    existing_keys = set(
        (
            await db_session.execute(
                select(Agent.workspace_key).where(Agent.workspace_key.is_not(None))
            )
        )
        .scalars()
        .all()
    )
    workspace_key = make_workspace_key(new_name, existing_keys)

    new_agent = Agent(
        name=new_name,
        description=agent_config.get("description", ""),
        provider=service_provider,
        model=service_model,
        system_prompt=agent_config.get("system_prompt", ""),
        cognitive_profile_id=agent_config.get("cognitive_profile_id"),
        workspace_key=workspace_key,
        is_active=True,
        parameters=agent_config.get("parameters"),
    )
    db_session.add(new_agent)
    await db_session.flush()
    await db_session.refresh(new_agent)
    new_id = new_agent.id

    # 2. The workspace folder, scaffolded from the ROW — the key's directory, the derived agent.json,
    # skills/, state.json and persona.md. The bundle's payload lands on top of it below.
    ws_dir = scaffold(new_agent)

    # agent.json — the bundle's own manifest, with the fields THIS import decided patched to the
    # row's: the row is authoritative, so a manifest that still named the service the resolution
    # replaced must not leave the folder disagreeing with the database.
    agent_json = bundle.get("agent_json", {})
    if agent_json:
        agent_json["db_id"] = new_id
        agent_json["name"] = new_name
        agent_json["provider"] = service_provider
        agent_json["model"] = service_model
        with open(_os.path.join(ws_dir, "agent.json"), "w") as f:
            json.dump(agent_json, f, indent=2)

    # Skills
    for skill in bundle.get("skills", []):
        fname = skill.get("filename", "")
        content = skill.get("content", "")
        if fname:
            with open(_os.path.join(ws_dir, "skills", fname), "w") as f:
                f.write(content)

    # Cognitive memory
    mem_entries = bundle.get("cognitive_memory", [])
    if mem_entries:
        mem_db = _os.path.join(ws_dir, "cognitive_memory.db")
        try:
            conn = sqlite3.connect(mem_db)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cognitive_memory (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            for entry in mem_entries:
                conn.execute(
                    "INSERT OR REPLACE INTO cognitive_memory (key, value, created_at, updated_at) VALUES (?, ?, ?, ?)",
                    (entry.get("key"), entry.get("value"), entry.get("created_at"), entry.get("updated_at")),
                )
            conn.commit()
            conn.close()
            logger.info("Restored %d cognitive memory entries for agent %d", len(mem_entries), new_id)
        except sqlite3.Error as e:
            logger.warning("Failed to restore cognitive memory: %s", e)

    logger.info(
        "Imported agent %d (original: %s, new name: %s, service: %s/%s — from %s)",
        new_id,
        agent_config.get("name"),
        new_name,
        service_provider,
        service_model,
        service_source,
    )
    return ImportedAgent(
        agent_id=new_id,
        provider=service_provider,
        model=service_model,
        service_source=service_source,
    )
