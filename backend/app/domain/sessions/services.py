"""
Session domain service.

Business logic for session management.
"""

import logging
from typing import Optional, List
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.domain.sessions.schemas import SessionCreate, SessionUpdate
from app.infrastructure.database.models import ChatMessage, ChatSession

logger = logging.getLogger(__name__)


class SessionService:
    """
    Service for session business logic.

    Handles CRUD operations for chat sessions.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize session service.

        Args:
            db: Async database session
        """
        self.db = db

    async def list_all(
        self, skip: int = 0, limit: int = 100,
        agent_id: Optional[int] = None,
        unnamed_only: bool = False,
        source: Optional[str] = None,
    ) -> tuple[List[ChatSession], int]:
        """
        List all sessions with pagination and optional filters.

        Args:
            skip: Number of records to skip
            limit: Maximum records to return
            agent_id: If set, only return sessions for this agent
            unnamed_only: If True, only return sessions with no title
            source: If set ('agent' | 'exa'), only return sessions
                from that surface (2026-09-04, the exa-leak dig —
                the agent page was listing Exa's sessions too).

        Returns:
            Tuple of (sessions list, total count)
        """
        # Build base conditions
        conditions = []
        if agent_id is not None:
            conditions.append(ChatSession.agent_id == agent_id)
        if source is not None:
            conditions.append(ChatSession.source == source)
        if unnamed_only:
            conditions.append(
                (ChatSession.title.is_(None))
                | (ChatSession.title == "")
                | (ChatSession.title == "None")
                | (ChatSession.title.like("New Session %"))
            )

        # Get total count
        count_query = select(func.count()).select_from(ChatSession)
        if conditions:
            count_query = count_query.where(*conditions)
        total_raw = await self.db.scalar(count_query)
        total: int = total_raw if total_raw is not None else 0

        # Get sessions
        query = (
            select(ChatSession)
            .order_by(ChatSession.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if conditions:
            query = query.where(*conditions)
        result = await self.db.execute(query)
        sessions = list(result.scalars().all())

        return sessions, total

    async def message_counts(self, session_ids: list[int]) -> dict[int, int]:
        """Count messages per session, for a batch of session ids, in ONE query.

        WHY THIS EXISTS (2026-09-15): the sessions list is deliberately
        titles-only — `list_sessions` returns `messages=[]` on the fast path —
        so the frontend had NO count to show and fell back to reading
        `session.messages.length`, which is lazily loaded. That made the eye
        button's toast report 0 for every session you had not opened, and a
        STALE count for the one you had (the user: "I deleted all the messages
        and it still shows 96"). The count has to come from the database, and
        it has to be one query rather than a lazy load per row.

        Args:
            session_ids: The session ids to count for. Empty is a no-op.

        Returns:
            {session_id: message_count}, with 0 for ids that have no messages.
        """
        if not session_ids:
            return {}
        query = (
            select(ChatMessage.session_id, func.count(ChatMessage.id))
            .where(ChatMessage.session_id.in_(session_ids))
            .group_by(ChatMessage.session_id)
        )
        result = await self.db.execute(query)
        # Seed every requested id with 0: a session with no messages has no
        # row in the GROUP BY result, and a missing key would read as "unknown"
        # rather than "zero" at the call site.
        return {sid: 0 for sid in session_ids} | {sid: int(n) for sid, n in result.all()}

    async def get_by_id(self, session_id: int) -> Optional[ChatSession]:
        """
        Get session by ID.

        Args:
            session_id: Session ID

        Returns:
            Session if found, None otherwise
        """
        query = select(ChatSession).where(ChatSession.id == session_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def create(self, session_data: SessionCreate) -> ChatSession:
        """
        Create a new session.

        Args:
            session_data: Session creation data

        Returns:
            Created session
        """
        # Set default title if not provided (prevents null titles)
        title = session_data.title if session_data.title is not None else "New Session"
        
        session = ChatSession(
            agent_id=session_data.agent_id,
            title=title,
            source=session_data.source,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)

        logger.info(f"Created session {session.id} for agent {session.agent_id}")
        return session

    async def add_message(
        self, session_id: int, role: str, content: str
    ) -> ChatMessage:
        """Append a message to a session (the Exa bridge's save path)."""
        session = await self.db.get(ChatSession, session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")
        msg = ChatMessage(session_id=session_id, role=role, content=content)
        self.db.add(msg)
        # THE LAST-ACTIVITY TOUCH (2026-09-09, the sort fix — B1):
        # the session list sorts by updated_at, which only moved on
        # title-generation before; a session with fresh messages now
        # rises to the top of the panel.
        session.updated_at = datetime.now()
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def update(
        self, session_id: int, session_data: SessionUpdate
    ) -> Optional[ChatSession]:
        """
        Update an existing session.

        Args:
            session_id: Session ID
            session_data: Session update data

        Returns:
            Updated session if found, None otherwise
        """
        session = await self.get_by_id(session_id)
        if not session:
            return None

        update_data = session_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(session, field, value)

        await self.db.flush()
        await self.db.refresh(session)

        logger.info(f"Updated session {session_id}")
        return session

    async def count_all(self) -> int:
        """Return total session count."""
        count_query = select(func.count()).select_from(ChatSession)
        raw = await self.db.scalar(count_query)
        return raw if raw is not None else 0

    async def bulk_delete(self, session_ids: list[int]) -> int:
        """Delete multiple sessions by ID in a single query."""
        from sqlalchemy import delete as sa_delete
        logger = logging.getLogger(__name__)
        logger.info("bulk_delete service: ids=%s", session_ids)
        # THE ORPHAN FIX (2026-08-24): the messages die with their
        # sessions (see delete() — same rationale).
        if session_ids:
            await self.db.execute(
                sa_delete(ChatMessage).where(ChatMessage.session_id.in_(session_ids))
            )
        stmt = sa_delete(ChatSession).where(ChatSession.id.in_(session_ids))
        result = await self.db.execute(stmt)
        count = getattr(result, "rowcount", None) or 0
        logger.info("bulk_delete service: deleted=%d", count)
        return count

    async def delete(self, session_id: int) -> bool:
        """
        Delete a session.

        The caller's dependency generator will commit the transaction,
        so we avoid an explicit flush here to prevent IllegalStateChangeError
        when this method is called in a loop (e.g. delete_all_sessions).

        Args:
            session_id: Session ID

        Returns:
            True if deleted, False if not found
        """
        session = await self.get_by_id(session_id)
        if not session:
            return False

        # THE ORPHAN FIX (2026-08-24, the ghost-history bug): the
        # session's messages must die WITH the session. The FK
        # cascade (ondelete='CASCADE') now fires via the FK pragma,
        # but this explicit delete is the belt-and-suspenders — a
        # deleted session must NEVER leave orphaned messages behind
        # (they collide with the reused session id later).
        from sqlalchemy import delete as sa_delete
        await self.db.execute(
            sa_delete(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        await self.db.delete(session)

        logger.info(f"Deleted session {session_id}")
        return True

    async def clear_all(self) -> int:
        """
        Delete ALL sessions.

        Returns:
            Number of sessions deleted.
        """
        sessions, total = await self.list_all(skip=0, limit=100000)
        count = len(sessions)

        for session in sessions:
            await self.db.delete(session)

        await self.db.flush()

        logger.info(f"Cleared all sessions — deleted {count} sessions")
        return count

    async def search_by_title(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> tuple[List[ChatSession], int]:
        """
        Search sessions by title using a case-insensitive LIKE query.

        Args:
            query: Search string to match against session titles
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            Tuple of (matching sessions list, total count)
        """
        search_pattern = f"%{query}%"

        # Get total count
        count_query = (
            select(func.count())
            .select_from(ChatSession)
            .where(ChatSession.title.ilike(search_pattern))
        )
        total_raw = await self.db.scalar(count_query)
        total: int = total_raw if total_raw is not None else 0

        # Get matching sessions
        query_stmt = (
            select(ChatSession)
            .where(ChatSession.title.ilike(search_pattern))
            .order_by(ChatSession.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query_stmt)
        sessions = list(result.scalars().all())

        return sessions, total

    async def get_agent_sessions(
        self, agent_id: int, skip: int = 0, limit: int = 100
    ) -> tuple[List[ChatSession], int]:
        """
        Get all sessions for a specific agent.

        Args:
            agent_id: Agent ID
            skip: Number of records to skip
            limit: Maximum records to return

        Returns:
            Tuple of (sessions list, total count)
        """
        # Get total count for this agent
        count_query = select(func.count()).where(ChatSession.agent_id == agent_id)
        total_raw = await self.db.scalar(count_query)
        total: int = total_raw if total_raw is not None else 0

        # Get sessions
        query = (
            select(ChatSession)
            .where(ChatSession.agent_id == agent_id)
            .order_by(ChatSession.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self.db.execute(query)
        sessions = list(result.scalars().all())

        return sessions, total
