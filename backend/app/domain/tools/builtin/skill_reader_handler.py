"""Skill reader tool — generic skills + the agent's OWN folder skills.

The skills partition (2026-09-02, the user's workspace-first call):
generic/shared skills live repo-level (skills/); agent-specific
skills live in the agent's workspace (agents/<key>/skills/). This
one tool reads BOTH — the agent's personal sheets are reachable
through the same surface as the generic ones.

THE TWO CONVENTIONS: the repo's curated skills are directory-style
(<category>/<name>/SKILL.md — what SkillLoader.scan() globs); the
per-agent + flat skills are `{name}.skill.md` (the context_builder +
skills_router convention). The agent-folder fallback scans BOTH.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import Paths

SKILLS_ROOT = str(Paths.skills_dir)


def _scan_dir(root: str | Path) -> list:
    """Scan a skills root for BOTH conventions: directory-style
    SKILL.md files (SkillLoader's glob) and flat {name}.skill.md
    files (the agent/personal convention). Returns parsed Skills."""
    from app.skills.loader import SkillLoader

    loader = SkillLoader(root_dir=str(root))
    found = loader.scan()  # the SKILL.md convention

    root_p = Path(root)
    if root_p.is_dir():
        for f in sorted(root_p.rglob("*.skill.md")):
            skill = loader._parse_file(f)
            found.append(skill)
    return found


def _load_skills(config: dict[str, Any]) -> list:
    """The skill roots: the GLOBAL skills dir + (when present) the
    AGENT'S OWN folder skills dir. Agent skills win name ties (later
    entries overwrite in the merged dict). Agents WITHOUT a workspace
    get the global dir only (the system-manager path keeps its old
    behavior — the global scan still finds only SKILL.md there, which
    is unchanged for repo-curated skills)."""
    merged: dict[str, Any] = {}
    for skill in _scan_dir(SKILLS_ROOT):
        merged[skill.name.lower()] = skill
    base = config.get("base_path")
    if base:
        agent_skills = Path(base) / "skills"
        if agent_skills.is_dir():
            for skill in _scan_dir(agent_skills):
                merged[skill.name.lower()] = skill  # agent wins ties
    return list(merged.values())


def _to_skill_dict(skill) -> dict:
    return {
        "name": skill.name,
        "description": skill.description,
        "category": skill.category,
        "version": skill.version,
        "tags": skill.tags,
        "body": skill.body,
    }


class SkillReaderTool:
    """The skill reader — generic + personal, one surface."""

    name = "Skill Reader"
    slug = "skill-reader"
    capability = "doc-lookup"
    # THE WORKSPACE GRANT: the execution service injects the agent's
    # own folder as base_path (needs_workspace, 2026-08-24) — the
    # handler then scans agents/<key>/skills/ in addition to the
    # global dir. No workspace -> global dir only (unchanged).
    needs_workspace = True
    description = (
        "Search and read skill sheets: the SHARED skills (the repo's "
        "generic procedures) AND your OWN personal skills (the skills "
        "folder in your workspace — yours alone). Use skill_name for "
        "the full sheet, query to search across both."
    )
    icon = "book"
    color = "#6F42C1"
    tags = ["skills", "documentation", "procedures", "personal"]
    config_schema: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    arguments_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Optional search term to find relevant skills"},
            "skill_name": {"type": "string", "description": "Optional exact skill name to load full content"},
        },
        "required": [],
    }

    def __init__(self) -> None:
        pass

    async def execute(self, config: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        query = kwargs.get("query", "")
        skill_name = kwargs.get("skill_name", "")

        skills = _load_skills(config)

        if skill_name:
            q = skill_name.lower()
            for s in skills:
                if s.name.lower() == q:
                    return {"success": True, "skill": _to_skill_dict(s)}
            return {"success": False, "error": f"Skill not found: {skill_name}"}

        if query:
            q = query.lower()
            matches = [
                _to_skill_dict(s) for s in skills
                if q in s.name.lower() or q in (s.description or "").lower()
                or any(q in (t or "").lower() for t in (s.tags or []))
            ]
            return {"success": True, "matches": matches, "count": len(matches)}

        return {
            "success": True,
            "skills": [_to_skill_dict(s) for s in skills],
            "count": len(skills),
        }
