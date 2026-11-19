"""
The multi-agent API — template listing and the not-found paths.

Tests API endpoints for multi-agent workflow execution.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.workflows.api.multi_agent_router import router as multi_agent_router


@pytest.fixture(scope="session")
def test_app():
    """Create test FastAPI app with multi-agent router."""
    app = FastAPI()
    app.include_router(multi_agent_router)
    return app


@pytest.fixture
async def client(test_app):
    """Create async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestMultiAgentAPIEndpoints:
    """Test multi-agent API endpoint availability."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test multi-agent health check endpoint."""
        response = await client.get("/multi-agent/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "unhealthy"]
        assert data["service"] == "multi-agent-orchestration"

    @pytest.mark.asyncio
    async def test_list_templates_endpoint(self, client):
        """Test listing multi-agent templates."""
        response = await client.get("/multi-agent/templates")
        
        assert response.status_code == 200
        templates = response.json()
        
        assert isinstance(templates, list)
        assert len(templates) >= 1, "Should have at least 1 multi-agent template"
        
        # Check template structure
        template = templates[0]
        assert "id" in template
        assert "name" in template
        assert "workflow_type" in template

    @pytest.mark.asyncio
    async def test_get_template_detail_endpoint(self, client):
        """Test getting template details."""
        response = await client.get("/multi-agent/templates/story-collab-hunter-editor")
        
        assert response.status_code == 200
        template = response.json()
        
        assert template["id"] == "story-collab-hunter-editor"
        assert template["agent_count"] == 2
        assert template["context_mode"] in ["cumulative", "isolated"]
        assert "agents" in template
        assert len(template["agents"]) == 2

    @pytest.mark.asyncio
    async def test_get_nonexistent_template(self, client):
        """Test getting nonexistent template returns 400."""
        response = await client.get("/multi-agent/templates/nonexistent-template")
        
        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_get_non_multi_agent_template(self, client):
        """Test getting non-multi-agent template returns 400."""
        # agent-hello is "advanced" type, not "multi_agent"
        response = await client.get("/multi-agent/templates/agent-hello")
        
        assert response.status_code == 400


class TestMultiAgentExecuteEndpoint:
    """Test multi-agent workflow execution endpoint."""

    @pytest.mark.asyncio
    async def test_execute_request_validation(self, client):
        """Test that execute endpoint validates request."""
        # Missing required fields
        response = await client.post("/multi-agent/execute", json={})
        
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_execute_with_invalid_template(self, client):
        """Test execution with invalid template."""
        response = await client.post("/multi-agent/execute", json={
            "template_id": "nonexistent-template",
            "initial_message": "Test message"
        })
        
        # Should return 400 or 500 (template not found or execution failed)
        assert response.status_code in [400, 404, 500]


class TestIntegration:
    """Integration tests for multi-agent API."""

    @pytest.mark.asyncio
    async def test_templates_list_contains_expected_templates(self, client):
        """Test that templates list contains expected templates."""
        response = await client.get("/multi-agent/templates")
        
        assert response.status_code == 200
        templates = response.json()
        
        template_ids = [t["id"] for t in templates]
        
        # Check expected templates
        expected = [
            "story-collab-hunter-editor",
            "story-enhance-scheherazade-tooled",
            "creative-chain-triple"
        ]
        
        for expected_id in expected:
            assert expected_id in template_ids, f"Missing template: {expected_id}"

    @pytest.mark.asyncio
    async def test_hunter_editor_template_details(self, client):
        """Test Hunter + Editor template details."""
        response = await client.get("/multi-agent/templates/story-collab-hunter-editor")
        
        assert response.status_code == 200
        template = response.json()
        
        # Verify template structure
        assert template["name"] == "Story Collaboration: Hunter + Editor"
        assert template["agent_count"] == 2
        assert template["context_mode"] == "isolated"
        assert template["final_output_key"] == "final_story"
        
        # Verify agents
        agents = template["agents"]
        assert agents[0]["agent_id"] == 21  # Hunter
        assert agents[1]["agent_id"] == 16  # Hemingway
        
        # Verify input/output key chaining
        assert agents[0]["output_key"] == "draft"
        assert agents[1]["input_key"] == "draft"

    @pytest.mark.asyncio
    async def test_three_agent_template_details(self, client):
        """Test three-agent template details."""
        response = await client.get("/multi-agent/templates/creative-chain-triple")
        
        assert response.status_code == 200
        template = response.json()
        
        assert template["agent_count"] == 3
        assert template["context_mode"] == "cumulative"
        
        agents = template["agents"]
        assert len(agents) == 3
        assert agents[0]["agent_id"] == 21  # Writer
        assert agents[1]["agent_id"] == 16  # Editor
        assert agents[2]["agent_id"] == 15  # Critic
