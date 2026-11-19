"""
The parallel workflow templates — existence, validation and graph building.
"""

import sqlite3
import json

from typing import Any, cast
from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
from app.workflows.graphs.multi_agent_graph import build_multi_agent_graph
from app.core.config import Paths, get_settings

# THE ONE-RESOLVER DOCTRINE: the shared-db path comes from the app's `Paths`,
# never a literal or a parent-walk. Reaching `cogitate.db` directly meant these
# tests wrote to the PRODUCTION database, and passed only because the code under
# test read the same production file. Under test, `Paths` resolves to the
# temporary copy — so test and code agree on the same database.
DB_PATH = str(Paths.from_settings(get_settings()).shared_db)


def load_template(template_id: str) -> dict:
    """Load a template from the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT config FROM workflow_templates WHERE id = ?",
        (template_id,)
    )
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        raise ValueError(f"Template {template_id} not found")
    
    return cast(dict[Any, Any], json.loads(result[0]))


class TestParallelTemplates:
    """Test parallel workflow templates from database."""

    def test_parallel_research_analysis_template_exists(self):
        """Test that parallel-research-analysis template exists."""
        config_dict = load_template("parallel-research-analysis")
        assert config_dict is not None
        assert config_dict["execution_mode"] == "parallel"
        assert config_dict["parallel_groups"] == [[1, 2], [3]]

    def test_parallel_research_analysis_validates(self):
        """Test that parallel-research-analysis validates correctly."""
        config_dict = load_template("parallel-research-analysis")
        config = MultiAgentConfig.model_validate(config_dict)
        
        assert config.execution_mode == "parallel"
        assert len(config.agents) == 3
        assert config.agents[0].enable_tools is True
        assert len(config.agents[0].tools) > 0

    def test_parallel_research_analysis_builds_graph(self):
        """Test that parallel-research-analysis builds graph successfully."""
        config_dict = load_template("parallel-research-analysis")
        config = MultiAgentConfig.model_validate(config_dict)
        
        graph = build_multi_agent_graph(config)
        assert graph is not None

    def test_parallel_creative_review_template_exists(self):
        """Test that parallel-creative-review template exists."""
        config_dict = load_template("parallel-creative-review")
        assert config_dict is not None
        assert config_dict["execution_mode"] == "parallel"
        assert config_dict["parallel_groups"] == [[1, 2, 3], [4]]

    def test_parallel_creative_review_validates(self):
        """Test that parallel-creative-review validates correctly."""
        config_dict = load_template("parallel-creative-review")
        config = MultiAgentConfig.model_validate(config_dict)
        
        assert config.execution_mode == "parallel"
        assert len(config.agents) == 4
        assert config.parallel_groups == [[1, 2, 3], [4]]

    def test_parallel_creative_review_builds_graph(self):
        """Test that parallel-creative-review builds graph successfully."""
        config_dict = load_template("parallel-creative-review")
        config = MultiAgentConfig.model_validate(config_dict)
        
        graph = build_multi_agent_graph(config)
        assert graph is not None

    def test_parallel_data_pipeline_template_exists(self):
        """Test that parallel-data-pipeline template exists."""
        config_dict = load_template("parallel-data-pipeline")
        assert config_dict is not None
        assert config_dict["execution_mode"] == "parallel"

    def test_parallel_data_pipeline_validates(self):
        """Test that parallel-data-pipeline validates correctly."""
        config_dict = load_template("parallel-data-pipeline")
        config = MultiAgentConfig.model_validate(config_dict)
        
        assert config.execution_mode == "parallel"
        assert len(config.agents) == 3
        assert config.agents[0].enable_tools is True
        assert len(config.agents[0].tools) == 2  # calculator and datetime

    def test_parallel_data_pipeline_builds_graph(self):
        """Test that parallel-data-pipeline builds graph successfully."""
        config_dict = load_template("parallel-data-pipeline")
        config = MultiAgentConfig.model_validate(config_dict)
        
        graph = build_multi_agent_graph(config)
        assert graph is not None


class TestSequentialBaselineTemplate:
    """Test sequential baseline template for comparison."""

    def test_sequential_baseline_template_exists(self):
        """Test that sequential-tool-enhanced-baseline template exists."""
        config_dict = load_template("sequential-tool-enhanced-baseline")
        assert config_dict is not None
        assert config_dict["execution_mode"] == "sequential"

    def test_sequential_baseline_validates(self):
        """Test that sequential-tool-enhanced-baseline validates correctly."""
        config_dict = load_template("sequential-tool-enhanced-baseline")
        config = MultiAgentConfig.model_validate(config_dict)
        
        assert config.execution_mode == "sequential"
        assert len(config.agents) == 3
        assert config.agents[0].enable_tools is True

    def test_sequential_baseline_builds_graph(self):
        """Test that sequential-tool-enhanced-baseline builds graph successfully."""
        config_dict = load_template("sequential-tool-enhanced-baseline")
        config = MultiAgentConfig.model_validate(config_dict)
        
        graph = build_multi_agent_graph(config)
        assert graph is not None


class TestTemplateComparison:
    """Test comparison between parallel and sequential templates."""

    def test_parallel_vs_sequential_agent_count(self):
        """Test that parallel and sequential baseline have same agent count."""
        parallel_config = MultiAgentConfig.model_validate(
            load_template("parallel-research-analysis")
        )
        sequential_config = MultiAgentConfig.model_validate(
            load_template("sequential-tool-enhanced-baseline")
        )
        
        # Both should have 3 agents
        assert len(parallel_config.agents) == 3
        assert len(sequential_config.agents) == 3

    def test_parallel_vs_sequential_execution_mode(self):
        """Test that parallel and sequential have different execution modes."""
        parallel_config = MultiAgentConfig.model_validate(
            load_template("parallel-research-analysis")
        )
        sequential_config = MultiAgentConfig.model_validate(
            load_template("sequential-tool-enhanced-baseline")
        )
        
        assert parallel_config.execution_mode == "parallel"
        assert sequential_config.execution_mode == "sequential"

    def test_parallel_vs_sequential_agent_ids_match(self):
        """Test that parallel and sequential use same agent IDs."""
        parallel_config = MultiAgentConfig.model_validate(
            load_template("parallel-research-analysis")
        )
        sequential_config = MultiAgentConfig.model_validate(
            load_template("sequential-tool-enhanced-baseline")
        )
        
        parallel_agent_ids = [a.agent_id for a in parallel_config.agents]
        sequential_agent_ids = [a.agent_id for a in sequential_config.agents]
        
        assert parallel_agent_ids == sequential_agent_ids
