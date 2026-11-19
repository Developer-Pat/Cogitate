"""
Multi-agent workflow orchestration service.

Executes multi-agent workflows by:
1. Loading template configuration from database
2. Building LangGraph from multi-agent config
3. Managing state and context passing
4. Executing the workflow and returning results
"""

import logging
import uuid
import sqlite3
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, UTC

from pydantic import BaseModel, Field

from app.domain.workflows.schemas.multi_agent_config import MultiAgentConfig
from app.workflows.graphs.multi_agent_graph import build_multi_agent_graph
from app.workflows.state.workflow_state import RunMetadata
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


# Database path — resolve from the app's canonical BASE_DIR so we always
# use the same cogitate.db as the SQLAlchemy engine, regardless of CWD.
from app.core.config import Paths, get_settings
from pathlib import Path
DB_PATH = Paths.from_settings(get_settings()).shared_db


class WorkflowResult(BaseModel):
    """Result of multi-agent workflow execution."""
    workflow_id: str
    template_id: str
    status: str  # "completed", "error", "cancelled"
    output: Any
    agent_outputs: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: str
    completed_at: str
    elapsed_seconds: float = 0.0


class MultiAgentExecuteRequest(BaseModel):
    """Request to execute a multi-agent workflow."""
    template_id: str = Field(..., description="ID of multi-agent template")
    initial_message: str = Field(..., description="Initial user input/message")
    workflow_id: Optional[str] = Field(None, description="Optional custom workflow ID")


class MultiAgentOrchestrationService:
    """
    Service for orchestrating multi-agent workflows.

    This service:
    1. Loads multi-agent templates from database
    2. Validates configuration against schema
    3. Builds LangGraph workflow dynamically
    4. Executes the workflow with state management
    5. Returns structured results

    Example:
        ```python
        service = MultiAgentOrchestrationService()
        result = await service.execute_multi_agent(
            template_id="story-collab-hunter-editor",
            initial_message="Write a sci-fi story about time travel"
        )
        print(result.output)  # Final story
        ```
    """

    @property
    def db_path(self) -> Path:
        """The shared database, resolved on EVERY read.

        This was a module-level constant captured at import. That cannot follow
        a redirected installation: under test the harness points DATABASE_URL at
        a copy of a migrated DB, and a path bound at import (or in __init__)
        keeps naming the original — producing "no such table" against the wrong
        file. The resolver was always correct; it was just applied too early.
        """
        from app.core.config import Paths, get_settings

        override: Path | None = getattr(self, "_db_path_override", None)
        if override is not None:
            return override
        return Paths.from_settings(get_settings()).shared_db

    @db_path.setter
    def db_path(self, value) -> None:
        """An explicit override — the test seam.

        Kept deliberately: tests point a service at their own database.
        The resolver above is the DEFAULT, not a cage.
        """
        self._db_path_override = value

    def _load_template_from_db(self, template_id: str) -> Dict[str, Any]:
        """
        Load workflow template from database.

        Args:
            template_id: ID of template to load

        Returns:
            Template configuration dict

        Raises:
            ValueError: If template not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM workflow_templates WHERE id = ?",
            (template_id,)
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            raise ValueError(f"Template '{template_id}' not found in database")

        # Convert to dict
        template = dict(row)
        template["config"] = json.loads(template["config"])
        template["tags"] = json.loads(template["tags"]) if template["tags"] else []

        logger.info(f"✅ Loaded template: {template_id} - {template['name']}")
        logger.info(f"   Workflow type: {template['workflow_type']}")
        logger.info(f"   Tags: {template['tags']}")

        return template

    def _validate_multi_agent_config(self, config: Dict[str, Any]) -> MultiAgentConfig:
        """
        Validate template config as multi-agent configuration.

        Args:
            config: Template config dict

        Returns:
            Validated MultiAgentConfig

        Raises:
            ValidationError: If config is invalid
        """
        return MultiAgentConfig.model_validate(config)

    def _build_initial_state(
        self,
        workflow_id: str,
        template_id: str,
        initial_input: str,
        config: MultiAgentConfig
    ) -> Dict[str, Any]:
        """
        Build initial workflow state.

        Args:
            workflow_id: Unique workflow execution ID
            template_id: Template being executed
            initial_input: Initial user input
            config: Validated multi-agent config

        Returns:
            Initial state dict for LangGraph
        """
        now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

        # Set up inputs with user input
        inputs = {"user_input": initial_input}

        # Create metadata
        metadata = RunMetadata(
            workflow_id=workflow_id,
            template_id=template_id,
            started_at=now,
            status="running",
            config=config.model_dump(),
            tags=None
        )

        # Build initial state
        initial_state = {
            "messages": [HumanMessage(content=f"Starting multi-agent workflow: {initial_input[:100]}...")],
            "workflow_id": workflow_id,
            "template_id": template_id,
            "inputs": inputs,
            "current_step": None,
            "execution_result": None,
            "outputs": {},
            "approval_required": False,
            "approval_status": None,
            "metadata": metadata,
            "tool_calls_history": [],
            "tool_loop_count": 0,
        }

        logger.info(f"📋 Initial state created for workflow {workflow_id}")
        logger.info(f"   Template: {template_id}")
        logger.info(f"   Input: {initial_input[:100]}...")

        return initial_state

    async def execute_multi_agent(
        self,
        template_id: str,
        initial_message: str,
        workflow_id: Optional[str] = None
    ) -> WorkflowResult:
        """
        Execute a multi-agent workflow.

        This is the main entry point for executing multi-agent workflows.
        It loads the template, builds the graph, and executes it.

        Args:
            template_id: ID of multi-agent template
            initial_message: Initial user input/message
            workflow_id: Optional custom workflow ID (generated if not provided)

        Returns:
            WorkflowResult with execution output

        Raises:
            ValueError: If template not found or invalid
            Exception: If workflow execution fails
        """
        import time
        start_time = time.time()
        
        # Generate workflow ID if not provided
        if not workflow_id:
            workflow_id = f"wf-ma-{uuid.uuid4().hex[:12]}"

        logger.info("🚀 Starting multi-agent workflow execution")
        logger.info(f"   Workflow ID: {workflow_id}")
        logger.info(f"   Template ID: {template_id}")
        logger.info(f"   Initial message: {initial_message[:100]}...")

        try:
            # Step 1: Load template from database
            template = self._load_template_from_db(template_id)

            # Step 2: Validate multi-agent config
            config = self._validate_multi_agent_config(template["config"])
            logger.info(f"✅ Multi-agent config validated: {len(config.agents)} agents")

            # Step 3: Build LangGraph
            graph = build_multi_agent_graph(config)
            compiled_graph = graph.compile()
            logger.info("✅ LangGraph compiled successfully")

            # Step 4: Build initial state
            initial_state = self._build_initial_state(
                workflow_id=workflow_id,
                template_id=template_id,
                initial_input=initial_message,
                config=config
            )

            # Step 5: Execute graph
            logger.info("📤 Executing multi-agent workflow...")
            result_state = compiled_graph.invoke(initial_state)
            logger.info("📥 Workflow execution completed")

            # Step 6: Extract results
            elapsed_seconds = time.time() - start_time
            now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

            # Get final output
            outputs = result_state.get("outputs", {})
            final_output = outputs.get(config.final_output_key)

            # Collect all agent outputs
            agent_outputs = {}
            for key, value in outputs.items():
                if isinstance(value, dict) and "agent_name" in value:
                    agent_outputs[f"step_{value.get('step', 'unknown')}"] = {
                        "agent_name": value["agent_name"],
                        "agent_id": value["agent_id"],
                        "content": value["content"],
                    }

            # Check for errors
            if "error" in outputs:
                return WorkflowResult(
                    workflow_id=workflow_id,
                    template_id=template_id,
                    status="error",
                    output=outputs.get("error"),
                    agent_outputs=agent_outputs,
                    error=outputs.get("error"),
                    started_at=initial_state["metadata"].started_at,
                    completed_at=now,
                    elapsed_seconds=elapsed_seconds
                )

            logger.info("✅ Multi-agent workflow completed successfully")
            logger.info(f"   Final output key: {config.final_output_key}")
            logger.info(f"   Agent outputs: {len(agent_outputs)}")
            logger.info(f"   Elapsed time: {elapsed_seconds:.2f}s")

            return WorkflowResult(
                workflow_id=workflow_id,
                template_id=template_id,
                status="completed",
                output=final_output,
                agent_outputs=agent_outputs,
                started_at=initial_state["metadata"].started_at,
                completed_at=now,
                elapsed_seconds=elapsed_seconds
            )

        except Exception as e:
            elapsed_seconds = time.time() - start_time
            now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            
            logger.error(f"❌ Multi-agent workflow execution failed: {str(e)}", exc_info=True)
            
            return WorkflowResult(
                workflow_id=workflow_id,
                template_id=template_id,
                status="error",
                output=None,
                agent_outputs=None,
                error=str(e),
                started_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                completed_at=now,
                elapsed_seconds=elapsed_seconds
            )

    def list_multi_agent_templates(self) -> List[Dict[str, Any]]:
        """
        List all multi-agent templates in database.

        Returns:
            List of template info dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, name, description, tags, workflow_type FROM workflow_templates WHERE workflow_type = 'multi_agent'"
        )

        templates = []
        for row in cursor.fetchall():
            template = dict(row)
            template["tags"] = json.loads(template["tags"]) if template["tags"] else []
            templates.append(template)

        conn.close()

        logger.info(f"📋 Found {len(templates)} multi-agent templates")
        return templates

    def get_template_info(self, template_id: str) -> Dict[str, Any]:
        """
        Get detailed info about a specific multi-agent template.

        Args:
            template_id: ID of template

        Returns:
            Template info with config

        Raises:
            ValueError: If template not found
        """
        template = self._load_template_from_db(template_id)
        
        if template["workflow_type"] != "multi_agent":
            raise ValueError(f"Template '{template_id}' is not a multi-agent template")
        
        # Validate config
        config = self._validate_multi_agent_config(template["config"])
        template["validated_config"] = config.model_dump()
        
        return template
