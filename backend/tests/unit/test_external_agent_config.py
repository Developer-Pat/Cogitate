"""External agent config — persistence + command parsing."""

REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root

import pytest

from app.domain.external_agent import (
    ExaBrain,
    ExternalAgentConfig,
    command_parts,
    get_config,
    save_config,
)
from app.infrastructure.database.models import UserSettings


@pytest.mark.asyncio
async def test_default_config_when_no_settings(test_session):
    # ESTABLISH the empty state; do not assume it. The test database is a copy
    # of a real installation, so it carries that installation's saved settings -
    # and this test then asserts the DEVELOPER's configuration instead of the
    # defaults. Clearing the row makes the assertion mean what it says.
    from sqlalchemy import delete

    await test_session.execute(delete(UserSettings))
    await test_session.commit()
    cfg = await get_config(test_session)
    assert cfg.command == "hermes acp"
    assert cfg.cwd == ""
    # fix-mode grant defaults OFF (read-only first; fix = explicit grant)
    assert cfg.fix_mode is False


@pytest.mark.asyncio
async def test_fix_mode_grant_roundtrip(test_session):
    # the TIER is the truth (2026-08-21); fix_mode is the derived
    # compat view (True == the fix tier)
    saved = await save_config(test_session, ExternalAgentConfig(command="hermes acp", cwd="", permission_tier="fix"))
    assert saved.permission_tier == "fix"
    assert saved.fix_mode is True  # the derived view
    loaded = await get_config(test_session)
    assert loaded.permission_tier == "fix"
    assert loaded.fix_mode is True
    # and it can be revoked (back to the chat tier)
    await save_config(test_session, ExternalAgentConfig(command="hermes acp", cwd="", permission_tier="chat"))
    assert (await get_config(test_session)).permission_tier == "chat"
    assert (await get_config(test_session)).fix_mode is False


@pytest.mark.asyncio
async def test_save_then_load_roundtrip(test_session):
    saved = await save_config(test_session, ExternalAgentConfig(command="openclaw acp", cwd="/tmp/agent"))
    assert saved.command == "openclaw acp"
    loaded = await get_config(test_session)
    assert loaded.command == "openclaw acp"
    assert loaded.cwd == "/tmp/agent"


@pytest.mark.asyncio
async def test_ignores_unknown_keys_in_blob(test_session):
    # simulate a settings blob with extra keys — only command/cwd kept
    from sqlalchemy import select
    row = UserSettings(user_key="default", settings={"external_agent": {"command": "hermes acp", "cwd": "", "bogus": 1}})
    test_session.add(row)
    await test_session.commit()
    cfg = await get_config(test_session)
    assert cfg.command == "hermes acp"
    assert cfg.cwd == ""


@pytest.mark.asyncio
async def test_the_brain_list_is_config_default_data(test_session):
    """THE EXA QUICK-SWITCH IS CONFIG, NOT BUNDLE CODE (2026-10-10, the service-literals arc).

    The four tested brains used to be a `const` in `AgentIntegration.tsx`, so changing which
    brains the page offered meant editing and rebuilding the frontend. They are the config
    field's own default now — served by `GET /config` and replaceable by `PUT /config`, so a
    model swap is a config write, not a build.
    """
    from sqlalchemy import delete

    await test_session.execute(delete(UserSettings))
    await test_session.commit()

    cfg = await get_config(test_session)

    assert [b.model for b in cfg.brains] == [
        "deepseek/deepseek-v4-flash",
        "deepseek/deepseek-v4-flash-vision-exp",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "google/gemini-3.1-flash-lite",
    ]
    # the vision flag is part of the data (the page's second dropdown filters on it)
    assert [b.model for b in cfg.brains if b.vision] == [
        "deepseek/deepseek-v4-flash-vision-exp",
        "google/gemini-3.1-flash-lite",
    ]


@pytest.mark.asyncio
async def test_a_replaced_brain_list_survives_the_roundtrip(test_session):
    """`get_config` keeps a WHITELIST of keys — a field it forgets does not fail, it silently
    reverts to the default on the next read."""
    brains = [
        ExaBrain(
            label="Only one",
            model="some-vendor/some-model",
            provider="openrouter",
            base_url="https://example.invalid/v1",
        )
    ]
    await save_config(
        test_session, ExternalAgentConfig(command="hermes acp", cwd="", brains=brains)
    )

    loaded = await get_config(test_session)

    assert [b.model for b in loaded.brains] == ["some-vendor/some-model"]
    assert loaded.brains[0].label == "Only one"
    assert loaded.brains[0].vision is False, "the flag defaults off, not missing"


def test_command_parts_splits_shlex():
    assert command_parts("hermes acp") == ["hermes", "acp"]
    assert command_parts("openclaw --debug acp") == ["openclaw", "--debug", "acp"]
    assert command_parts("") == ["hermes", "acp"]



@pytest.mark.asyncio
async def test_config_update_carries_the_brain_list_over(monkeypatch):
    """THE SAME PUT-MERGE TRAP the budget fields fell into (2026-09-08): the update handler
    builds the new config EXPLICITLY, so a field it omits is validated and then silently reset
    to its default by the next write. Saving the cwd must not put the four shipped brains back.
    """
    from app.api.v1.external_agent_router import update_external_agent_config
    from app.domain.external_agent.schemas import ExternalAgentConfigUpdate

    chosen = [
        ExaBrain(label="Mine", model="m/x", provider="deepseek", base_url="https://api.deepseek.com")
    ]
    store: dict = {"cfg": ExternalAgentConfig(command="hermes acp", cwd="", brains=chosen)}

    async def _fake_get_config(db):
        return store["cfg"]

    async def _fake_save_config(db, cfg):
        store["cfg"] = cfg

    monkeypatch.setattr("app.api.v1.external_agent_router.get_config", _fake_get_config)
    monkeypatch.setattr("app.api.v1.external_agent_router.save_config", _fake_save_config)

    updated = await update_external_agent_config(
        ExternalAgentConfigUpdate(cwd="/tmp/agent"), db=None
    )

    assert [b.model for b in updated.brains] == ["m/x"], "the list must carry over"


@pytest.mark.asyncio
async def test_config_update_merges_budget_fields(monkeypatch):
    """2026-09-08 (the PUT-merge gap, CAUGHT LIVE by the regime test):
    the update handler's explicit construction must carry the budget
    fields — a write of tool_call_checkin_every used to be validated
    then SILENTLY reset to the default (the old handler omitted both
    fields from the new-config build)."""
    from app.api.v1.external_agent_router import update_external_agent_config
    from app.domain.external_agent.schemas import ExternalAgentConfigUpdate

    store: dict = {}

    async def _fake_get_config(db):
        return store.get("cfg") or ExternalAgentConfig()

    async def _fake_save_config(db, cfg):
        store["cfg"] = cfg

    # the PUT handler binds these at MODULE level (the router's own
    # names — the package-attr patch would miss them)
    monkeypatch.setattr("app.api.v1.external_agent_router.get_config", _fake_get_config)
    monkeypatch.setattr("app.api.v1.external_agent_router.save_config", _fake_save_config)

    updated = await update_external_agent_config(
        ExternalAgentConfigUpdate(tool_call_checkin_every=3), db=None
    )
    assert updated.tool_call_checkin_every == 3, "the cadence write must land"
    assert updated.max_tool_calls_per_turn == 75, "the untouched field carries over"

    updated2 = await update_external_agent_config(
        ExternalAgentConfigUpdate(max_tool_calls_per_turn=90), db=None
    )
    assert updated2.max_tool_calls_per_turn == 90
    assert updated2.tool_call_checkin_every == 3, "the earlier write survives the next update"



def test_singleton_rebuilds_on_cwd_change(monkeypatch):
    """2026-09-08 (the LIVE catch — the user's report): the config PUT
    changed the cwd to the project root, but the singleton survived
    with the OLD cwd — the rebuild only fired on a TIER change, so
    sessions kept spawning with cwd=backend/ and the
    workspace_session auto-approve never covered project-root
    writes (.exa-workspace/ edits asked + timed out to denied)."""
    import app.domain.external_agent.services as svc

    monkeypatch.setattr(
        svc, "_client",
        svc.AcpClient(command=["hermes", "acp"], cwd="/old/stale/cwd", permission_tier="fix"),
    )
    old = svc._client
    rebuilt = svc.get_acp_client(
        command=["hermes", "acp"],
        cwd=str(REPO_ROOT),
        permission_tier="fix",
    )
    assert rebuilt is not old, "a cwd change must rebuild the singleton"
    assert rebuilt.cwd == str(REPO_ROOT)
    assert rebuilt.permission_tier == "fix"


def test_singleton_not_rebuilt_without_config_change(monkeypatch):
    """The same params must return the SAME client (no churn)."""
    import app.domain.external_agent.services as svc

    monkeypatch.setattr(
        svc, "_client",
        svc.AcpClient(command=["hermes", "acp"], cwd=str(REPO_ROOT), permission_tier="fix"),
    )
    same = svc.get_acp_client(
        command=["hermes", "acp"],
        cwd=str(REPO_ROOT),
        permission_tier="fix",
    )
    assert same is svc._client, "no config change = no rebuild"
