"""API tests for the provider key management endpoints (Keys tab)."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.env_key_store import env_key_store
from app.infrastructure.database.models import Provider


@pytest.fixture
def tmp_env(monkeypatch, tmp_path) -> Path:
    """Point the EnvKeyStore singleton at a temp .env (never the real one)."""
    env = tmp_path / ".env"
    env.write_text("# test env\n")
    monkeypatch.setattr(env_key_store, "env_path", env)
    return env


@pytest.fixture
async def key_providers(test_engine) -> list[int]:
    """Create two providers: one with a stored key, one without."""
    async with AsyncSession(test_engine) as session:
        p1 = Provider(
            name="keys-test-a", provider_type="openrouter",
            base_url="https://x.test", is_active=True,
        )
        p2 = Provider(
            name="keys-test-b", provider_type="ollama",
            base_url="http://localhost:11434", is_active=True,
        )
        session.add_all([p1, p2])
        await session.commit()
        await session.refresh(p1)
        await session.refresh(p2)
        return [p1.id, p2.id]


class TestProviderKeyManagement:
    """Keys-tab endpoints: list, set, clear."""

    @pytest.mark.anyio
    async def test_list_shows_sources(
        self, client: AsyncClient, key_providers: list[int], tmp_env: Path
    ) -> None:
        resp = await client.get("/api/v1/providers/managed/keys")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 2
        by_id = {p["provider_id"]: p for p in data["providers"]}
        # ollama provider → none (no key needed / none stored)
        assert by_id[key_providers[1]]["key_source"] == "none"

    @pytest.mark.anyio
    async def test_set_and_clear_key(
        self, client: AsyncClient, key_providers: list[int], monkeypatch, tmp_env: Path
    ) -> None:
        # Force settings key empty so source detection is deterministic
        from app.core.config import get_settings
        monkeypatch.setattr(get_settings(), "ollama_cloud_api_key", "")
        monkeypatch.setattr(get_settings(), "openrouter_api_key", "")

        pid = key_providers[0]

        # Set → written to .env (not the DB)
        resp = await client.put(
            f"/api/v1/providers/managed/{pid}/key",
            json={"api_key": "test-key-abc"},
        )
        assert resp.status_code == 200
        assert resp.json()["key_source"] == "env"
        assert "OPENROUTER_API_KEY=test-key-abc" in tmp_env.read_text()

        # List reflects env
        resp = await client.get("/api/v1/providers/managed/keys")
        by_id = {p["provider_id"]: p for p in resp.json()["providers"]}
        assert by_id[pid]["key_source"] == "env"

        # Clear → removed from .env
        resp = await client.delete(f"/api/v1/providers/managed/{pid}/key")
        assert resp.status_code == 200
        assert "OPENROUTER_API_KEY" not in tmp_env.read_text()

        resp = await client.get("/api/v1/providers/managed/keys")
        by_id = {p["provider_id"]: p for p in resp.json()["providers"]}
        assert by_id[pid]["key_source"] == "none"

    @pytest.mark.anyio
    async def test_set_requires_key(
        self, client: AsyncClient, key_providers: list[int]
    ) -> None:
        resp = await client.put(
            f"/api/v1/providers/managed/{key_providers[0]}/key",
            json={"api_key": "   "},
        )
        assert resp.status_code == 400
