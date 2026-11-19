"""
The multi-agent templates — existence, schema validity, and agent wiring.

Verifies templates are correctly stored in database and validate against schema.
"""

import sqlite3
import json

from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
from app.core.config import Paths, get_settings

# THE ONE-RESOLVER DOCTRINE: the shared-db path comes from the app's `Paths`,
# never a literal or a parent-walk. Reaching `cogitate.db` directly meant these
# tests wrote to the PRODUCTION database, and passed only because the code under
# test read the same production file. Under test, `Paths` resolves to the
# temporary copy — so test and code agree on the same database.
DB_PATH = str(Paths.from_settings(get_settings()).shared_db)


def get_template_from_db(template_id: str) -> dict:
    """Load template config from database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT config, workflow_type FROM workflow_templates WHERE id = ?',
        (template_id,)
    )
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise ValueError(f"Template '{template_id}' not found in database")
    
    config = json.loads(result[0])
    workflow_type = result[1]
    
    return {
        "config": config,
        "workflow_type": workflow_type
    }


class TestTemplateLoading:
    """Test template loading from database."""

    def test_hunter_editor_template_exists(self):
        """Test that Hunter + Editor template exists in database."""
        template = get_template_from_db("story-collab-hunter-editor")
        
        assert template["workflow_type"] == "multi_agent"
        assert "agents" in template["config"]
        assert len(template["config"]["agents"]) == 2

    def test_hunter_editor_template_schema_validation(self):
        """Test that Hunter + Editor template validates against schema."""
        template = get_template_from_db("story-collab-hunter-editor")
        config = MultiAgentConfig.model_validate(template["config"])
        
        assert len(config.agents) == 2
        assert config.agents[0].agent_id == 21  # Hunter
        assert config.agents[1].agent_id == 16  # Hemingway (Editor)
        assert config.context_mode == "isolated"
        assert config.final_output_key == "final_story"

    def test_hunter_editor_agent_configuration(self):
        """Test Hunter + Editor agent step configuration."""
        template = get_template_from_db("story-collab-hunter-editor")
        config = MultiAgentConfig.model_validate(template["config"])
        
        # Agent 1: Hunter (Writer)
        hunter_step = config.agents[0]
        assert hunter_step.step == 1
        assert hunter_step.input_key == "user_input"
        assert hunter_step.output_key == "draft"
        assert hunter_step.system_prompt_override is not None
        assert "Hunter" in hunter_step.system_prompt_override
        assert "fiction writer" in hunter_step.system_prompt_override
        
        # Agent 2: Editor (Hemingway)
        editor_step = config.agents[1]
        assert editor_step.step == 2
        assert editor_step.input_key == "draft"
        assert editor_step.output_key == "final_story"
        assert editor_step.system_prompt_override is not None
        assert "editor" in editor_step.system_prompt_override.lower()
        assert "refine" in editor_step.system_prompt_override.lower()

    def test_three_agent_template_exists(self):
        """Test that three-agent chain template exists."""
        template = get_template_from_db("creative-chain-triple")
        
        assert template["workflow_type"] == "multi_agent"
        config = MultiAgentConfig.model_validate(template["config"])
        
        assert len(config.agents) == 3
        assert config.agents[0].agent_id == 21  # Writer
        assert config.agents[1].agent_id == 16  # Editor
        assert config.agents[2].agent_id == 15  # Critic

    def test_tool_enhanced_template_exists(self):
        """Test that tool-enhanced template exists."""
        template = get_template_from_db("story-enhance-scheherazade-tooled")
        
        assert template["workflow_type"] == "multi_agent"
        config = MultiAgentConfig.model_validate(template["config"])
        
        assert len(config.agents) == 2
        assert config.agents[0].agent_id == 15  # Scheherazade
        assert config.agents[1].agent_id == 25  # Tooled Up
        assert config.context_mode == "cumulative"


class TestDataIntegrity:
    """Test data integrity for multi-agent templates."""

    def test_all_multi_agent_templates_validate(self):
        """Test that all multi-agent templates in DB validate correctly."""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT id, config FROM workflow_templates WHERE workflow_type = \"multi_agent\"'
        )
        
        templates = cursor.fetchall()
        conn.close()
        
        assert len(templates) >= 1, "No multi-agent templates found"
        
        for template_id, config_json in templates:
            config = json.loads(config_json)
            # Should not raise ValidationError
            validated = MultiAgentConfig.model_validate(config)
            assert len(validated.agents) >= 2, f"Template {template_id} has < 2 agents"

    def test_template_agents_have_valid_step_order(self):
        """Test that agent steps have valid step ordering."""
        template = get_template_from_db("story-collab-hunter-editor")
        config = MultiAgentConfig.model_validate(template["config"])
        
        # Steps should be sequential
        steps = [agent.step for agent in config.agents]
        assert steps == sorted(steps), "Agent steps are not in order"
        
        # Each step should be unique
        assert len(steps) == len(set(steps)), "Duplicate step numbers found"
