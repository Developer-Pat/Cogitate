"""EXA SHIPS INACTIVE (2026-11-18, the user's ruling).

Exa is INCLUDED in the box and NOT running in it: a fresh install has no
runtime and no key, and nothing is spawned. Activating it is the user's
decision, and every surface that reaches it before that answers with STATE —
"not active" — never with a failed spawn.

The distinction the tests defend: `enabled` is the decision, `runnable` is
whether this machine can honour it, and neither one is allowed to be guessed.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.v1.external_agent_router as rtr
from app.api.v1.external_agent_router import (
    activate_external_agent,
    deactivate_external_agent,
    router as external_agent_router,
)
from app.domain.external_agent import (
    AcpClient,
    ExternalAgentConfig,
    ExternalAgentInactive,
    get_config,
    probe_runnable,
    save_config,
)

app = FastAPI()
app.include_router(external_agent_router)


# ── the decision ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fresh_install_is_inactive(test_session):
    """No settings row = a fresh install = Exa present and switched OFF."""
    from sqlalchemy import delete

    from app.infrastructure.database.models import UserSettings

    await test_session.execute(delete(UserSettings))
    await test_session.commit()
    assert (await get_config(test_session)).enabled is False


@pytest.mark.asyncio
async def test_activation_survives_the_round_trip(test_session):
    """The decision is PERSISTED, both directions — an activation that lived
    only in memory would come back off on the next backend start."""
    base = await get_config(test_session)

    await save_config(test_session, base.model_copy(update={"enabled": True}))
    assert (await get_config(test_session)).enabled is True

    await save_config(test_session, base.model_copy(update={"enabled": False}))
    assert (await get_config(test_session)).enabled is False


@pytest.mark.asyncio
async def test_a_config_write_does_not_silently_reset_the_activation(test_session):
    """The PUT-merge trap (the budget fields' own incident): a field left out of
    the explicit construction is validated and then reset to its default."""
    base = await get_config(test_session)
    await save_config(test_session, base.model_copy(update={"enabled": True}))

    updated = await rtr.update_external_agent_config(
        rtr.ExternalAgentConfigUpdate(command="hermes acp"), db=test_session
    )
    assert updated.enabled is True


# ── the refusal ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_refuses_before_spawning_anything():
    """The gate fires BEFORE a subprocess exists: a de-activated Exa costs no
    process and no traceback from a binary that was never installed."""
    client = AcpClient(command=["definitely-not-installed", "acp"], enabled=False)
    with pytest.raises(ExternalAgentInactive):
        await client.start()
    assert client.connected is False


def test_probe_names_what_is_missing():
    """`runnable` is a PROBE, so the refusal can name the absent runtime rather
    than leaving a dead switch."""
    reason = probe_runnable(ExternalAgentConfig(command="definitely-not-installed acp"))
    assert reason is not None
    assert "definitely-not-installed" in reason


def test_probe_is_quiet_when_the_binary_exists():
    assert probe_runnable(ExternalAgentConfig(command="sh")) is None


# ── the surfaces ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_reports_whether_this_box_can_run_it(test_session, monkeypatch):
    """Activation is the user's call, not a capability test — but the answer
    carries the probe so a page can say WHY nothing answers, and the
    provisioning log so it can say what the switch DID.

    Provisioning is stubbed: the real one writes into the install's own
    `.hermes`, and a test may not touch the repo (`test_exa_activation.py`
    covers the real sequence on a tmp home).
    """
    from app.domain.external_agent import activation

    calls: list[dict] = []

    def fake_provision(**kwargs):
        calls.append(kwargs)
        return ["skills seeded into .hermes/skills/cogitate (2 file(s) added)"]

    monkeypatch.setattr(activation, "provision_home", fake_provision)

    result = await activate_external_agent(db=test_session)
    assert calls, "activation must provision the home"
    assert result["enabled"] is True
    assert result["runnable"] is (result["blocked_reason"] is None)
    # the seeded lines AND the decision, in the order the sequence took them
    assert result["provisioned"] == [
        "skills seeded into .hermes/skills/cogitate (2 file(s) added)",
        "activated: Exa will spawn on the next chat",
    ]
    assert set(result) == {"enabled", "runnable", "blocked_reason", "provisioned"}

    off = await deactivate_external_agent(db=test_session)
    assert off["enabled"] is False
    assert set(off) == {"enabled", "runnable", "blocked_reason"}


@pytest.mark.asyncio
async def test_a_home_that_cannot_be_provisioned_is_not_activated(test_session, monkeypatch):
    """The decision is taken LAST: a switch whose provisioning failed must not
    come back on, or the user gets an agent with no identity and no explanation."""
    from fastapi import HTTPException

    from app.domain.external_agent import activation

    def boom(**kwargs):
        raise PermissionError("read-only home")

    monkeypatch.setattr(activation, "provision_home", boom)

    with pytest.raises(HTTPException) as exc:
        await activate_external_agent(db=test_session)
    assert exc.value.status_code == 500
    assert "read-only home" in exc.value.detail
    assert (await get_config(test_session)).enabled is False


def test_ws_answers_inactive_instead_of_spawning(monkeypatch):
    """A de-activated Exa answers the panel with its state, and no subprocess
    is created (the client would fail loudly if one were)."""

    async def fake_db():
        yield object()

    async def inactive_config(_db):
        return ExternalAgentConfig(enabled=False)

    async def no_spawn(*_a, **_k):
        raise AssertionError("nothing may spawn while Exa is inactive")

    monkeypatch.setattr(rtr, "_db", fake_db)
    monkeypatch.setattr(rtr, "get_config", inactive_config)
    monkeypatch.setattr(rtr, "get_acp_client", no_spawn)

    with TestClient(app).websocket_connect("/external-agent/ws") as ws:
        msg = ws.receive_json()
    assert msg["type"] == "status"
    assert msg["status"] == "inactive"
    assert "not active" in msg["message"].lower()


def test_ws_fails_closed_when_the_config_cannot_be_read(monkeypatch):
    """An unreadable config is NOT permission to spawn — the failure mode of
    guessing is an agent the user never activated, with its tools."""

    async def broken_db():
        raise RuntimeError("no database")
        yield  # pragma: no cover — makes this an async generator

    async def no_spawn(*_a, **_k):
        raise AssertionError("nothing may spawn without a readable activation decision")

    monkeypatch.setattr(rtr, "_db", broken_db)
    monkeypatch.setattr(rtr, "get_acp_client", no_spawn)

    with TestClient(app).websocket_connect("/external-agent/ws") as ws:
        msg = ws.receive_json()
    assert msg["status"] == "inactive"
