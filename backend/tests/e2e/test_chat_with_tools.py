"""
E2E Tests — API endpoint availability and basic connectivity.
"""

import pytest
import pytest_asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1"


@pytest_asyncio.fixture
async def client():
    async with httpx.AsyncClient(timeout=30.0) as c:
        yield c


# =============================================================================
# Integration Verification Tests
# =============================================================================


class TestE2EIntegrationVerification:
    """Verify all integration points work together."""

    @pytest.mark.asyncio
    async def test_api_endpoints_available(self, client: httpx.AsyncClient):
        health = await client.get(f"{BASE_URL}/health")
        assert health.status_code == 200
        assert health.json()["status"] == "healthy"

        tools = await client.get(f"{BASE_URL}/tools")
        assert tools.status_code == 200

        agents = await client.get(f"{BASE_URL}/agents")
        assert agents.status_code == 200

    @pytest.mark.skip(reason="Requires agent creation + tool enabling — not applicable in current arch")
    @pytest.mark.asyncio
    async def test_tool_execution_endpoint(self, client: httpx.AsyncClient):
        pass

    @pytest.mark.skip(reason="Agent-based chat is not exercised in this E2E suite")
    @pytest.mark.asyncio
    async def test_chat_without_tools_enabled(self, client: httpx.AsyncClient):
        pass
