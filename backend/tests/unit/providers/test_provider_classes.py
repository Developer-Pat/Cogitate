"""Provider classes split cloud APIs from local daemons, with a loopback tiebreaker.

The location derivation must agree with the factory's key
requirement: cloud types need keys, local types never do — one
constant drives both.
"""

from app.domain.providers.provider_classes import (
    PROVIDER_CLOUD_TYPES,
    provider_location,
)


def test_cloud_types_are_remote_api_providers():
    assert {"openrouter", "deepseek", "groq", "openai", "anthropic", "ollama_cloud"} <= PROVIDER_CLOUD_TYPES


def test_local_types_are_daemons():
    assert "ollama" not in PROVIDER_CLOUD_TYPES
    assert "llama" not in PROVIDER_CLOUD_TYPES


def test_location_derivation():
    assert provider_location("openrouter") == "cloud"
    assert provider_location("deepseek") == "cloud"
    assert provider_location("ollama_cloud") == "cloud"
    assert provider_location("ollama") == "local"
    assert provider_location("llama") == "local"
    # Unknown types default to local (a self-hosted daemon the user
    # runs — the conservative class: no key demands, no SaaS
    # assumptions).
    assert provider_location("my_local_server") == "local"


def test_loopback_tiebreaker():
    # llama.cpp registers as an 'openai' TYPE pointed at the
    # loopback — the cloud whitelist says cloud, the URL says local.
    assert provider_location("openai", "http://127.0.0.1:8080/v1") == "local"
    assert provider_location("openai", "http://localhost:1234/v1") == "local"
    # The same type pointed at the real API = cloud.
    assert provider_location("openai", "https://api.openai.com/v1") == "cloud"
    assert provider_location("openrouter", "https://openrouter.ai/api/v1") == "cloud"
    assert provider_location("openrouter", None) == "cloud"
