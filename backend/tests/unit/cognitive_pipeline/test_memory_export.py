"""The memory status and export endpoints — their shapes, and the folder clear.

Tests cover:
- Memory status endpoint
- Memory export endpoint
- Clear session endpoints (folder-based)
"""
import json
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestMemoryStatus:
    @pytest.mark.asyncio
    async def test_memory_status_returns_structure(self, client):
        """Should return the expected status fields even for non-existent agents."""
        resp = await client.get("/api/v1/cognitive/memory/nonexistent/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_folder" in data
        assert "session_count" in data
        assert "turn_count" in data
        assert "has_summaries" in data
        assert "fact_count" in data

    @pytest.mark.asyncio
    async def test_export_returns_structure(self, client):
        """Should return the expected export structure."""
        resp = await client.get("/api/v1/cognitive/memory/nonexistent/export")
        assert resp.status_code == 200
        data = resp.json()
        assert "agent_folder" in data
        assert "sessions" in data
        assert "summaries" in data
        assert "facts" in data
        assert "vector_sessions" in data

    @pytest.mark.asyncio
    async def test_clear_folder_all(self, client):
        resp = await client.delete("/api/v1/cognitive/memory/nonexistent/clear/all")
        assert resp.status_code == 200
        assert "All memory cleared" in resp.text
