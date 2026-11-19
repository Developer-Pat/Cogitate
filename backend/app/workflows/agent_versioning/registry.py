"""
Agent configuration schema and registry.

Defines:
- AgentConfig: Schema for agent configuration
- AgentVersion: Version metadata
- AgentRegistry: In-memory registry for agent configurations

Note: This is an in-memory implementation for Phase 2.
In production, integrate with database persistence.
"""

from typing import Any, Optional, Dict, List
from datetime import datetime, UTC
from pydantic import BaseModel, ConfigDict, Field


class AgentConfig(BaseModel):
    """
    Agent configuration schema.

    Defines all parameters needed to instantiate and run an agent.

    Attributes:
        id: Unique agent identifier
        name: Human-readable name
        version: Semantic version (e.g., "1.0.0")
        description: Agent purpose and capabilities
        role: Agent role/persona (for role-playing)
        goal: Primary objective
        backstory: Context and personality
        llm_model: LLM model to use (e.g., "gpt-4o-mini")
        temperature: LLM temperature (0.0-2.0)
        tools: List of tool IDs available to agent
        metadata: Additional configuration
    """
    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Human-readable name")
    version: str = Field(..., description="Semantic version")
    description: str = Field(..., description="Agent purpose and capabilities")
    
    # Role-playing attributes (CrewAI-style)
    role: Optional[str] = Field(None, description="Agent role/persona")
    goal: Optional[str] = Field(None, description="Primary objective")
    backstory: Optional[str] = Field(None, description="Context and personality")
    
    # LLM configuration
    llm_model: str = Field(default="gpt-4o-mini", description="LLM model to use")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="LLM temperature")
    # REMOVED (G-I, 2026-09-25): `max_tokens: int = Field(default=2000, ge=1)` — a
    # second declaration home, in another domain, that NOTHING read (no executor, no
    # resolver, no export consumer imported it) and that carried the silent 2000
    # default the rest of the arc spent its time deleting. A versioned agent's output
    # budget is declared where the resolver reads it: `agents.llm_spec.max_output`.
    # `agent_versions` holds no rows; `workflow_versions` three, none of them read.
    
    # Tool access
    tools: List[str] = Field(default_factory=list, description="Available tool IDs")
    
    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional configuration")
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"))
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"))
    
    model_config = ConfigDict(json_schema_extra={ "example": { "id": "agent-research-assistant", "name": "Research Assistant", "version": "1.0.0", "description": "Helps with research tasks and information gathering", "role": "Research Analyst", "goal": "Find accurate, relevant information quickly", "backstory": "You are an experienced research analyst with expertise in synthesizing complex information.", "llm_model": "gpt-4o-mini", "temperature": 0.3, "tools": ["web_search", "document_reader"], } })


class AgentVersion(BaseModel):
    """
    Agent version metadata.

    Tracks version history and deployment status.

    Attributes:
        version: Semantic version string
        agent_id: Parent agent ID
        status: Deployment status (draft, active, archived, deprecated)
        changelog: What changed in this version
        is_ab_testable: Can be used in A/B tests
        traffic_percentage: For A/B testing (0-100)
    """
    version: str = Field(..., description="Semantic version string")
    agent_id: str = Field(..., description="Parent agent ID")
    status: str = Field(default="draft", description="Deployment status")
    changelog: Optional[str] = Field(None, description="What changed in this version")
    is_ab_testable: bool = Field(default=True, description="Can be used in A/B tests")
    traffic_percentage: int = Field(default=0, ge=0, le=100, description="Traffic percentage for A/B testing")
    
    model_config = ConfigDict(json_schema_extra={ "example": { "version": "1.0.0", "agent_id": "agent-research-assistant", "status": "active", "changelog": "Initial release", "is_ab_testable": True, "traffic_percentage": 50, } })


class AgentRegistry:
    """
    In-memory registry for agent configurations.

    Provides:
    - Registration of agent configurations
    - Version lookup
    - A/B test routing
    - CRUD operations

    Note: This is an in-memory implementation for Phase 2.
    For production, integrate with database persistence.

    Usage:
        ```python
        # Register agent
        config = AgentConfig(...)
        AgentRegistry.register(config)
        
        # Get specific version
        config = AgentRegistry.get("agent-id", version="1.0.0")
        
        # Get latest active version
        config = AgentRegistry.get_latest("agent-id")
        
        # Get all versions
        versions = AgentRegistry.get_all_versions("agent-id")
        ```
    """

    # In-memory storage: {agent_id: {version: AgentConfig}}
    _agents: Dict[str, Dict[str, AgentConfig]] = {}
    
    # Version metadata: {agent_id: {version: AgentVersion}}
    _versions: Dict[str, Dict[str, AgentVersion]] = {}
    
    # Default version per agent: {agent_id: version}
    _defaults: Dict[str, str] = {}

    @classmethod
    def register(cls, config: AgentConfig, version_metadata: Optional[AgentVersion] = None) -> AgentConfig:
        """
        Register an agent configuration.

        Args:
            config: Agent configuration to register
            version_metadata: Optional version metadata (created automatically if not provided)

        Returns:
            Registered agent configuration

        Raises:
            ValueError: If agent ID or version already exists
        """
        agent_id = config.id
        version = config.version

        # Initialize storage for agent if needed
        if agent_id not in cls._agents:
            cls._agents[agent_id] = {}
            cls._versions[agent_id] = {}

        # Check if version already exists
        if version in cls._agents[agent_id]:
            raise ValueError(f"Agent {agent_id} version {version} already registered")

        # Register configuration
        cls._agents[agent_id][version] = config

        # Create version metadata if not provided
        if version_metadata is None:
            version_metadata = AgentVersion(
                version=version,
                agent_id=agent_id,
                status="active",
                changelog="Initial registration",
            )

        cls._versions[agent_id][version] = version_metadata

        # Set as default if first version
        if agent_id not in cls._defaults:
            cls._defaults[agent_id] = version

        return config

    @classmethod
    def get(cls, agent_id: str, version: Optional[str] = None) -> Optional[AgentConfig]:
        """
        Get agent configuration.

        Args:
            agent_id: Agent identifier
            version: Specific version (optional, uses default if not specified)

        Returns:
            Agent configuration or None if not found
        """
        if agent_id not in cls._agents:
            return None

        if version is None:
            version = cls._defaults.get(agent_id)
            if version is None:
                return None

        return cls._agents[agent_id].get(version)

    @classmethod
    def get_latest(cls, agent_id: str, status: Optional[str] = "active") -> Optional[AgentConfig]:
        """
        Get latest active version of an agent.

        Args:
            agent_id: Agent identifier
            status: Filter by status (default: "active")

        Returns:
            Latest agent configuration or None if not found
        """
        if agent_id not in cls._agents:
            return None

        # Get all versions with specified status
        active_versions = []
        for version, metadata in cls._versions.get(agent_id, {}).items():
            if metadata.status == status:
                active_versions.append(version)

        if not active_versions:
            return None

        # Return latest (simple approach: last registered)
        latest_version = active_versions[-1]
        return cls._agents[agent_id].get(latest_version)

    @classmethod
    def get_all_versions(cls, agent_id: str) -> List[AgentVersion]:
        """
        Get all versions for an agent.

        Args:
            agent_id: Agent identifier

        Returns:
            List of version metadata
        """
        return list(cls._versions.get(agent_id, {}).values())

    @classmethod
    def update_status(cls, agent_id: str, version: str, status: str) -> bool:
        """
        Update version status.

        Args:
            agent_id: Agent identifier
            version: Version to update
            status: New status (draft, active, archived, deprecated)

        Returns:
            True if updated, False if not found
        """
        if agent_id not in cls._versions:
            return False

        if version not in cls._versions[agent_id]:
            return False

        cls._versions[agent_id][version].status = status
        return True

    @classmethod
    def set_default(cls, agent_id: str, version: str) -> bool:
        """
        Set default version for an agent.

        Args:
            agent_id: Agent identifier
            version: Version to set as default

        Returns:
            True if set, False if version not found
        """
        if agent_id not in cls._versions:
            return False

        if version not in cls._versions[agent_id]:
            return False

        cls._defaults[agent_id] = version
        return True

    @classmethod
    def list_agents(cls) -> List[str]:
        """
        List all registered agent IDs.

        Returns:
            List of agent identifiers
        """
        return list(cls._agents.keys())

    @classmethod
    def reset(cls):
        """
        Reset registry (for testing only).

        WARNING: Clears all registered agents
        """
        cls._agents.clear()
        cls._versions.clear()
        cls._defaults.clear()
