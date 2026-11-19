"""
Database configuration and session management.

Provides async SQLAlchemy engine and session factory.
Defaults to SQLite for local development, PostgreSQL for production.

NOTE: This module manages TWO databases:
1. Main app database (cogitate.db) - for agents, sessions, tools, etc.
2. Documents database (cogitate_docs_en.db) - for help documentation
"""

import logging
from collections.abc import AsyncGenerator
from sqlalchemy import event

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models (main app database)."""

    pass


class DocumentsBase(Base):
    """Base class for document database models only.

    Documents-specific models (Document, DocumentRelation, DocumentAnalytics)
    inherit from this class to isolate them from the main app schema.
    """

    __abstract__ = True


# ============================================================================
# Main Application Database
# ============================================================================

# Create async engine for main app database
if "sqlite" in settings.database_url:
    # SQLite-specific settings for better concurrency
    # THE FK PRAGMA (2026-08-24, the orphaned-messages bug): SQLite
    # does NOT enforce foreign keys by default — the declared
    # ondelete='CASCADE' on chat_messages.session_id was DEAD WEIGHT,
    # so deleting a session orphaned its messages, and the reused
    # session id later inherited the ghosts. Enabling the pragma
    # makes the declared cascades REAL (the session delete now
    # removes its messages at the SQLite level).
    engine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,  # Wait up to 30 seconds for locks
        },
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,   # Recycle connections after 1 hour
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_fk_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

# Create async session factory for main app
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ============================================================================
# Documents Database (Separate)
# ============================================================================

# Get documents database URL from settings (with fallback)
# The fallback was a cwd-relative path (`./data/...`), which resolves against
# whatever directory the process was started in — the phantom-path class this
# codebase has been bitten by before. Resolved through `Paths` instead.
def _documents_db_url() -> str:
    explicit = getattr(settings, "documents_database_url", None)
    if explicit:
        return str(explicit)
    from app.core.config import Paths as _Paths

    return f"sqlite+aiosqlite:///{_Paths.from_settings(settings).data_dir / 'cogitate_docs_en.db'}"


documents_db_url = _documents_db_url()

# Create async engine for documents database
if "sqlite" in documents_db_url:
    documents_engine = create_async_engine(
        documents_db_url,
        echo=settings.db_echo,
        connect_args={
            "check_same_thread": False,
            "timeout": 30,
        },
        pool_pre_ping=True,
        pool_recycle=3600,
    )
else:
    documents_engine = create_async_engine(
        documents_db_url,
        echo=settings.db_echo,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

# Create async session factory for documents
DocumentsSessionLocal = async_sessionmaker(
    bind=documents_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ═══════════════════════════════════════════════════════════════════════════════
# DIAGNOSTIC HELPERS  (added for IllegalStateChangeError investigation)
# ═══════════════════════════════════════════════════════════════════════════════

def _session_state_str(session: AsyncSession) -> str:
    """Return a debug string with the session's internal transaction state."""
    try:
        sync_session = getattr(session, "sync_session", None)
        if sync_session is None:
            return "no_sync_session"
        txn = getattr(sync_session, "_transaction", None)
        txn_state = (
            str(txn._state)
            if txn is not None and hasattr(txn, "_state")
            else "no_transaction"
        )
        close_state = getattr(sync_session, "_close_state", None)
        return f"txn_state={txn_state}, close_state={close_state}"
    except Exception:
        return "state_inspect_failed"


# ═══════════════════════════════════════════════════════════════════════════════
# Session Dependency Generators
# ═══════════════════════════════════════════════════════════════════════════════

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session for main app.

    Yields:
        AsyncSession: Database session instance

    Example:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            logger.debug(
                "get_db_session: committing — %s",
                _session_state_str(session),
            )
            await session.commit()
        except Exception:
            logger.warning(
                "get_db_session: commit failed, rolling back — %s",
                _session_state_str(session),
                exc_info=True,
            )
            try:
                await session.rollback()
            except Exception as rb_exc:
                logger.critical(
                    "get_db_session: rollback ALSO failed — %s, rollback_error=%s",
                    _session_state_str(session),
                    rb_exc,
                    exc_info=True,
                )
            raise
        finally:
            logger.debug(
                "get_db_session: closing — %s",
                _session_state_str(session),
            )
            await session.close()


async def get_documents_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency that provides a database session for documents.

    Yields:
        AsyncSession: Documents database session instance

    Example:
        @router.get("/documents")
        async def get_documents(db: AsyncSession = Depends(get_documents_session)):
            ...
    """
    async with DocumentsSessionLocal() as session:
        try:
            yield session
            logger.debug(
                "get_documents_session: committing — %s",
                _session_state_str(session),
            )
            await session.commit()
        except Exception:
            logger.warning(
                "get_documents_session: commit failed, rolling back — %s",
                _session_state_str(session),
                exc_info=True,
            )
            try:
                await session.rollback()
            except Exception as rb_exc:
                logger.critical(
                    "get_documents_session: rollback ALSO failed — "
                    "%s, rollback_error=%s",
                    _session_state_str(session),
                    rb_exc,
                    exc_info=True,
                )
            raise
        finally:
            logger.debug(
                "get_documents_session: closing — %s",
                _session_state_str(session),
            )
            await session.close()




async def init_db() -> None:
    """
    Initialize main application database tables.

    Creates all tables defined in the models if they don't exist.
    """

    # Import models so they're registered with the Base metadata
    from app.infrastructure.database.models import (  # noqa: F401
        Agent,
        ChatMessage,
        ChatSession,
        FrontendAgentPackage,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Main database tables created/verified")

    # THE STRUCTURE SEED (2026-11-18): the capability ROWS — never their values.
    # A fresh install had none (they only ever existed because a developer made
    # them by hand), and a missing row defaults to kind=llm, which let
    # `embeddings` inherit the chat default provider. Idempotent: a warm install
    # creates nothing.
    from app.infrastructure.database import get_db_session
    from app.domain.providers.capabilities import ensure_capability_rows

    async for session in get_db_session():
        created = await ensure_capability_rows(session)
        if created:
            logger.info("Capability rows seeded: %s", ", ".join(created))
        break


async def init_documents_db() -> None:
    """
    Initialize documents database tables.

    Creates all tables defined in the DocumentsBase models if they don't exist.
    """

    # Import document models (order matters: base tables before relations)
    from app.infrastructure.database.models import (  # noqa: F401
        Document,
        DocumentAnalytics,
        DocumentRelation,
    )

    async with documents_engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(DocumentsBase.metadata.create_all)

    logger.info("Documents database tables created/verified")


async def close_db() -> None:
    """
    Dispose all database engines on application shutdown.

    Should be called from the application's shutdown event handler.
    """
    await engine.dispose()
    await documents_engine.dispose()
