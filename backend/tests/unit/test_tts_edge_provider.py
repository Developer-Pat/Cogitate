"""The Edge TTS provider — the keyless online neural voices."""

from pathlib import Path

import pytest

from app.domain.tts.registry import get_tts_provider, list_tts_providers
from app.domain.tts.providers.edge_provider import EdgeProvider, _binary

VOICES_TABLE = """Name                               Gender    ContentCategories      VoicePersonalities
---------------------------------  --------  ---------------------  --------------------------------------
en-US-AriaNeural                   Female    General                Friendly, Positive
en-US-GuyNeural                    Male      General                Friendly, Positive
fr-FR-DeniseNeural                 Female    General                Friendly, Positive
"""


@pytest.fixture
def fake_binary(tmp_path):
    (tmp_path / "edge-tts").write_bytes(b"#!/bin/sh\n")
    return tmp_path


@pytest.mark.asyncio
async def test_edge_lists_the_en_voices(fake_binary, monkeypatch):
    async def fake_exec(*args, **kwargs):
        class FakeProc:
            returncode = 0

            async def communicate(self):
                return VOICES_TABLE.encode(), b""

        return FakeProc()

    monkeypatch.setattr("app.domain.tts.providers.edge_provider._binary", lambda: str(fake_binary / "edge-tts"))
    monkeypatch.setattr("app.domain.tts.providers.edge_provider.asyncio.create_subprocess_exec", fake_exec)
    provider = EdgeProvider()
    voices = await provider.voices()
    assert voices == [
        {"name": "en-US-AriaNeural", "lang": "en-US", "default": False},
        {"name": "en-US-GuyNeural", "lang": "en-US", "default": False},
    ]


@pytest.mark.asyncio
async def test_edge_synthesizes_an_mp3(fake_binary, monkeypatch):
    async def fake_exec(*args, **kwargs):
        out_path = Path(args[args.index("--write-media") + 1])
        out_path.write_bytes(b"MP3DATA")

        class FakeProc:
            returncode = 0

            async def communicate(self):
                return b"", b""

        return FakeProc()

    monkeypatch.setattr("app.domain.tts.providers.edge_provider._binary", lambda: str(fake_binary / "edge-tts"))
    monkeypatch.setattr("app.domain.tts.providers.edge_provider.asyncio.create_subprocess_exec", fake_exec)
    provider = EdgeProvider()
    data = await provider.synthesize("hello", "en-US-AriaNeural", rate=1.2)
    assert data == b"MP3DATA"
    assert provider.media_type == "audio/mpeg"


def test_the_registry_has_both_providers():
    names = list_tts_providers()
    assert "piper" in names and "edge" in names
    assert get_tts_provider("edge").name == "edge"


def test_the_binary_resolves_the_user_install():
    # the absolute user-level path wins (the backend's PATH may not
    # include ~/.local/bin)
    assert _binary().endswith("edge-tts")
