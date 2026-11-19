"""THE TTS PROVIDER CONTRACT (2026-08-30, the provider build — the
study's section 6): ONE API for the private (piper) + the online
(cloud) paths. The providers implement this; the router + the
frontend never know which one answers.

    voices()     -> the provider's selectable voices
    synthesize(text, voice, rate) -> the wav bytes
"""

from typing import Protocol, TypedDict


class TtsVoice(TypedDict):
    name: str
    lang: str
    default: bool


class TtsProvider(Protocol):
    name: str
    media_type: str  # "audio/wav" (piper) | "audio/mpeg" (edge)

    async def voices(self) -> list[TtsVoice]:
        """The provider's selectable voices (the picker's options)."""
        ...

    async def synthesize(self, text: str, voice: str, rate: float = 1.0) -> bytes:
        """Synthesize the text in the given voice -> the wav bytes."""
        ...
