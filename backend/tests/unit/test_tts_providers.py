"""The TTS registry lists and rejects providers; Piper lists voices and synthesizes."""

from pathlib import Path

import pytest

from app.domain.tts.registry import get_tts_provider, list_tts_providers
from app.domain.tts.providers.piper_provider import PiperProvider


class _FakeLocator:
    def __init__(self, piper_dir: Path):
        self.piper_dir = piper_dir


class _FakePaths:
    @classmethod
    def from_settings(cls, settings):
        return _FakeLocator(settings.piper_dir)


class _FakeSettings:
    def __init__(self, piper_dir: Path):
        self.piper_dir = piper_dir


@pytest.fixture
def piper_dir(tmp_path):
    (tmp_path / "piper").write_bytes(b"#!/bin/sh\n")
    (tmp_path / "en_US-lessac-medium.onnx").write_bytes(b"model")
    (tmp_path / "en_US-lessac-medium.onnx.json").write_bytes(b"{}")
    return tmp_path


def test_registry_lists_the_providers():
    assert list_tts_providers() == ["piper", "edge"]
    assert get_tts_provider("piper").name == "piper"


def test_registry_rejects_the_unknown_provider():
    with pytest.raises(ValueError):
        get_tts_provider("nope")


@pytest.mark.asyncio
async def test_piper_lists_the_model_voices(piper_dir, monkeypatch):
    monkeypatch.setattr("app.domain.tts.providers.piper_provider.Paths", _FakePaths)
    monkeypatch.setattr("app.domain.tts.providers.piper_provider.get_settings", lambda: _FakeSettings(piper_dir))
    provider = PiperProvider()
    voices = await provider.voices()
    assert voices == [{"name": "en_US-lessac-medium", "lang": "en-US", "default": False}]


@pytest.mark.asyncio
async def test_piper_synthesizes_via_the_binary(piper_dir, monkeypatch):
    monkeypatch.setattr("app.domain.tts.providers.piper_provider.Paths", _FakePaths)
    monkeypatch.setattr("app.domain.tts.providers.piper_provider.get_settings", lambda: _FakeSettings(piper_dir))

    async def fake_exec(*args, **kwargs):
        out_path = Path(args[args.index("--output_file") + 1])
        out_path.write_bytes(b"WAVDATA")

        class FakeProc:
            returncode = 0

            async def communicate(self, data=None):
                return None, b""

        return FakeProc()

    monkeypatch.setattr("app.domain.tts.providers.piper_provider.asyncio.create_subprocess_exec", fake_exec)
    provider = PiperProvider()
    wav = await provider.synthesize("hello", "en_US-lessac-medium", rate=2.0)
    assert wav == b"WAVDATA"


@pytest.mark.asyncio
async def test_piper_rejects_the_unknown_voice(piper_dir, monkeypatch):
    monkeypatch.setattr("app.domain.tts.providers.piper_provider.Paths", _FakePaths)
    monkeypatch.setattr("app.domain.tts.providers.piper_provider.get_settings", lambda: _FakeSettings(piper_dir))
    provider = PiperProvider()
    with pytest.raises(ValueError):
        await provider.synthesize("hello", "no-such-voice")


def test_sticky_mode_defaults_to_siren():
    """The P3 (2026-08-31): the sticky alerts' voice mode defaults to
    the siren-loop; the spoken mode's the opt-in."""
    from app.domain.tts.config import DEFAULT_CONFIG

    assert DEFAULT_CONFIG["sticky_mode"] == "siren"
