"""Skills management API (2026-08-14).

The image-management model applied to the skill library: browse
(the loader's scan/parse/validate output) + curated flag + in-use
view. Read-only for v1 — upload/import/export/delete arrive
organically (skills are DIRECTORIES with SKILL.md inside, not
single files like images).

Curated = ships with the repo (./skills/<category>/<name>/SKILL.md).
Agent-local = lives in an agent's dir (agents/<name>/skills/).
In-use = an agent references the skill (agent-dir file OR derived
from the system prompt).
"""

from __future__ import annotations

import pathlib
from typing import Any, Optional

from fastapi import APIRouter, Query
from app.core.config import Paths, get_settings

router = APIRouter(prefix="/skills", tags=["skills"])

# repo skills root: <repo>/skills (same resolution as skill_reader_handler)
SKILLS_ROOT = str(
    Paths.skills_dir
)
# repo agents root: <repo>/agents
AGENTS_ROOT = str(
    Paths.agents_dir
)


def _skill_to_dict(skill: Any, curated: bool) -> dict[str, Any]:
    return {
        "name": skill.name,
        "description": skill.description,
        "category": skill.category,
        "tags": skill.tags,
        "version": skill.version,
        "author": skill.author,
        "related_skills": skill.related_skills,
        "curated": curated,
        "valid": skill.valid,
        "errors": [e.message for e in skill.errors],
        "warnings": [e.message for e in skill.warnings],
        "path": skill.file_path,
        "body": skill.body or "",
    }


@router.get("")
async def list_skills(
    curated: str = "all",
    q: Optional[str] = Query(default=None, description="Search name/description/tags"),
):
    """List skills with curated flag (loader-validated).

    curated: "all" (default) | "true" (repo skills only) | "false"
    (agent-local only). q filters name/description/tags (case-
    insensitive substring).
    """
    from app.skills.loader import SkillLoader

    loader = SkillLoader(root_dir=SKILLS_ROOT)
    skills = loader.scan()

    # agent-local skills: agents/<name>/skills/*.skill.md (system-manager's model)
    agent_skills: list[dict[str, Any]] = []
    agents_root = pathlib.Path(AGENTS_ROOT)
    if agents_root.is_dir():
        for skill_file in sorted(agents_root.glob("*/skills/*.skill.md")):
            name = skill_file.stem
            agent = skill_file.parent.parent.name
            body = skill_file.read_text(encoding="utf-8", errors="replace")
            agent_skills.append({
                "name": name,
                "description": "",
                "category": agent,
                "tags": [],
                "version": "",
                "author": "",
                "related_skills": [],
                "curated": False,
                "valid": True,
                "errors": [],
                "warnings": [],
                "path": str(skill_file),
                "body": body,
            })

    items = [_skill_to_dict(s, True) for s in skills] + agent_skills

    if curated == "true":
        items = [i for i in items if i["curated"]]
    elif curated == "false":
        items = [i for i in items if not i["curated"]]

    if q:
        ql = q.lower()
        items = [
            i for i in items
            if ql in i["name"].lower()
            or ql in (i["description"] or "").lower()
            or any(ql in t.lower() for t in i["tags"])
        ]

    items.sort(key=lambda i: (not i["curated"], i["name"].lower()))
    return {"skills": items, "total": len(items)}


@router.get("/in-use")
async def skills_in_use():
    """Which agents reference which skills.

    Sources (both shown, marked):
    - file: the agent dir has skills/<name>.skill.md
    - derived: the agent's system_prompt mentions the skill name
      (the AgentCard skill derivation: system_prompt is the primary
      skill). Read-only view — no mapping table invented.
    """
    import sqlite3

    # file-based: agents/<name>/skills/*.skill.md
    file_map: dict[str, list[str]] = {}
    agents_root = pathlib.Path(AGENTS_ROOT)
    if agents_root.is_dir():
        for skill_file in sorted(agents_root.glob("*/skills/*.skill.md")):
            agent = skill_file.parent.parent.name
            file_map.setdefault(skill_file.stem, []).append(agent)

    # prompt-derived: scan DB agents' system_prompts for skill names
    derived_map: dict[str, list[str]] = {}
    db_path = Paths.from_settings(get_settings()).shared_db
    if db_path.exists():
        try:
            con = sqlite3.connect(str(db_path))
            rows = con.execute(
                "SELECT name, system_prompt FROM agents"
            ).fetchall()
            con.close()
            for agent_name, system_prompt in rows:
                if not system_prompt:
                    continue
                skill_files = list(agents_root.glob("*/skills/*.skill.md")) if agents_root.is_dir() else []
                for skill_file in skill_files:
                    stem = skill_file.stem
                    if stem.lower() in system_prompt.lower():
                        derived_map.setdefault(stem, []).append(agent_name)
        except Exception:
            pass

    # union, with source labels
    all_names = sorted(set(file_map) | set(derived_map))
    return {
        "assignments": [
            {
                "skill": name,
                "agents": sorted(set(file_map.get(name, []) + derived_map.get(name, []))),
                "sources": {
                    "file": file_map.get(name, []),
                    "derived": derived_map.get(name, []),
                },
            }
            for name in all_names
        ],
        "total": len(all_names),
    }
