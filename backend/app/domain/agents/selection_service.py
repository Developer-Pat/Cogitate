"""Agent selection service (ARM Phase B — the yellow pages).

select_agents(db, criteria) — the ARM's query surface: filter the
pool by capability/role/domain/depth/provider/spec/collective,
rank deterministically, return ARM cards. GRAS semantics: selection
is information, access is the grant (the tooling upgrade's Phase C)
— this service never grants.

Criteria are AND-ed; capability is OR-within-field. Empty criteria
= the whole pool (discovery).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import Agent
from app.domain.tools.models import AgentTool, Tool
from app.domain.tools.provider_spec import spec_for

# the curated role/domain vocabulary (Phase B kickoff — the kinds
# lesson: plain, curated, no invented codes). Agents' tags feed
# role/domain at create; the vocabulary validates + displays.
ROLE_VOCABULARY = {
    "writer", "researcher", "coder", "analyst", "designer",
    "prompt-engineer", "system-ops", "generalist",
}
DOMAIN_VOCABULARY = {
    "fiction", "nonfiction", "math", "physics", "software",
    "finance", "art", "research", "engineering", "general",
}


class AgentSelectionCriteria(Dict[str, Any]):
    """The selection criteria (study 13).

    capability: List[str] — any-of enabled tool slugs
    role / domain: str — curated vocabulary
    depth: "deep" | "shallow" — cognitive profile family
    provider: str
    spec: "local" | "cloud"
    collective: str — collection name (a picker FILTER, never
      a routing target — study 15)
    min_tools: int — minimum enabled tool count
    """


async def select_agents(
    db: AsyncSession,
    criteria: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Filter + rank the pool; return ARM cards (deterministic)."""
    criteria = criteria or {}
    caps = criteria.get("capability") or []
    role = criteria.get("role")
    domain = criteria.get("domain")
    depth = criteria.get("depth")
    provider = criteria.get("provider")
    spec = criteria.get("spec")
    collective = criteria.get("collective")
    min_tools = criteria.get("min_tools")

    agents = (await db.execute(select(Agent).where(Agent.deleted_at.is_(None)))).scalars().all()

    results = []
    for agent in agents:
        # enabled tool slugs + count (the capability axis)
        tool_rows = (
            await db.execute(
                select(Tool.slug, Tool.capability)
                .join(AgentTool, AgentTool.tool_id == Tool.id)
                .where(
                    AgentTool.agent_id == str(agent.id),
                    AgentTool.is_enabled == True,  # noqa: E712
                )
            )
        ).all()
        enabled = {slug for slug, _ in tool_rows}
        # the canonical capability set — the SELECTION vocabulary
        # (duckduckgo/tavily both provide web-search; the criterion
        # matches the CAPABILITY, not the provider slug)
        capabilities = {cap for _, cap in tool_rows if cap}

        # collective memberships
        from app.domain.collections.models import Collection, CollectionItem
        coll_rows = (
            await db.execute(
                select(Collection.name)
                .join(CollectionItem, CollectionItem.collection_id == Collection.id)
                .where(
                    CollectionItem.entity_id == str(agent.id),
                    CollectionItem.entity_type == "agent",
                )
            )
        ).all()
        collectives = [r[0] for r in coll_rows]

        # tags → role/domain (the curated vocabulary)
        tags = set(agent.tags or [])
        agent_role = next((t for t in tags if t in ROLE_VOCABULARY), None)
        agent_domain = next((t for t in tags if t in DOMAIN_VOCABULARY), None)

        # depth from the cognitive profile
        agent_depth = None
        if agent.cognitive_profile_id is not None:
            from app.infrastructure.database.models import CognitiveProfile
            prof = (
                await db.execute(
                    select(CognitiveProfile.name).where(
                        CognitiveProfile.id == agent.cognitive_profile_id
                    )
                )
            ).scalar_one_or_none()
            if prof:
                agent_depth = depth_family(prof)

        # spec from the classifier
        location, _size = spec_for(agent.provider, agent.model)

        # ── filter (all AND-ed) ────────────────────────────────
        if caps:
            if not any(c in capabilities for c in caps):
                continue
        if role and agent_role != role:
            continue
        if domain and agent_domain != domain:
            continue
        if depth and agent_depth != depth:
            continue
        if provider and agent.provider != provider:
            continue
        if spec and location != spec:
            continue
        if collective and collective not in collectives:
            continue
        if min_tools and len(enabled) < min_tools:
            continue

        # the ARM card (what matched — for transparency)
        matched = []
        if caps:
            matched.append(f"capability:{','.join(caps)}")
        if role:
            matched.append(f"role:{role}")
        if domain:
            matched.append(f"domain:{domain}")
        if depth:
            matched.append(f"depth:{depth}")
        if spec:
            matched.append(f"spec:{spec}")
        if collective:
            matched.append(f"collective:{collective}")

        results.append({
            "id": str(agent.id),
            "name": agent.name,
            "role": agent_role,
            "domain": agent_domain,
            "depth": agent_depth,
            "spec": location,
            "capabilities": sorted(capabilities),
            "skills": list(agent.skills or []),
            "collectives": collectives,
            "matched_on": matched,
            "_tool_count": len(enabled),
        })

    # ── rank (deterministic, not magical) ─────────────────────
    # criteria order = priority (matched_on length), then enabled-
    # tool count, then name — stable for ARM
    def _rank_key(r: Dict[str, Any]) -> Any:
        return (
            -len(r.get("matched_on", []) or []),
            -int(r.get("_tool_count", 0) or 0),
            str(r.get("name", "")).lower(),
        )

    results.sort(key=_rank_key)
    for r in results:
        r.pop("_tool_count", None)
    return results


def depth_family(profile_name: str) -> str:
    """The deep/shallow family of a cognitive profile — THE canonical
    map (the UI chip + the agent-selection share it).

    deep: research-pro, research-std, code-gen (memory/pipeline)
    shallow: quick-response, conversational, chat-skill (fast, lean —
        chat-skill added 2026-09-06: Bob's trial profile = stateless,
        direct-yield; the profiles table itself calls it shallow)
    balanced: balanced-chat, system-admin (in-between)
    """
    deep = {"research-pro", "research-std", "code-gen"}
    shallow = {"quick-response", "conversational", "chat-skill"}
    if profile_name in deep:
        return "deep"
    if profile_name in shallow:
        return "shallow"
    return "balanced"
