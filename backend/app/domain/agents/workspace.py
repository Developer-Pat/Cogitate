"""Agent workspace scaffold (agent-lifecycle Phase B).

The agent's on-disk identity: a stable-keyed folder with a DERIVED
agent.json (regenerable from the row — never a second source of
truth) + an empty skills/ directory. The DB-first lens: the disk
is the manifestation of the row; the workspace_key COLUMN is the
lookup (Phase A's seam), the folder is what it points at.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.infrastructure.database.models import Agent

# The agents/ root (absolute, project-anchored — never cwd-relative)
from app.core.config import Paths, get_settings
AGENTS_ROOT = Paths.from_settings(get_settings()).agents_dir

# The shared skill library (repo-root skills/) — the SAME pool the
# skill-reader tool scans. A new agent's named skills are copied from
# here into its own workspace.
SHARED_SKILLS = Paths.skills_dir


def _slugify(name: str) -> str:
    """A filesystem-safe key from the agent name (lowercase,
    alphanumeric + hyphens)."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "agent"


def make_workspace_key(name: str, existing_keys: set[str]) -> str:
    """A STABLE, unique workspace key for a new agent.

    From the name (human-readable) with a short suffix when the
    slug collides. NOT the raw name — folder-safe + rename-proof
    (renames never move files; the key is the column's value).
    """
    base = _slugify(name)
    key = base
    n = 1
    while key in existing_keys:
        key = f"{base}-{n}"
        n += 1
    return key


def agent_json(agent: Agent) -> dict:
    """The DERIVED agent.json contents — a snapshot of the row."""
    return {
        "format_version": "1.0",
        "folder": agent.workspace_key or "",
        "name": agent.name,
        "description": agent.description,
        "provider": agent.provider,
        "model": agent.model,
        # NOTE: the persona is NOT in the manifest (2026-09-02 — the
        # workspace-first partition): it lives in persona.md (the
        # workspace home) + the agents row (the synced fallback).
        # agent.json is a registry manifest, not a content store.
        "cognitive_profile_id": agent.cognitive_profile_id,
        "skills": agent.skills or [],
        "tags": agent.tags or [],
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        "is_active": agent.is_active,
        "db_id": agent.id,
        "workspace_key": agent.workspace_key,
        # DERIVED — regenerable from the agents row (the source of
        # truth is the DB; this file is a convenience snapshot).
        "_derived": True,
    }


def scaffold(agent: Agent) -> Path:
    """Create the workspace folder + derived agent.json + skills/, seed
    the named skills, and start a fresh state.json.

    IDEMPOTENT by design: an existing file is never overwritten. An
    agent's own state and its grown skills must survive a re-scaffold
    (provision runs on existing agents too).

    Returns the workspace path. Raises OSError on write failure
    (the caller rolls back the row).
    """
    key = agent.workspace_key or make_workspace_key(agent.name, set())
    agent.workspace_key = key
    ws_dir = AGENTS_ROOT / key
    ws_dir.mkdir(parents=True, exist_ok=True)
    skills_dir = ws_dir / "skills"
    skills_dir.mkdir(exist_ok=True)
    (ws_dir / "agent.json").write_text(
        json.dumps(agent_json(agent), indent=2), encoding="utf-8"
    )

    # THE STARTING STATE (2026-09-10): every agent gets a state.json to
    # start from. It is NEVER carried in from a template — an agent's
    # facts are its own (Bob's location, his watch list). A template
    # clones the CHARACTER; the instance starts empty.
    state_path = ws_dir / "state.json"
    if not state_path.exists():
        # {"facts": {}, "sources": []} — BOTH keys present and empty, so
        # the update-state / update-sources tools have a well-formed store
        # to write into from the first turn. An empty store is NOT
        # defaulted with placeholder facts: the agent genuinely knows
        # nothing yet, and its persona says so (the STORED STATE block is
        # omitted entirely while it is empty).
        state_path.write_text(
            json.dumps({"facts": {}, "sources": []}, indent=2), encoding="utf-8"
        )

    # THE SKILL SEEDING (2026-09-10): the row's `skills` list names the
    # skills; the shared library is the source. Missing files are copied,
    # existing ones are left alone ("skills grow").
    _seed_skills(agent, skills_dir)

    # THE PERSONA HOME (2026-09-02): provision writes persona.md from
    # the row (the folder-first read path then prefers the file; the
    # row stays the synced fallback). Best-effort — the row remains.
    _prompt = getattr(agent, "system_prompt", None)
    if _prompt:
        try:
            (ws_dir / "persona.md").write_text(_prompt, encoding="utf-8")
        except OSError:
            import logging
            logging.getLogger(__name__).warning(
                "persona.md write failed at %s — the row stays authoritative", ws_dir
            )
    return ws_dir


def _find_shared_skill(name: str) -> Path | None:
    """Locate a shared skill by name, in either house convention.

    The repo's curated skills are directory-style
    (`<category>/<name>/SKILL.md`); the flat/agent convention is
    `{name}.skill.md`. Both are supported because the skill-reader
    tool reads both.
    """
    if not SHARED_SKILLS.is_dir():
        return None
    flat = SHARED_SKILLS / f"{name}.skill.md"
    if flat.exists():
        return flat
    for p in SHARED_SKILLS.rglob("SKILL.md"):
        if p.parent.name == name:
            return p
    return None


def _seed_skills(agent: Agent, ws_skills_dir: Path) -> list[str]:
    """Copy the agent's named skills in from the shared library.

    Best-effort by design: a skill this install does not have is logged,
    not fatal — a template may name one that was never shipped, and a
    half-created agent is worse than a missing skill.
    """
    import logging
    import shutil

    logger = logging.getLogger(__name__)

    names = getattr(agent, "skills", None) or []
    if isinstance(names, str):
        try:
            names = json.loads(names)
        except (ValueError, TypeError):
            names = []
    if not isinstance(names, list):
        return []

    seeded: list[str] = []
    for name in names:
        src = _find_shared_skill(str(name))
        if src is None:
            logger.warning(
                "skill %r not found in %s — not seeded (the agent keeps its row)",
                name, SHARED_SKILLS,
            )
            continue
        dst = ws_skills_dir / src.name
        if dst.exists():
            continue  # a grown or edited skill is never overwritten
        shutil.copy2(src, dst)
        seeded.append(str(name))
    if seeded:
        logger.info("seeded %d skill(s) into %s", len(seeded), ws_skills_dir)
    return seeded


def provision(agent: Agent, existing_keys: set[str]) -> Path:
    """Attach a workspace to an EXISTING agent row (the shallow-agent
    provisioning, 2026-09-02): assign a stable key when the row has
    none, then scaffold the folder (agent.json derived + skills/).

    THE IDEMPOTENCE: when the row already has a key, the existing
    folder is returned untouched (never a second folder, never a key
    change — the workspace identity is stable; the create path makes
    new keys, this path adopts old rows like Bob).

    Returns the workspace path. Raises OSError on write failure.
    """
    if agent.workspace_key:
        return AGENTS_ROOT / agent.workspace_key
    key = make_workspace_key(agent.name, existing_keys)
    agent.workspace_key = key
    return scaffold(agent)
