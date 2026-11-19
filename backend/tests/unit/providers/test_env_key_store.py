"""Unit tests for EnvKeyStore — the app's single secrets store (.env)."""

import os
import stat
from pathlib import Path

import pytest

from app.domain.providers.env_key_store import (
    EnvKeyStore,
    PROVIDER_ENV_VAR,
    env_key_store,
)


@pytest.fixture
def store(tmp_path) -> tuple[EnvKeyStore, Path]:
    env = tmp_path / ".env"
    env.write_text(
        "# Security section\n"
        "OPENROUTER_API_KEY=old-router\n"
        "DEEPSEEK_API_KEY=deep-1\n"
        "TAVILY_API_KEY=tav-1\n"
    )
    return EnvKeyStore(env_path=env), env


class TestEnvKeyStore:
    def test_provider_map_has_cloud_providers(self) -> None:
        assert PROVIDER_ENV_VAR["openrouter"] == "OPENROUTER_API_KEY"
        assert PROVIDER_ENV_VAR["ollama_cloud"] == "OLLAMA_CLOUD_API_KEY"
        assert "ollama" not in PROVIDER_ENV_VAR  # local needs no key

    def test_get_key_existing(self, store) -> None:
        s, _ = store
        assert s.get_key("openrouter") == "old-router"

    def test_get_key_missing(self, store) -> None:
        s, _ = store
        assert s.get_key("groq") is None

    def test_set_key_updates_in_place(self, store) -> None:
        s, env = store
        s.set_key("openrouter", "new-router")
        text = env.read_text()
        assert "OPENROUTER_API_KEY=new-router" in text
        assert "OPENROUTER_API_KEY=old-router" not in text
        # other vars untouched
        assert "DEEPSEEK_API_KEY=deep-1" in text

    def test_set_key_appends_missing(self, store) -> None:
        s, env = store
        s.set_key("groq", "groq-1")
        assert s.get_key("groq") == "groq-1"
        assert "GROQ_API_KEY=groq-1" in env.read_text()

    def test_clear_key_removes_line(self, store) -> None:
        s, env = store
        s.clear_key("deepseek")
        assert s.get_key("deepseek") is None
        assert "DEEPSEEK_API_KEY" not in env.read_text()
        assert "OPENROUTER_API_KEY=old-router" in env.read_text()

    def test_writes_0600_permissions(self, store) -> None:
        s, env = store
        s.set_key("groq", "groq-1")
        mode = stat.S_IMODE(os.stat(env).st_mode)
        assert mode == 0o600

    def test_unknown_provider_is_noop(self, store) -> None:
        s, _ = store
        assert s.set_key("ollama", "x") is False
        assert s.clear_key("nonexistent") is False

    def test_creates_file_if_missing(self, tmp_path) -> None:
        env = tmp_path / "sub" / ".env"  # parent dir doesn't exist
        s = EnvKeyStore(env_path=env)
        assert s.set_key("groq", "groq-2") is True
        assert s.get_key("groq") == "groq-2"


class TestEnvKeyStoreSettingsSync:
    """set/clear must update the lru_cached settings instance."""

    def test_set_key_updates_settings(self, store, monkeypatch) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "groq_api_key", "")
        s, _ = store
        s.set_key("groq", "groq-sync")
        assert get_settings().groq_api_key == "groq-sync"

    def test_clear_key_clears_settings(self, store, monkeypatch) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "groq_api_key", "groq-sync")
        s, _ = store
        s.clear_key("groq")
        assert get_settings().groq_api_key == ""
