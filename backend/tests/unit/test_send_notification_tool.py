"""The send_notification tool — its payload shape and its validation.

The purpose-built announcement surface: what an agent calls to say something
reaches the user as a notification.
"""

import pytest

from app.domain.tools.builtin.send_notification_handler import (
    SendNotificationTool,
)


@pytest.fixture
def tool():
    return SendNotificationTool()


@pytest.mark.asyncio
async def test_publishes_the_notification_shape(tool, monkeypatch):
    published = {}

    def fake_publish(topic, payload=None):
        published["topic"] = topic
        published["payload"] = payload

    monkeypatch.setattr("app.domain.messaging.services.publish", fake_publish)

    result = await tool.execute(
        title="The workflow finished",
        message="12 rows processed",
        type="success",
        sticky=True,
    )
    assert result["success"] is True
    assert result["type"] == "success"
    assert published["topic"] == "notify:exa"
    assert published["payload"]["title"] == "The workflow finished"
    assert published["payload"]["type"] == "success"
    assert published["payload"]["sticky"] is True
    assert published["payload"]["from"] == "exa"
    assert published["payload"]["kind"] == "exa-notification"


@pytest.mark.asyncio
async def test_rejects_missing_title(tool):
    result = await tool.execute(message="no title")
    assert result["success"] is False
    assert "title" in result["error"]


@pytest.mark.asyncio
async def test_rejects_bad_type(tool):
    result = await tool.execute(title="x", type="loud")
    assert result["success"] is False
    assert "type" in result["error"]


@pytest.mark.asyncio
async def test_defaults_info_and_non_sticky(tool, monkeypatch):
    published = {}

    def fake_publish(topic, payload=None):
        published["payload"] = payload

    monkeypatch.setattr("app.domain.messaging.services.publish", fake_publish)

    await tool.execute(title="quiet note")
    assert published["payload"]["type"] == "info"
    assert published["payload"]["sticky"] is False


@pytest.mark.asyncio
async def test_publishes_the_action_link(tool, monkeypatch):
    published = {}

    def fake_publish(topic, payload=None):
        published["payload"] = payload

    monkeypatch.setattr("app.domain.messaging.services.publish", fake_publish)

    result = await tool.execute(
        title="Talk to me",
        message="The workflow finished — come check the results.",
        type="success",
        link="/exa",
        link_label="Talk to me",
    )
    assert result["success"] is True
    assert result["link"] == "/exa"
    assert published["payload"]["action"] == {"label": "Talk to me", "href": "/exa"}


@pytest.mark.asyncio
async def test_link_label_defaults_to_open(tool, monkeypatch):
    published = {}

    def fake_publish(topic, payload=None):
        published["payload"] = payload

    monkeypatch.setattr("app.domain.messaging.services.publish", fake_publish)

    await tool.execute(title="x", link="/messages")
    assert published["payload"]["action"] == {"label": "Open", "href": "/messages"}


@pytest.mark.asyncio
async def test_rejects_unsafe_link(tool):
    result = await tool.execute(title="x", link="javascript:alert(1)")
    assert result["success"] is False
    assert "link" in result["error"]
