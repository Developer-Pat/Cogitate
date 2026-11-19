"""
A/B Testing for agent configurations.

Provides:
- ABTestConfig: A/B test configuration schema
- ABTestManager: Manages A/B test routing and analytics

Usage:
    ```python
    from app.workflows.agent_versioning import ABTestManager, ABTestConfig
    
    # Create A/B test
    ab_test = ABTestConfig(
        id="experiment-1",
        name="Agent Version Test",
        variants=[
            {"agent_id": "agent-v1", "traffic_percentage": 50},
            {"agent_id": "agent-v2", "traffic_percentage": 50},
        ]
    )
    ABTestManager.create_test(ab_test)
    
    # Get routed agent
    agent_id = ABTestManager.get_routed_agent("experiment-1")
    config = AgentRegistry.get(agent_id)
    ```
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, ConfigDict, Field
import random
import hashlib
from datetime import datetime, UTC


class ABTestVariant(BaseModel):
    """
    A/B test variant configuration.

    Attributes:
        agent_id: Agent configuration to use
        traffic_percentage: Percentage of traffic (0-100)
        name: Human-readable variant name
        description: Variant description
    """
    agent_id: str = Field(..., description="Agent configuration to use")
    traffic_percentage: int = Field(..., ge=0, le=100, description="Percentage of traffic")
    name: Optional[str] = Field(None, description="Human-readable variant name")
    description: Optional[str] = Field(None, description="Variant description")


class ABTestConfig(BaseModel):
    """
    A/B test configuration.

    Defines an experiment with multiple variants and traffic distribution.

    Attributes:
        id: Unique experiment identifier
        name: Human-readable name
        description: Experiment purpose and hypothesis
        variants: List of test variants
        status: Test status (draft, running, paused, completed)
        start_time: When test started
        end_time: When test ended
        metadata: Additional experiment metadata
    """
    id: str = Field(..., description="Unique experiment identifier")
    name: str = Field(..., description="Human-readable name")
    description: str = Field(..., description="Experiment purpose and hypothesis")
    variants: List[ABTestVariant] = Field(..., description="Test variants")
    status: str = Field(default="draft", description="Test status")
    start_time: Optional[str] = Field(None, description="When test started")
    end_time: Optional[str] = Field(None, description="When test ended")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(json_schema_extra={ "example": { "id": "experiment-agent-performance", "name": "Agent Performance Test", "description": "Test if v2 agent performs better than v1", "variants": [ { "agent_id": "agent-assistant-v1", "traffic_percentage": 50, "name": "Control (v1)" }, { "agent_id": "agent-assistant-v2", "traffic_percentage": 50, "name": "Treatment (v2)" } ], "status": "running", } })


class ABTestManager:
    """
    Manages A/B tests for agent configurations.

    Provides:
    - Test creation and management
    - Traffic routing based on percentages
    - Consistent hashing for user stickiness
    - Test analytics

    Usage:
        ```python
        # Create test
        ABTestManager.create_test(ab_test_config)
        
        # Get routed agent for user
        agent_id = ABTestManager.get_routed_agent("experiment-id", user_id="user-123")
        
        # Get test results
        results = ABTestManager.get_test_results("experiment-id")
        ```
    """

    # In-memory storage: {test_id: ABTestConfig}
    _tests: Dict[str, ABTestConfig] = {}
    
    # Analytics: {test_id: {variant_id: {metric: value}}}
    _analytics: Dict[str, Dict[str, Dict[str, Any]]] = {}

    @classmethod
    def create_test(cls, config: ABTestConfig) -> ABTestConfig:
        """
        Create a new A/B test.

        Args:
            config: A/B test configuration

        Returns:
            Created test configuration

        Raises:
            ValueError: If test ID already exists or traffic doesn't sum to 100
        """
        if config.id in cls._tests:
            raise ValueError(f"A/B test {config.id} already exists")

        # Validate traffic distribution
        total_traffic = sum(v.traffic_percentage for v in config.variants)
        if total_traffic != 100:
            raise ValueError(f"Traffic percentages must sum to 100, got {total_traffic}")

        cls._tests[config.id] = config
        cls._analytics[config.id] = {}

        return config

    @classmethod
    def get_test(cls, test_id: str) -> Optional[ABTestConfig]:
        """
        Get A/B test configuration.

        Args:
            test_id: Test identifier

        Returns:
            Test configuration or None if not found
        """
        return cls._tests.get(test_id)

    @classmethod
    def get_routed_agent(cls, test_id: str, user_id: Optional[str] = None) -> Optional[str]:
        """
        Get agent ID based on A/B test routing.

        Uses consistent hashing for user stickiness:
        - Same user always gets same variant
        - Traffic distribution respects percentages

        Args:
            test_id: Test identifier
            user_id: Optional user ID for sticky routing

        Returns:
            Routed agent ID or None if test not found
        """
        test = cls._tests.get(test_id)
        if not test:
            return None

        if test.status != "running":
            return None

        if not test.variants:
            return None

        # If only one variant, return it
        if len(test.variants) == 1:
            return test.variants[0].agent_id

        # Determine variant based on user_id or random
        if user_id:
            # Consistent hashing for sticky sessions
            hash_value = cls._consistent_hash(user_id, test_id)
        else:
            # Random routing
            hash_value = random.random()

        # Route based on traffic distribution
        cumulative: float = 0.0
        for variant in test.variants:
            cumulative += variant.traffic_percentage / 100.0
            if hash_value < cumulative:
                return variant.agent_id

        # Fallback to last variant (shouldn't happen with proper percentages)
        return test.variants[-1].agent_id

    @classmethod
    def _consistent_hash(cls, value: str, salt: str = "") -> float:
        """
        Consistent hash function for sticky routing.

        Args:
            value: Value to hash (e.g., user_id)
            salt: Optional salt for variation (e.g., test_id)

        Returns:
            Float between 0 and 1
        """
        hash_input = f"{value}:{salt}"
        hash_bytes = hashlib.md5(hash_input.encode()).digest()
        hash_int = int.from_bytes(hash_bytes[:8], byteorder='big')
        return (hash_int % 10000) / 10000.0

    @classmethod
    def start_test(cls, test_id: str) -> bool:
        """
        Start an A/B test.

        Args:
            test_id: Test identifier

        Returns:
            True if started, False if not found
        """
        test = cls._tests.get(test_id)
        if not test:
            return False

        test.status = "running"
        test.start_time = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return True

    @classmethod
    def pause_test(cls, test_id: str) -> bool:
        """
        Pause an A/B test.

        Args:
            test_id: Test identifier

        Returns:
            True if paused, False if not found
        """
        test = cls._tests.get(test_id)
        if not test:
            return False

        test.status = "paused"
        return True

    @classmethod
    def complete_test(cls, test_id: str) -> bool:
        """
        Complete an A/B test.

        Args:
            test_id: Test identifier

        Returns:
            True if completed, False if not found
        """
        test = cls._tests.get(test_id)
        if not test:
            return False

        test.status = "completed"
        test.end_time = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        return True

    @classmethod
    def list_tests(cls, status: Optional[str] = None) -> List[ABTestConfig]:
        """
        List A/B tests.

        Args:
            status: Optional status filter

        Returns:
            List of test configurations
        """
        tests = list(cls._tests.values())
        if status:
            tests = [t for t in tests if t.status == status]
        return tests

    @classmethod
    def reset(cls):
        """
        Reset all tests (for testing only).

        WARNING: Clears all A/B tests
        """
        cls._tests.clear()
        cls._analytics.clear()
