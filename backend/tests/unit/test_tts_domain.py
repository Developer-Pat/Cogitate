"""The TTS half of phase 5: the preferences stay, the ENGINE becomes the capability's answer.

This file is the net the TTS side never had. The STT mirror (`test_stt_domain.py`) covers its config
round-trip and router; TTS's config and router were untested, which mattered once the engine stopped
being a stored preference.

Three things are pinned here, and they are different questions:

* the **store** holds only what belongs to the user — a retired `provider` key is stripped on read, so
  a blob written before the change cannot read as a second answer;
* the **router** resolves the engine from the `tts` capability and refuses LOUDLY when the capability
  names nothing — there is no engine name in code to fall back to;
* the retired `provider` field is **refused** by the update schema (phase 6, G2-F4 — the shim that
  used to write it, `set_speech_service`, is gone), and the voice rule that shim carried is published
  by `GET /voices` as `default`, so whoever reads the list can repair a voice the engine cannot speak.
"""

from __future__ import annotations

import json

import pytest

from app.domain.tts.config import DEFAULT_CONFIG, get_tts_config, save_tts_config


# ── the store ────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_default_config_shape():
    """The preferences only — the ENGINE is the `tts` capability's answer (phase 5)."""
    cfg = dict(DEFAULT_CONFIG)
    assert cfg["voice"] == "en_US-lessac-medium"
    assert cfg["source"] == "piper"          # the PATH selector, not an engine
    assert cfg["sticky_mode"] == "siren"
    assert "provider" not in cfg


@pytest.mark.anyio
async def test_config_save_merge_round_trip(test_session):
    saved = await save_tts_config(test_session, {"rate": 1.5})
    assert saved["rate"] == 1.5
    assert saved["voice"] == "en_US-lessac-medium"   # the default merged
    assert "provider" not in saved

    reloaded = await get_tts_config(test_session)
    assert reloaded["rate"] == 1.5
    assert "provider" not in reloaded


@pytest.mark.anyio
async def test_a_retired_provider_key_can_never_be_stored_again(test_session):
    """The engine has ONE home now; a stored second copy is the defect this arc removed."""
    saved = await save_tts_config(test_session, {"provider": "piper", "rate": 1.2})

    assert saved["rate"] == 1.2
    assert "provider" not in saved
    assert "provider" not in await get_tts_config(test_session)


@pytest.mark.anyio
async def test_a_stale_blob_provider_is_stripped_on_read(test_session):
    """The live blob still carries the retired key — the read must not surface it."""
    from app.infrastructure.database.models import UserSettings

    test_session.add(
        UserSettings(
            user_key="default",
            settings={"tts": {"provider": "edge", "voice": "en-AU-NatashaNeural", "rate": 1}},
        )
    )
    await test_session.commit()

    cfg = await get_tts_config(test_session)

    assert cfg["voice"] == "en-AU-NatashaNeural"     # the preference survives
    assert "provider" not in cfg                     # the engine does not


# ── the router ───────────────────────────────────────────────────────────────────────────────────

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import tts_router as tts_router_mod
from app.api.v1.tts_router import router as tts_router
from app.infrastructure.database import get_db_session

app = FastAPI()
app.include_router(tts_router)


class FakeEngine:
    """One TTS engine: the voices it offers, and the bytes it 'speaks'."""

    name = "piper"
    media_type = "audio/wav"

    def __init__(self, voices: list[str]):
        self._voices = voices

    async def voices(self) -> list[dict]:
        return [{"name": name} for name in self._voices]

    async def synthesize(self, text: str, voice: str, rate: float = 1.0) -> bytes:
        return b"RIFF-wav"


@pytest.fixture
def client(monkeypatch, test_session):
    app.dependency_overrides[get_db_session] = lambda: test_session

    async def fake_get_config(db):
        # ENABLED on purpose: these tests are about what the endpoints DO when speech is
        # on. The shipped default is off (DEFAULT_CONFIG["enabled"] is False) and the
        # refusal has its own tests below.
        return {**DEFAULT_CONFIG, "enabled": True}

    async def fake_save_config(db, updates):
        return {**DEFAULT_CONFIG, **updates}

    async def fake_resolver(db, capability):
        """The capability's answer: WHICH engine speaks (patched — the rows live in the app's db)."""
        return ("piper", "capability config")

    # THE ROUTER-MODULE PATCHES: the router holds its OWN imported references.
    monkeypatch.setattr(tts_router_mod, "get_tts_config", fake_get_config)
    monkeypatch.setattr(tts_router_mod, "save_tts_config", fake_save_config)
    monkeypatch.setattr(tts_router_mod, "resolve_named_service", fake_resolver)
    yield TestClient(app)
    app.dependency_overrides.pop(get_db_session, None)


def test_speak_returns_the_wav(client, monkeypatch):
    monkeypatch.setattr(
        tts_router_mod, "get_tts_provider", lambda name: FakeEngine(["en_US-lessac-medium"])
    )

    resp = client.get("/tts/speak", params={"text": "hello"})

    assert resp.status_code == 200
    assert resp.content == b"RIFF-wav"
    assert resp.headers["content-type"].startswith("audio/wav")


def test_voices_lists_the_resolved_engines_voices(client, monkeypatch):
    monkeypatch.setattr(tts_router_mod, "get_tts_provider", lambda name: FakeEngine(["v-one", "v-two"]))

    resp = client.get("/tts/voices")

    assert resp.status_code == 200
    assert resp.json() == {
        "provider": "piper",
        "voices": [{"name": "v-one"}, {"name": "v-two"}],
        "default": "v-one",
    }


async def _disabled(db):
    return {**DEFAULT_CONFIG, "enabled": False}


def test_speak_refuses_when_speech_is_off(client, monkeypatch):
    """THE OFF SWITCH IS A SWITCH: a disabled install does not synthesize, whatever asks."""
    monkeypatch.setattr(tts_router_mod, "get_tts_config", _disabled)

    resp = client.get("/tts/speak", params={"text": "hello"})

    assert resp.status_code == 409
    assert "switched off" in resp.json()["detail"]


def test_the_voice_list_refuses_when_speech_is_off(client, monkeypatch):
    """`/voices` runs the engine's own listing (edge-tts asks Microsoft), so it is gated too."""
    monkeypatch.setattr(tts_router_mod, "get_tts_config", _disabled)

    assert client.get("/tts/voices").status_code == 409


def test_the_guard_runs_before_a_provider_is_built(client, monkeypatch):
    """No provider, no subprocess, no socket while the switch is off."""
    def exploding(name):
        raise AssertionError("a provider was constructed while speech was off")

    monkeypatch.setattr(tts_router_mod, "get_tts_config", _disabled)
    monkeypatch.setattr(tts_router_mod, "get_tts_provider", exploding)

    assert client.get("/tts/speak", params={"text": "hi"}).status_code == 409
    assert client.get("/tts/voices").status_code == 409


def test_config_reports_the_resolved_engine(client):
    """The read carries `provider` — but it is the CAPABILITY's answer, not a stored copy."""
    resp = client.get("/tts/config")

    assert resp.status_code == 200
    assert resp.json()["provider"] == "piper"
    assert resp.json()["voice"] == "en_US-lessac-medium"


def test_the_retired_provider_field_is_refused_naming_the_replacement(client):
    """`PUT /config`'s `provider` is RETIRED (phase 6, G2-F4): the engine is the capability's answer.

    Refused, not ignored: an ignored key makes a stale producer's flip SUCCEED while the value goes
    nowhere — indistinguishable from a working save. The refusal names where the engine is changed.
    """
    resp = client.put("/tts/config", json={"provider": "piper"})

    assert resp.status_code == 422
    detail = json.dumps(resp.json())
    assert "provider" in detail
    assert "/providers/capabilities" in detail


def test_the_voices_list_names_the_default_voice_for_a_fresh_choice(client, monkeypatch):
    """The rule the engine flip used to apply, published with the LIST it belongs to.

    A voice from the previous engine errors on the new one (piper: "Unknown piper voice"), and the
    engine is changed on /providers/capabilities where nothing knows about voices — so `GET /voices`
    answers what a repair should pick: the app's configured voice when this engine offers it…
    """
    monkeypatch.setattr(
        tts_router_mod,
        "get_tts_provider",
        lambda name: FakeEngine(["en-AU-NatashaNeural", "en_US-lessac-medium"]),
    )

    resp = client.get("/tts/voices")

    assert resp.status_code == 200
    assert resp.json()["default"] == "en_US-lessac-medium"    # the app's own default, offered here


def test_the_voices_default_falls_back_to_the_engines_first(client, monkeypatch):
    """…else the engine's first — the fallback the flip ended with."""
    monkeypatch.setattr(
        tts_router_mod, "get_tts_provider", lambda name: FakeEngine(["zz-one", "zz-two"])
    )

    resp = client.get("/tts/voices")

    assert resp.json()["default"] == "zz-one"


def test_a_voice_the_engine_does_not_have_is_rejected(client, monkeypatch):
    monkeypatch.setattr(tts_router_mod, "get_tts_provider", lambda name: FakeEngine(["known"]))

    resp = client.put("/tts/config", json={"voice": "unknown"})

    assert resp.status_code == 400
    assert "Unknown voice" in resp.json()["detail"]


def test_speak_with_nothing_configured_is_a_loud_503(client, monkeypatch):
    """No engine anywhere: REFUSE — there is no engine name written in code to fall back to."""

    async def empty_resolver(db, capability):
        return (None, "none")

    monkeypatch.setattr(tts_router_mod, "resolve_named_service", empty_resolver)

    resp = client.get("/tts/speak", params={"text": "hello"})

    assert resp.status_code == 503
    assert "tts" in resp.json()["detail"]


# ── the write path the speech rows now share, against real capability rows ────────────────────────


@pytest.mark.anyio
async def test_the_general_write_path_re_points_a_speech_capability_the_read_then_sees(test_session):
    """What replaced the shim: the same move (`edge` → `piper`) through `replace_chain`.

    The speech rows are edited like every other capability's now (phase 6, G2-F4) — this pins that the
    ONE write path does move the engine, and leaves no second candidate behind.
    """
    from sqlalchemy import select

    from app.domain.providers.capabilities import (
        CandidateSpec,
        replace_chain,
        resolve_named_service,
    )
    from app.infrastructure.database.models import Capability, CapabilityService

    capability = Capability(key="tts", label="Text to speech", kind="speech", enabled=True)
    test_session.add(capability)
    await test_session.flush()
    test_session.add(
        CapabilityService(
            capability_id=capability.id, ordinal=0, service_name="edge", enabled=True
        )
    )
    await test_session.commit()

    await replace_chain(test_session, "tts", [CandidateSpec(service_name="piper")])

    engine, reason = await resolve_named_service(test_session, "tts")
    assert engine == "piper"
    assert reason == "capability config"

    rows = (
        await test_session.execute(
            select(CapabilityService).where(CapabilityService.capability_id == capability.id)
        )
    ).scalars().all()
    assert [r.service_name for r in rows] == ["piper"]       # moved, not duplicated
