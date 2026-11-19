"""Sound management — list/upload/delete/restore + the config guard."""

import io
import math
import struct
import wave

import pytest
from fastapi import UploadFile

from app.api.v1 import sounds_router
from app.domain.messaging import sounds


def _tiny_wav(dur: float = 0.01, freq: float = 880.0) -> bytes:
    rate = 8000
    n = int(rate * dur)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(
            struct.pack("<h", int(math.sin(2 * math.pi * freq * i / rate) * 8000))
            for i in range(n)
        )
        w.writeframes(frames)
    return buf.getvalue()


def _settings(max_size=2 * 1024 * 1024):
    class S:
        max_sound_upload_size = max_size
        allowed_sound_types = ["audio/wav", "audio/x-wav", "audio/wave"]

    return S()


def _paths(tmp_path, curated=None):
    class P:
        def __init__(self):
            self.notification_sounds_dir = tmp_path
            # the real Paths ALWAYS has a curated dir — the fake
            # mirrors it (a None would crash the domain's read)
            self.curated_sounds_dir = curated or (tmp_path / "curated")

        @classmethod
        def from_settings(cls, settings):
            return cls()

    return P()


def _up(name: str, data: bytes, content_type: str = "audio/wav") -> UploadFile:
    return UploadFile(
        file=io.BytesIO(data), filename=name, headers={"content-type": content_type}
    )


@pytest.mark.asyncio
async def test_list_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    result = await sounds_router.list_sounds()
    assert result["total"] == 0
    assert result["sounds"] == []


@pytest.mark.asyncio
async def test_upload_and_list(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    data = _tiny_wav()
    uploaded = await sounds_router.upload_sound(_up("ping.wav", data))
    assert uploaded["filename"].endswith(".wav")
    assert uploaded["size"] == len(data)
    result = await sounds_router.list_sounds()
    assert result["total"] == 1
    assert result["sounds"][0]["filename"] == uploaded["filename"]
    assert result["sounds"][0]["mime"] == "audio/wav"
    assert result["sounds"][0]["url"] == f"/api/v1/sounds/{uploaded['filename']}/file"


@pytest.mark.asyncio
async def test_serve_file(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    uploaded = await sounds_router.upload_sound(_up("ping.wav", _tiny_wav()))
    resp = await sounds_router.serve_sound(uploaded["filename"])
    assert resp.status_code == 200
    assert resp.media_type == "audio/wav"
    # FileResponse streams the file — verify the served path + the bytes on disk
    assert str(resp.path) == str(tmp_path / uploaded["filename"])
    assert (tmp_path / uploaded["filename"]).read_bytes() == _tiny_wav()


@pytest.mark.asyncio
async def test_serve_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    with pytest.raises(Exception) as exc:
        await sounds_router.serve_sound("../evil.wav")
    assert "Invalid filename" in str(exc.value)


@pytest.mark.asyncio
async def test_upload_dedups_content(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    data = _tiny_wav()
    a = await sounds_router.upload_sound(_up("a.wav", data))
    b = await sounds_router.upload_sound(_up("b.wav", data))
    assert a["filename"] == b["filename"]  # same bytes -> same file


@pytest.mark.asyncio
async def test_upload_rejects_bad_type(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    with pytest.raises(Exception) as exc:
        await sounds_router.upload_sound(_up("evil.txt", b"hello", "text/plain"))
    assert "Invalid file type" in str(exc.value)


@pytest.mark.asyncio
async def test_upload_rejects_oversize(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings(max_size=10))
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    with pytest.raises(Exception) as exc:
        await sounds_router.upload_sound(_up("big.wav", _tiny_wav()))
    assert "too large" in str(exc.value)


@pytest.mark.asyncio
async def test_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    uploaded = await sounds_router.upload_sound(_up("ping.wav", _tiny_wav()))
    result = await sounds_router.delete_sound(uploaded["filename"])
    assert result is None
    assert (tmp_path / uploaded["filename"]).exists() is False


@pytest.mark.asyncio
async def test_delete_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    with pytest.raises(Exception) as exc:
        await sounds_router.delete_sound("../evil.wav")
    assert "Invalid filename" in str(exc.value)


@pytest.mark.asyncio
async def test_delete_refuses_configured_sound(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path))
    uploaded = await sounds_router.upload_sound(_up("ping.wav", _tiny_wav()))
    monkeypatch.setattr(sounds, "configured_sound_id", lambda: uploaded["filename"])
    with pytest.raises(Exception) as exc:
        await sounds_router.delete_sound(uploaded["filename"])
    assert "configured notification sound" in str(exc.value)


@pytest.mark.asyncio
async def test_restore_curated(tmp_path, monkeypatch):
    monkeypatch.setattr(sounds, "get_settings", lambda: _settings())
    curated = tmp_path / "curated"
    curated.mkdir()
    (curated / "gentle-ping.wav").write_bytes(_tiny_wav())
    (curated / "soft-chime.wav").write_bytes(_tiny_wav(freq=660.0))
    monkeypatch.setattr(sounds, "Paths", _paths(tmp_path, curated=curated))

    result = await sounds_router.restore_curated_sounds()
    assert sorted(result["restored"]) == ["gentle-ping.wav", "soft-chime.wav"]

    # idempotent: a second restore adds nothing, and a user upload is untouched
    (tmp_path / "user-sound.wav").write_bytes(_tiny_wav())
    result2 = await sounds_router.restore_curated_sounds()
    assert result2["restored"] == []
    assert result2["skipped"] == 2
