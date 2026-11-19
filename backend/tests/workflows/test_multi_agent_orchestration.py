"""
The multi-agent orchestration service — template lookup and its error paths.

Verifies template loading, validation, and execution.
"""

import pytest

from app.domain.workflows.services.orchestration_service import (
    MultiAgentOrchestrationService,
    WorkflowResult,
    MultiAgentExecuteRequest,
)


class TestServiceInitialization:
    """Test orchestration service initialization."""

    def test_service_init(self):
        """Test service initializes correctly."""
        service = MultiAgentOrchestrationService()
        
        assert service is not None
        assert service.db_path.exists()


class TestTemplateLoading:
    """Test template loading from database."""

    def test_list_multi_agent_templates(self):
        """Test listing multi-agent templates."""
        service = MultiAgentOrchestrationService()
        
        templates = service.list_multi_agent_templates()
        
        assert len(templates) >= 1, "Should have at least 1 multi-agent template"
        
        # Check template structure
        template_ids = [t["id"] for t in templates]
        assert "story-collab-hunter-editor" in template_ids

    def test_get_template_info(self):
        """Test getting detailed template info."""
        service = MultiAgentOrchestrationService()
        
        template = service.get_template_info("story-collab-hunter-editor")
        
        assert template["id"] == "story-collab-hunter-editor"
        assert template["workflow_type"] == "multi_agent"
        assert "validated_config" in template
        assert len(template["validated_config"]["agents"]) == 2

    def test_get_template_info_nonexistent(self):
        """Test getting info for nonexistent template."""
        service = MultiAgentOrchestrationService()
        
        with pytest.raises(ValueError, match="not found"):
            service.get_template_info("nonexistent-template")

    def test_get_template_info_not_multi_agent(self):
        """Test getting info for non-multi-agent template."""
        service = MultiAgentOrchestrationService()
        
        # Try with a template that's not multi_agent type
        with pytest.raises(ValueError, match="not a multi-agent template"):
            service.get_template_info("agent-hello")  # This is "advanced" type


class TestRequestValidation:
    """Test request model validation."""

    def test_execute_request_minimal(self):
        """Test minimal execute request."""
        request = MultiAgentExecuteRequest(
            template_id="story-collab-hunter-editor",
            initial_message="Write a story"
        )
        
        assert request.template_id == "story-collab-hunter-editor"
        assert request.initial_message == "Write a story"
        assert request.workflow_id is None

    def test_execute_request_with_custom_workflow_id(self):
        """Test request with custom workflow ID."""
        request = MultiAgentExecuteRequest(
            template_id="story-collab-hunter-editor",
            initial_message="Write a story",
            workflow_id="wf-custom-123"
        )
        
        assert request.workflow_id == "wf-custom-123"


class TestWorkflowResult:
    """Test workflow result model."""

    def test_workflow_result_completed(self):
        """Test workflow result for completed execution."""
        result = WorkflowResult(
            workflow_id="wf-test-123",
            template_id="story-collab-hunter-editor",
            status="completed",
            output="Final story content",
            started_at="2026-03-30T12:00:00Z",
            completed_at="2026-03-30T12:00:05Z",
            elapsed_seconds=5.0
        )
        
        assert result.status == "completed"
        assert result.output == "Final story content"
        assert result.error is None

    def test_workflow_result_error(self):
        """Test workflow result for error case."""
        result = WorkflowResult(
            workflow_id="wf-test-123",
            template_id="story-collab-hunter-editor",
            status="error",
            output=None,
            error="Agent not found",
            started_at="2026-03-30T12:00:00Z",
            completed_at="2026-03-30T12:00:01Z",
            elapsed_seconds=1.0
        )
        
        assert result.status == "error"
        assert result.error == "Agent not found"


class TestIntegration:
    """Integration tests for orchestration service."""

    @pytest.mark.asyncio
    async def test_template_config_validates(self):
        """Test that template config validates correctly through service."""
        service = MultiAgentOrchestrationService()
        
        # Load and validate template
        template = service.get_template_info("story-collab-hunter-editor")
        
        config = template["validated_config"]
        assert len(config["agents"]) == 2
        assert config["context_mode"] == "isolated"
        assert config["final_output_key"] == "final_story"
        
        # Verify agent configuration
        agents = config["agents"]
        assert agents[0]["agent_id"] == 21  # Hunter
        assert agents[1]["agent_id"] == 16  # Hemingway
        
        # Verify input/output key chaining
        assert agents[0]["output_key"] == "draft"
        assert agents[1]["input_key"] == "draft"

    @pytest.mark.asyncio
    async def test_three_agent_template_validates(self):
        """Test that 3-agent template validates correctly."""
        service = MultiAgentOrchestrationService()
        
        template = service.get_template_info("creative-chain-triple")
        
        config = template["validated_config"]
        assert len(config["agents"]) == 3
        assert config["context_mode"] == "cumulative"
        
        # Verify agent chain
        agents = config["agents"]
        assert agents[0]["agent_id"] == 21  # Writer
        assert agents[1]["agent_id"] == 16  # Editor
        assert agents[2]["agent_id"] == 15  # Critic

    def test_all_multi_agent_templates_listed(self):
        """Test that all multi-agent templates are listed."""
        service = MultiAgentOrchestrationService()
        
        templates = service.list_multi_agent_templates()
        
        template_ids = [t["id"] for t in templates]
        
        # Check expected templates exist
        expected_templates = [
            "story-collab-hunter-editor",
            "story-enhance-scheherazade-tooled",
            "creative-chain-triple"
        ]
        
        for expected_id in expected_templates:
            assert expected_id in template_ids, f"Missing template: {expected_id}"
