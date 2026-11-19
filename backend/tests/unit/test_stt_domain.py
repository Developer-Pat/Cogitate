"""Speech-to-text config round-trips, the registry maps providers, and empty audio is rejected.

- the config: the defaults + the merge/save round-trip
- the router: the transcribe contract + the guards (the empty
  audio, the cap, the disabled, the unknown provider)
- the ROUND-TRIP HARNESS (the unit half): the deterministic
  TTS->STT loop with the mocked providers — the text the TTS
  "speaks" is what the STT "hears" (the real-models' accuracy is
  the live gate's job, not the unit's).
"""

import json

import pytest

from app.domain.stt.config import DEFAULT_CONFIG, get_stt_config, save_stt_config
from app.domain.stt.registry import get_stt_provider, list_stt_providers
from app.domain.stt.interface import SttResult


class FakeWhisper:
    """The round-trip's ear: it 'hears' exactly what the piper said."""

    name = "whisper"

    def __init__(self, expected: str):
        self.expected = expected

    async def transcribe(self, audio: bytes) -> SttResult:
        # THE ROUND-TRIP CONTRACT: the provider receives the wav
        # bytes the TTS produced — the harness asserts the bytes
        # ARRIVE (the wiring!), not the model's accuracy.
        assert audio == b"the-wav-bytes-the-tts-spoke"
        return SttResult(text=self.expected, language="en", duration=2.5)


@pytest.mark.anyio
async def test_default_config_shape():
    """The preferences only — the ENGINE is the `stt` capability's answer (phase 5)."""
    cfg = dict(DEFAULT_CONFIG)
    assert cfg["enabled"] is True
    assert "provider" not in cfg


@pytest.mark.anyio
async def test_config_save_merge_round_trip(test_session):
    saved = await save_stt_config(test_session, {"enabled": False})
    assert saved["enabled"] is False
    assert "provider" not in saved          # the retired key: the capability owns the engine

    reloaded = await get_stt_config(test_session)
    assert reloaded["enabled"] is False
    assert "provider" not in reloaded


@pytest.mark.anyio
async def test_a_retired_provider_key_can_never_be_stored_again(test_session):
    """A caller that still sends `provider` cannot put an engine back in the preferences.

    The engine has ONE home now, so a stored second copy is the defect this arc removed — the store
    drops the key rather than keeping it in step with nothing.
    """
    saved = await save_stt_config(test_session, {"provider": "nope", "enabled": True})

    assert "provider" not in saved
    assert "provider" not in await get_stt_config(test_session)


@pytest.mark.anyio
async def test_a_stale_blob_provider_is_stripped_on_read(test_session):
    """A blob written BEFORE this change still carries the key — the read must not surface it."""
    from sqlalchemy import select

    from app.infrastructure.database.models import UserSettings

    test_session.add(
        UserSettings(user_key="default", settings={"stt": {"provider": "whisper", "enabled": True}})
    )
    await test_session.commit()

    cfg = await get_stt_config(test_session)

    assert cfg["enabled"] is True
    assert "provider" not in cfg


@pytest.mark.anyio
async def test_registry_maps_whisper():
    assert list_stt_providers() == ["whisper"]
    provider = get_stt_provider("whisper")
    assert provider.name == "whisper"


def test_registry_unknown_provider():
    with pytest.raises(ValueError):
        get_stt_provider("nope")


@pytest.mark.anyio
async def test_round_trip_contract():
    """The TTS spoke the wav; the STT hears it back — the harness's
    unit half pins the wiring (the bytes arrive, the text returns)."""
    provider = FakeWhisper(expected="the quick brown fox")
    result = await provider.transcribe(b"the-wav-bytes-the-tts-spoke")
    assert result["text"] == "the quick brown fox"
    assert result["language"] == "en"
    assert result["duration"] == 2.5


# --- the router ---

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import stt_router as stt_router_mod
from app.api.v1.stt_router import router as stt_router
from app.infrastructure.database import get_db_session

app = FastAPI()
app.include_router(stt_router)


@pytest.fixture
def client(monkeypatch, test_session):
    # THE DB OVERRIDE (the house pattern): the router's Depends
    # resolves through the app's override map, not the module.
    app.dependency_overrides[get_db_session] = lambda: test_session

    async def fake_get_config(db):
        return dict(DEFAULT_CONFIG)

    async def fake_save_config(db, updates):
        return {**DEFAULT_CONFIG, **updates}

    async def fake_resolver(db, capability):
        """THE CAPABILITY'S ANSWER (phase 5): the engine the router must resolve.

        Patched at the router module, like the config functions: the router holds its OWN imported
        reference, so patching the capabilities module would never reach it.
        """
        return ("whisper", "capability config")

    # THE ROUTER-MODULE PATCHES: the router holds its OWN imported
    # references — the config-module patches would never reach it.
    monkeypatch.setattr(stt_router_mod, "get_stt_config", fake_get_config)
    monkeypatch.setattr(stt_router_mod, "save_stt_config", fake_save_config)
    monkeypatch.setattr(stt_router_mod, "resolve_named_service", fake_resolver)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db_session, None)


def test_transcribe_contract(client, monkeypatch):
    class FakeProvider:
        name = "whisper"

        async def transcribe(self, audio):
            return SttResult(text="hello world", language="en", duration=1.0)

    monkeypatch.setattr(
        "app.api.v1.stt_router.get_stt_provider", lambda name: FakeProvider()
    )

    resp = client.post(
        "/stt/transcribe",
        files={"file": ("sample.wav", b"RIFF-fake-wav-data", "audio/wav")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["provider"] == "whisper"
    assert body["text"] == "hello world"


def test_transcribe_empty_rejected(client):
    resp = client.post(
        "/stt/transcribe",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert resp.status_code == 400


def test_transcribe_disabled(client, monkeypatch):
    async def disabled(db):
        return {**DEFAULT_CONFIG, "enabled": False}

    monkeypatch.setattr(stt_router_mod, "get_stt_config", disabled)
    resp = client.post(
        "/stt/transcribe",
        files={"file": ("s.wav", b"RIFF-data", "audio/wav")},
    )
    assert resp.status_code == 400


def test_transcribe_unknown_engine_is_rejected(client, monkeypatch):
    """The capability names an engine the registry does not have → 400, before the audio work."""

    async def bad_resolver(db, capability):
        return ("nope", "capability config")

    monkeypatch.setattr(stt_router_mod, "resolve_named_service", bad_resolver)
    resp = client.post(
        "/stt/transcribe",
        files={"file": ("s.wav", b"RIFF-data", "audio/wav")},
    )
    assert resp.status_code == 400


def test_transcribe_with_nothing_configured_is_a_loud_503(client, monkeypatch):
    """No engine anywhere: the endpoint REFUSES rather than falling back to a name written in code."""

    async def empty_resolver(db, capability):
        return (None, "none")

    monkeypatch.setattr(stt_router_mod, "resolve_named_service", empty_resolver)
    resp = client.post(
        "/stt/transcribe",
        files={"file": ("s.wav", b"RIFF-data", "audio/wav")},
    )
    assert resp.status_code == 503
    assert "stt" in resp.json()["detail"]


def test_the_retired_provider_field_is_refused_naming_the_replacement(client):
    """`PUT /config`'s `provider` is RETIRED (phase 6, G2-F4): the engine is the capability's answer.

    Refused, not ignored — an ignored key makes a stale producer's flip succeed while the value goes
    nowhere. (The speech page never had an STT engine switch, so nothing in the app sends it; the
    guard is for bundles still in use.)
    """
    resp = client.put("/stt/config", json={"provider": "whisper"})

    assert resp.status_code == 422
    detail = json.dumps(resp.json())
    assert "provider" in detail
    assert "/providers/capabilities" in detail


def test_config_round_trip_through_api(client, monkeypatch):
    """The read reports the engine the CAPABILITY names — resolved, never a stored copy."""
    resp = client.put("/stt/config", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False
    assert resp.json()["provider"] == "whisper"

    resp = client.get("/stt/config")
    assert resp.status_code == 200
    assert resp.json()["provider"] == "whisper"


# --- the write path the speech rows now share, against real capability rows ---


@pytest.mark.anyio
async def test_the_general_write_path_re_points_the_capability_the_read_then_sees(test_session):
    """What replaced the shim: the same move (`edge` → `whisper`) through `replace_chain`.

    The capability is built here rather than assumed: the test database carries no capability rows
    (the copy is cleaned between tests), and a test that leaned on the live seed would pass for the
    wrong reason — this asserts the MOVE and that no second candidate appears.
    """
    from sqlalchemy import select

    from app.domain.providers.capabilities import (
        CandidateSpec,
        replace_chain,
        resolve_named_service,
    )
    from app.infrastructure.database.models import Capability, CapabilityService

    capability = Capability(key="stt", label="Speech to text", kind="speech", enabled=True)
    test_session.add(capability)
    await test_session.flush()
    test_session.add(
        CapabilityService(
            capability_id=capability.id, ordinal=0, service_name="edge", enabled=True
        )
    )
    await test_session.commit()

    await replace_chain(test_session, "stt", [CandidateSpec(service_name="whisper")])

    engine, reason = await resolve_named_service(test_session, "stt")
    assert engine == "whisper"
    assert reason == "capability config"

    rows = (
        await test_session.execute(
            select(CapabilityService).where(CapabilityService.capability_id == capability.id)
        )
    ).scalars().all()
    assert [r.service_name for r in rows] == ["whisper"]     # moved, not duplicated
