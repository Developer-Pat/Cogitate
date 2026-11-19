"""Agent tool grants (Phase C — the keyed tier).

The grant is the access object for KEYED tools: an agent may
execute a keyed tool only when a grant exists. The slug stays
identity; the grant is separate access (study 11).

granted_by: user | exa | system
scope: session | permanent | run:<workflow_id>
expires_at: NULL = permanent; session/run grants expire
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# Import team_tools first: the Tool model's relationship to
# TeamTool is a string reference resolved at mapper configuration —
# importing models alone raises "failed to locate a name".
from app.domain.tools import team_tools  # noqa: F401  (mapper resolution)
from app.domain.tools.models import AgentToolGrant


def _norm_uuid(value: str) -> str:
    """Normalize a UUID string to the hyphenated canonical form.

    The runtime's tool_def.id is hyphenated (SQLAlchemy UUID type);
    raw sqlite3 reads return hyphen-less. Grants are keyed by the
    hyphenated form so the execution-path lookup always matches.
    """
    v = value.strip()
    if "-" not in v and len(v) == 32:
        return f"{v[:8]}-{v[8:12]}-{v[12:16]}-{v[16:20]}-{v[20:]}"
    return v

logger = logging.getLogger(__name__)


class AgentToolGrantService:
    """CRUD + query for agent tool grants."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def has_grant(
        self,
        agent_id: str,
        tool_id: str,
        scopes: Optional[List[str]] = None,
    ) -> bool:
        """True if the agent holds a live grant for the tool.

        A grant is live when its scope is in the requested scopes
        (default: any) and it has not expired. Expired rows are
        ignored (and lazily cleaned by revoke_expired).
        """
        stmt = select(AgentToolGrant).where(
            AgentToolGrant.agent_id == str(agent_id),
            AgentToolGrant.tool_id == _norm_uuid(tool_id),
        )
        if scopes is not None:
            stmt = stmt.where(AgentToolGrant.scope.in_(scopes))
        rows = (await self.db.execute(stmt)).scalars().all()
        now = datetime.now(timezone.utc)
        for g in rows:
            exp = g.expires_at
            if exp is None:
                return True
            # the test DB stores naive datetimes; treat them as UTC
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now:
                return True
        return False

    async def grant(
        self,
        agent_id: str,
        tool_id: str,
        granted_by: str = "user",
        scope: str = "permanent",
        expires_at: Optional[datetime] = None,
    ) -> AgentToolGrant:
        """Issue a grant (idempotent per agent/tool/scope)."""
        existing = (
            await self.db.execute(
                select(AgentToolGrant).where(
                    AgentToolGrant.agent_id == str(agent_id),
                    AgentToolGrant.tool_id == _norm_uuid(tool_id),
                    AgentToolGrant.scope == scope,
                )
            )
        ).scalars().first()
        if existing:
            existing.granted_by = granted_by
            existing.expires_at = expires_at
            self.db.add(existing)
            await self.db.commit()
            return existing
        grant = AgentToolGrant(
            id=str(uuid4()),
            agent_id=str(agent_id),
            tool_id=_norm_uuid(tool_id),
            granted_by=granted_by,
            scope=scope,
            expires_at=expires_at,
        )
        self.db.add(grant)
        await self.db.commit()
        await self.db.refresh(grant)
        return grant

    async def revoke(
        self,
        agent_id: str,
        tool_id: str,
        scope: Optional[str] = None,
    ) -> int:
        """Revoke grants for an agent+tool (optionally one scope)."""
        stmt = delete(AgentToolGrant).where(
            AgentToolGrant.agent_id == str(agent_id),
            AgentToolGrant.tool_id == _norm_uuid(tool_id),
        )
        if scope:
            stmt = stmt.where(AgentToolGrant.scope == scope)
        result = await self.db.execute(stmt)
        await self.db.commit()
        # DELETE results expose rowcount on the underlying cursor
        return int(getattr(result, "rowcount", 0) or 0)

    async def grants_for_agent(self, agent_id: str) -> List[AgentToolGrant]:
        """All grants an agent holds."""
        rows = (
            await self.db.execute(
                select(AgentToolGrant).where(
                    AgentToolGrant.agent_id == str(agent_id)
                )
            )
        ).scalars().all()
        return list(rows)

    async def revoke_expired(self) -> int:
        """Delete expired grants (the lazy cleanup)."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            delete(AgentToolGrant).where(AgentToolGrant.expires_at < now)
        )
        await self.db.commit()
        return int(getattr(result, "rowcount", 0) or 0)
