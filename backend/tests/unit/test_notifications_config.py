"""Notifications config — the UserSettings-backed store + the router."""

import time

import pytest

from app.api.v1.notifications_router import NotificationsConfigUpdate, update_config
from app.domain.messaging.notifications_config import (
    get_notifications_config,
    save_notifications_config,
)


@pytest.mark.asyncio
async def test_defaults(test_session):
    cfg = await get_notifications_config(test_session)
    assert cfg == {
        "suppressed": False,
        "audio_enabled": False,
        "sound_id": "gentle-ping.wav",
        "mute_until": None,
        "volume": 1.0,
        "sound_success": "end-of-run.wav",
        "sound_warning": "alert.wav",
        "sound_error": "emergency.wav",
        "sound_level": "warning",
    }


@pytest.mark.asyncio
async def test_roundtrip(test_session):
    saved = await save_notifications_config(
        test_session, {"audio_enabled": True, "sound_id": "soft-chime.wav"}
    )
    assert saved["audio_enabled"] is True
    loaded = await get_notifications_config(test_session)
    assert loaded["audio_enabled"] is True
    assert loaded["sound_id"] == "soft-chime.wav"
    assert loaded["suppressed"] is False  # untouched


@pytest.mark.asyncio
async def test_none_updates_are_skipped(test_session):
    await save_notifications_config(test_session, {"audio_enabled": True})
    # a None update must NOT overwrite the stored value
    saved = await save_notifications_config(test_session, {"audio_enabled": None})
    assert saved["audio_enabled"] is True
    loaded = await get_notifications_config(test_session)
    assert loaded["audio_enabled"] is True


@pytest.mark.asyncio
async def test_unknown_keys_ignored(test_session):
    saved = await save_notifications_config(
        test_session, {"sound_id": "ping.wav", "bogus": 123}
    )
    assert "bogus" not in saved


@pytest.mark.asyncio
async def test_update_config_rejects_missing_sound(test_session, monkeypatch, tmp_path):
    # point the sounds store at an empty dir -> every sound_id 400s
    class S:
        max_sound_upload_size = 1
        allowed_sound_types = ["audio/wav"]

    class P:
        def __init__(self):
            self.notification_sounds_dir = tmp_path
            self.curated_sounds_dir = tmp_path / "curated"

        @classmethod
        def from_settings(cls, settings):
            return cls()

    from app.api.v1 import sounds_router
    from app.domain.messaging import sounds as sounds_mod
    monkeypatch.setattr(sounds_mod, "get_settings", lambda: S())
    monkeypatch.setattr(sounds_mod, "Paths", P())

    with pytest.raises(Exception) as exc:
        await update_config(
            NotificationsConfigUpdate(sound_id="nope.wav"), test_session
        )
    assert "Sound not found" in str(exc.value)


@pytest.mark.asyncio
async def test_update_config_accepts_existing_sound(test_session, monkeypatch, tmp_path):
    (tmp_path / "ping.wav").write_bytes(b"RIFF-fake")
    class S:
        max_sound_upload_size = 1
        allowed_sound_types = ["audio/wav"]

    class P:
        def __init__(self):
            self.notification_sounds_dir = tmp_path
            self.curated_sounds_dir = tmp_path / "curated"

        @classmethod
        def from_settings(cls, settings):
            return cls()

    from app.api.v1 import sounds_router
    from app.domain.messaging import sounds as sounds_mod
    monkeypatch.setattr(sounds_mod, "get_settings", lambda: S())
    monkeypatch.setattr(sounds_mod, "Paths", P())

    saved = await update_config(
        NotificationsConfigUpdate(sound_id="ping.wav"), test_session
    )
    assert saved["sound_id"] == "ping.wav"


@pytest.mark.asyncio
async def test_mute_until_roundtrip(test_session):
    saved = await save_notifications_config(
        test_session, {"suppressed": True, "mute_until": 1234.5}
    )
    assert saved["suppressed"] is True
    assert saved["mute_until"] == 1234.5
    loaded = await get_notifications_config(test_session)
    assert loaded["mute_until"] == 1234.5


@pytest.mark.asyncio
async def test_clear_removes_mute_until(test_session):
    await save_notifications_config(
        test_session, {"suppressed": True, "mute_until": 1234.5}
    )
    saved = await save_notifications_config(
        test_session, {"suppressed": False}, clear={"mute_until"}
    )
    assert saved["suppressed"] is False
    assert "mute_until" not in saved or saved["mute_until"] is None
    loaded = await get_notifications_config(test_session)
    assert loaded["mute_until"] is None


@pytest.mark.asyncio
async def test_restore_notifications_flips_and_clears(test_session, monkeypatch):
    await save_notifications_config(
        test_session, {"suppressed": True, "mute_until": time.time() - 10}
    )
    # the restore opens its OWN session (the production get_db_session)
    # — point it at the test session
    async def _session_gen():
        yield test_session

    import app.infrastructure.database as db_mod
    monkeypatch.setattr(db_mod, "get_db_session", _session_gen)
    from app.domain.messaging.notifications import restore_notifications
    await restore_notifications()
    loaded = await get_notifications_config(test_session)
    assert loaded["suppressed"] is False
    assert loaded["mute_until"] is None


@pytest.mark.asyncio
async def test_restore_notifications_noops_when_already_restored(test_session):
    await save_notifications_config(test_session, {"suppressed": False})
    from app.domain.messaging.notifications import restore_notifications
    await restore_notifications()
    loaded = await get_notifications_config(test_session)
    assert loaded["suppressed"] is False


@pytest.mark.asyncio
async def test_ensure_mute_restore_heals_expired_mute(test_session, monkeypatch):
    await save_notifications_config(
        test_session, {"suppressed": True, "mute_until": time.time() - 5}
    )
    async def _session_gen():
        yield test_session

    import app.infrastructure.database as db_mod
    monkeypatch.setattr(db_mod, "get_db_session", _session_gen)
    from app.domain.messaging.notifications import ensure_mute_restore
    await ensure_mute_restore()
    loaded = await get_notifications_config(test_session)
    assert loaded["suppressed"] is False


@pytest.mark.asyncio
async def test_ensure_mute_restore_leaves_active_mute(test_session):
    await save_notifications_config(
        test_session, {"suppressed": True, "mute_until": time.time() + 3600}
    )
    from app.domain.messaging.notifications import ensure_mute_restore
    await ensure_mute_restore()
    loaded = await get_notifications_config(test_session)
    assert loaded["suppressed"] is True


@pytest.mark.asyncio
async def test_volume_roundtrip(test_session):
    saved = await save_notifications_config(test_session, {"volume": 0.4})
    assert saved["volume"] == 0.4
    loaded = await get_notifications_config(test_session)
    assert loaded["volume"] == 0.4


def test_volume_validation_rejects_out_of_range():
    from pydantic import ValidationError

    from app.api.v1.notifications_router import NotificationsConfigUpdate

    with pytest.raises(ValidationError):
        NotificationsConfigUpdate(volume=1.5)
    with pytest.raises(ValidationError):
        NotificationsConfigUpdate(volume=-0.1)
    # the bounds are legal
    assert NotificationsConfigUpdate(volume=0.0).volume == 0.0
    assert NotificationsConfigUpdate(volume=1.0).volume == 1.0
