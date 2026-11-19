"""THE TTS PROVIDER REGISTRY (2026-08-30, the provider build): the
ONE resolver — a MAP (the doctrine). New providers = a file + a
registration here; the config's provider selects."""

from app.domain.tts.interface import TtsProvider
from app.domain.tts.providers.piper_provider import PiperProvider
from app.domain.tts.providers.edge_provider import EdgeProvider

_PROVIDERS: dict[str, TtsProvider] = {
    "piper": PiperProvider(),
    "edge": EdgeProvider(),
}


def get_tts_provider(name: str) -> TtsProvider:
    provider = _PROVIDERS.get(name)
    if provider is None:
        raise ValueError(f"Unknown TTS provider: {name}")
    return provider


def list_tts_providers() -> list[str]:
    return list(_PROVIDERS)
