"""The encryption key a bare install needs — and the one it must not invent twice.

Provider API keys at rest are encrypted with a Fernet key. The rule is ONE key
per installation: a random key per process makes stored secrets undecryptable,
and a key that must be pasted into `.env` before the app will start is a
first-run wall. So the service reads `COGITATE_ENCRYPTION_KEY` when it is set,
and otherwise generates a key ONCE, beside the database, with owner-only
permissions.
"""

from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from app.domain.providers.services import EncryptionService


@pytest.fixture
def install_dir(tmp_path):
    """A throwaway installation whose data dir is not the real one."""
    data = tmp_path / "install" / "data"
    data.mkdir(parents=True)
    return data


@pytest.fixture
def key_path(monkeypatch, install_dir):
    path = install_dir / ".encryption_key"
    monkeypatch.setattr(EncryptionService, "key_file_path", staticmethod(lambda: path))
    return path


def no_configured_key(monkeypatch):
    """Settings answer '' — the shape a bare install has."""
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(cogitate_encryption_key=""),
    )


class TestGeneratedOnFirstUse:
    def test_a_bare_install_gets_one_key_written_once(self, monkeypatch, key_path):
        no_configured_key(monkeypatch)

        first = EncryptionService()
        assert key_path.exists(), "the key must be persisted, not generated per process"
        assert oct(key_path.stat().st_mode & 0o777) == "0o600", "owner-only"

        second = EncryptionService()
        assert second.key == first.key, "a second instance must read the same key"

    def test_secrets_survive_a_new_instance(self, monkeypatch, key_path):
        no_configured_key(monkeypatch)
        token = EncryptionService().encrypt("sk-live-value")
        assert EncryptionService().decrypt(token) == "sk-live-value"

    def test_an_existing_key_file_is_reused_verbatim(self, monkeypatch, key_path):
        no_configured_key(monkeypatch)
        supplied = Fernet.generate_key().decode()
        key_path.write_text(supplied + "\n")

        assert EncryptionService().key == supplied.encode()


class TestConfiguredKeyWins:
    def test_a_valid_env_key_is_used_and_no_file_is_written(self, monkeypatch, key_path):
        supplied = Fernet.generate_key().decode()
        monkeypatch.setattr(
            "app.core.config.get_settings",
            lambda: SimpleNamespace(cogitate_encryption_key=supplied),
        )

        assert EncryptionService().key == supplied.encode()
        assert not key_path.exists()

    def test_a_placeholder_key_falls_back_instead_of_crashing(self, monkeypatch, key_path):
        """`.env.example` used to ship `your-fernet-encryption-key-here`."""
        monkeypatch.setattr(
            "app.core.config.get_settings",
            lambda: SimpleNamespace(cogitate_encryption_key="your-fernet-encryption-key-here"),
        )

        service = EncryptionService()
        assert key_path.exists(), "the invalid value must not leave the install with no key"
        assert EncryptionService().decrypt(service.encrypt("sk-x")) == "sk-x"
