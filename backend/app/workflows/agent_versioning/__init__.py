"""
Agent versioning module for cogitate platform.

Provides:
- Agent configuration schema
- Agent registry for version management
- A/B testing support

Usage:
    ```python
    from app.workflows.agent_versioning import AgentRegistry
    
    # Get agent configuration
    config = AgentRegistry.get_agent_config("agent-id", version="1.0.0")
    
    # A/B test routing
    config = AgentRegistry.get_ab_tested_config("experiment-id")
    ```
"""

from .registry import AgentRegistry, AgentConfig, AgentVersion
from .ab_testing import ABTestManager, ABTestConfig, ABTestVariant

__all__ = [
    "AgentRegistry",
    "AgentConfig", 
    "AgentVersion",
    "ABTestManager",
    "ABTestConfig",
    "ABTestVariant",
]
