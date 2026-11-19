"""THE STT PROVIDER CONTRACT (2026-08-30, the _26 build — the TTS
pattern mirrored): ONE API for the speech-to-text paths. The
providers implement this; the router + the frontend never know
which one answers.

    transcribe(audio) -> the recognized text (+ language/duration)

The ROUND-TRIP harness (the _26 centerpiece): the TTS speaks a
known text -> the wav -> the STT transcribes -> the WER.
"""

from typing import Protocol, TypedDict


class SttResult(TypedDict):
    text: str
    language: str
    duration: float  # the audio's duration in seconds


class SttProvider(Protocol):
    name: str

    async def transcribe(self, audio: bytes) -> SttResult:
        """Transcribe the audio bytes (wav/mp3) -> the recognized text."""
        ...
