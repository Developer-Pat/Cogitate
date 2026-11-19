"""The notifications test endpoint — publishes through the real bus."""

import pytest

import app.api.v1.notifications_router as notifications_router
from app.api.v1.notifications_router import NotificationsTestPayload

# the endpoint's name collides with pytest's test_* collection — call
# it through a non-test_* alias
call_test_notification = notifications_router.test_notification


@pytest.mark.asyncio
async def test_test_notification_publishes(monkeypatch):
    published = {}

    class FakePublish:
        def __init__(self, spy):
            self.spy = spy

        def __call__(self, topic, payload=None):
            self.spy["topic"] = topic
            self.spy["payload"] = payload

    monkeypatch.setattr(
        "app.domain.messaging.services.publish",
        FakePublish(published),
    )
    result = await call_test_notification(
        NotificationsTestPayload(
            title="Severe weather warning",
            message="staying put",
            type="error",
            sticky=True,
            from_="system",
        )
    )
    assert result["ok"] is True
    assert result["sticky"] is True
    assert published["topic"] == "notify:test"
    assert published["payload"]["sticky"] is True
    assert published["payload"]["type"] == "error"
    assert published["payload"]["from"] == "system"


@pytest.mark.asyncio
async def test_test_notification_rejects_bad_type():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        NotificationsTestPayload(title="x", type="loud")
