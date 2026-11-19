"""Adding a message touches the session's updated_at, which the session panel sorts by.

add_message must touch the session.updated_at — the session panel
sorts by it, and before the fix only title-generation moved it, so
a session with fresh messages never rose to the top.
"""

import pytest

from app.domain.sessions.services import SessionService
from app.domain.sessions.schemas import SessionCreate


class FakeDb:
    """The minimal AsyncSession surface the service uses."""

    def __init__(self):
        self.added = []
        self.committed = False

    async def get(self, model, session_id):
        if model.__name__ == "ChatSession":
            session = _Session(session_id)
            self._session = session
            return session
        return None

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self.committed = True

    async def refresh(self, obj):
        pass


class _Session:
    def __init__(self, session_id):
        self.id = session_id
        self.updated_at = None


def _model_stub():
    import types
    stub = types.ModuleType("stub")
    return stub


@pytest.mark.asyncio
async def test_add_message_touches_updated_at(monkeypatch):
    from datetime import datetime
    from app.infrastructure.database import models

    db = FakeDb()
    service = SessionService(db)

    before = datetime(2026, 1, 1)
    db._session = _Session(99)
    db._session.updated_at = before

    # Patch the ChatMessage model constructor to return a stub
    class FakeMessage:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    monkeypatch.setattr(models, "ChatMessage", FakeMessage)

    await service.add_message(99, "user", "hi")

    assert db.committed
    assert db._session.updated_at is not None
    assert db._session.updated_at > before
    assert db.added, "the message must be staged"
