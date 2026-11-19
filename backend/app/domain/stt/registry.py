"""THE STT PROVIDER REGISTRY (2026-08-30, the _26 build): the ONE
resolver — a MAP (the doctrine, the TTS mirror). New providers =
a file + a registration here; the config's provider selects."""

from app.domain.stt.interface import SttProvider
from app.domain.stt.providers.whisper_provider import WhisperProvider

_PROVIDERS: dict[str, SttProvider] = {
    "whisper": WhisperProvider(),
}


def get_stt_provider(name: str) -> SttProvider:
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"Unknown STT provider: {name}")
    return provider


def list_stt_providers() -> list[str]:
    return list(_PROVIDERS)
