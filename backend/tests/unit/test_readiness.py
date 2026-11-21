"""The readiness verdict — the one thing both screens render.

What these defend:

- a FRESH install reads as unconfigured: no provider, no chat model, and the agents item is
  BLOCKED (the user cannot act yet) rather than "pick a profile" at a page with no profiles;
- the optional runtime item is never counted, so a stranger is never told to install Exa's
  runtime to make the app answer;
- once a dialable provider and a chat model resolve, those two items go `ok` on their own.
"""

from sqlalchemy import delete

from app.domain.providers import readiness
from app.infrastructure.database.models import Agent, Capability, Provider


def _item(report: readiness.ReadinessReport, key: str) -> readiness.ReadinessItem:
    item = report.item(key)
    assert item is not None, f"no readiness item {key!r} — the report lost one"
    return item


async def _bare(db) -> None:
    """Delete what a "fresh install" means here, instead of inheriting it.

    The test database is shared and persisted between runs (measured: six provider rows
    survived into a test that assumed none), so every test below names its own starting
    point — the same discipline the setup-offers tests had to adopt.
    """
    for model in (Agent, Provider, Capability):
        await db.execute(delete(model))
    await db.commit()


async def test_a_fresh_install_reads_as_unconfigured(test_session):
    await _bare(test_session)
    report = await readiness.measure(test_session)

    assert report.ready is False
    assert report.remaining == 3, "provider, chat model and agents are all still owed"

    assert _item(report, "provider").state == readiness.UNMET
    assert "No provider yet" in _item(report, "provider").detail

    assert _item(report, "chat").state == readiness.UNMET

    agents = _item(report, "agents")
    assert agents.state == readiness.BLOCKED, (
        "with no chat model the seed is waiting — the copy must not ask the user to pick a "
        "profile that cannot exist yet"
    )
    assert "once a chat model resolves" in agents.detail

    runtime = _item(report, "runtime")
    assert runtime.counted is False, "Exa is a decision, not a requirement"
    assert runtime.state in (readiness.OPTIONAL, readiness.OK)


async def test_a_model_that_carries_its_own_prefix_is_not_prefixed_twice(test_session):
    """The chat detail is the string the route module builds — not `provider/model`.

    Measured on a live install: `deepseek/~deepseek/deepseek-v4-flash-latest answers chat`. The
    row's model already carried its handler, and the detail glued the provider on again.
    """
    await _bare(test_session)
    test_session.add(
        Provider(
            name="Deepseek",
            display_name="Deepseek",
            provider_type="deepseek",
            base_url="https://api.deepseek.com",
            is_active=True,
            is_default=True,
            config={"default_model": "~deepseek/deepseek-v4-flash-latest"},
        )
    )
    await test_session.commit()

    report = await readiness.measure(test_session)
    chat = _item(report, "chat")
    assert chat.state == readiness.OK

    assert chat.detail.startswith("~deepseek/deepseek-v4-flash-latest answers chat"), chat.detail
    assert "deepseek/~deepseek/" not in chat.detail


async def test_a_dialable_provider_and_a_chat_model_turn_both_items_ok(test_session):
    await _bare(test_session)
    test_session.add(
        Provider(
            name="llama",
            display_name="Llama",
            provider_type="llama",
            # loopback, so `_is_dialable` holds without a key on this machine or in its .env
            base_url="http://localhost:11434",
            is_active=True,
            is_default=True,
            config={"default_model": "llama3.2"},
        )
    )
    await test_session.commit()

    report = await readiness.measure(test_session)

    assert _item(report, "provider").state == readiness.OK
    assert _item(report, "chat").state == readiness.OK, (
        "a default row carrying config.default_model is what the resolver's last rung reads"
    )
    assert _item(report, "agents").state == readiness.UNMET, (
        "the model answers and no agents exist — the message must say to restart, not wait"
    )
    assert report.remaining == 1
