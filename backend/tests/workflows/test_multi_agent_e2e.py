"""
End-to-end integration tests for multi-agent workflows.

Tests full workflow execution from API call through graph execution.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.workflows.api.multi_agent_router import router as multi_agent_router
from app.domain.workflows.services.orchestration_service import MultiAgentOrchestrationService


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


class TestEndToEndWorkflowExecution:
    """End-to-end workflow execution tests."""

    @pytest.mark.asyncio
    async def test_service_can_load_template(self):
        """Test that service can load and validate template."""
        service = MultiAgentOrchestrationService()
        
        # Load template
        template = service.get_template_info("story-collab-hunter-editor")
        
        # Verify template structure
        assert template["id"] == "story-collab-hunter-editor"
        assert template["workflow_type"] == "multi_agent"
        assert "validated_config" in template
        
        config = template["validated_config"]
        assert len(config["agents"]) == 2
        assert config["context_mode"] == "isolated"
        assert config["final_output_key"] == "final_story"

    @pytest.mark.asyncio
    async def test_api_returns_template_details(self, client):
        """Test that API returns complete template details."""
        response = await client.get("/multi-agent/templates/story-collab-hunter-editor")
        
        assert response.status_code == 200
        template = response.json()
        
        # Verify all expected fields
        assert template["id"] == "story-collab-hunter-editor"
        assert template["name"] == "Story Collaboration: Hunter + Editor"
        assert template["agent_count"] == 2
        assert template["context_mode"] == "isolated"
        assert template["final_output_key"] == "final_story"
        
        # Verify agent chain
        agents = template["agents"]
        assert len(agents) == 2
        
        # Agent 1: Hunter (Writer)
        assert agents[0]["agent_id"] == 21
        assert agents[0]["input_key"] == "user_input"
        assert agents[0]["output_key"] == "draft"
        assert "Hunter" in agents[0]["system_prompt_override"]
        
        # Agent 2: Hemingway (Editor)
        assert agents[1]["agent_id"] == 16
        assert agents[1]["input_key"] == "draft"
        assert agents[1]["output_key"] == "final_story"
        assert "editor" in agents[1]["system_prompt_override"].lower()

    @pytest.mark.asyncio
    async def test_api_health_check(self, client):
        """Test health check endpoint."""
        response = await client.get("/multi-agent/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service"] == "multi-agent-orchestration"
        assert data["status"] in ["healthy", "unhealthy"]
        assert "templates_available" in data
        assert "database" in data

    @pytest.mark.asyncio
    async def test_all_templates_accessible(self, client):
        """Test that all multi-agent templates are accessible via API."""
        # Get list of templates
        response = await client.get("/multi-agent/templates")
        assert response.status_code == 200
        templates = response.json()
        
        assert len(templates) >= 3, "Should have at least 3 multi-agent templates"
        
        # Each template should be accessible individually
        for template in templates:
            template_id = template["id"]
            
            detail_response = await client.get(f"/multi-agent/templates/{template_id}")
            assert detail_response.status_code == 200, f"Failed to get details for {template_id}"
            
            detail = detail_response.json()
            assert detail["id"] == template_id
            assert "agents" in detail
            assert len(detail["agents"]) >= 2


class TestGraphConstruction:
    """Test graph construction from templates."""

    def test_graph_builds_from_template_config(self):
        """Test that graph builds correctly from template config."""
        from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
        from app.workflows.graphs.multi_agent_graph import build_multi_agent_graph
        
        service = MultiAgentOrchestrationService()
        template = service.get_template_info("story-collab-hunter-editor")
        
        # Validate config
        config = MultiAgentConfig.model_validate(template["config"])
        
        # Build graph
        graph = build_multi_agent_graph(config)
        
        assert graph is not None
        assert hasattr(graph, 'compile')

    def test_three_agent_graph_builds(self):
        """Test that 3-agent graph builds correctly."""
        from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
        from app.workflows.graphs.multi_agent_graph import build_multi_agent_graph
        
        service = MultiAgentOrchestrationService()
        template = service.get_template_info("creative-chain-triple")
        
        config = MultiAgentConfig.model_validate(template["config"])
        graph = build_multi_agent_graph(config)
        
        assert graph is not None


class TestSchemaValidation:
    """Test schema validation end-to-end."""

    def test_template_config_validates_against_schema(self):
        """Test that template config validates against MultiAgentConfig schema."""
        from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
        
        service = MultiAgentOrchestrationService()
        
        # Test all multi-agent templates
        templates = service.list_multi_agent_templates()
        
        for template_info in templates:
            template = service.get_template_info(template_info["id"])
            
            # Should not raise ValidationError
            config = MultiAgentConfig.model_validate(template["config"])
            
            # Verify structure
            assert len(config.agents) >= 2
            assert config.context_mode in ["cumulative", "isolated"]
            assert config.final_output_key

    def test_agent_step_chaining_validates(self):
        """Test that agent steps are properly chained (output → input)."""
        from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
        
        service = MultiAgentOrchestrationService()
        template = service.get_template_info("story-collab-hunter-editor")
        config = MultiAgentConfig.model_validate(template["config"])
        
        # Verify chaining: Agent 1 output = Agent 2 input
        agents = sorted(config.agents, key=lambda a: a.step)
        
        for i in range(len(agents) - 1):
            current_output = agents[i].output_key
            next_input = agents[i + 1].input_key
            
            # For isolated mode, output of one should match input of next
            assert current_output == next_input, \
                f"Agent {i+1} output '{current_output}' doesn't match Agent {i+2} input '{next_input}'"


class TestIntegrationDataFlow:
    """Test data flow through multi-agent workflow."""

    def test_input_output_key_mapping(self):
        """Test that input/output keys are correctly mapped."""
        from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
        
        service = MultiAgentOrchestrationService()
        template = service.get_template_info("story-collab-hunter-editor")
        config = MultiAgentConfig.model_validate(template["config"])
        
        # Build map of output keys
        output_keys = {agent.step: agent.output_key for agent in config.agents}
        input_keys = {agent.step: agent.input_key for agent in config.agents}
        
        # First agent should take user_input
        assert input_keys[1] == "user_input"
        
        # Last agent should output to final_output_key
        last_step = len(config.agents)
        assert output_keys[last_step] == config.final_output_key

    def test_context_mode_configuration(self):
        """Test that context mode is correctly configured."""
        from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
        
        service = MultiAgentOrchestrationService()
        
        # Test isolated mode template
        template = service.get_template_info("story-collab-hunter-editor")
        config = MultiAgentConfig.model_validate(template["config"])
        assert config.context_mode == "isolated"
        
        # Test cumulative mode template
        template = service.get_template_info("creative-chain-triple")
        config = MultiAgentConfig.model_validate(template["config"])
        assert config.context_mode == "cumulative"
