"""Agent versioning and A/B testing — the registry, the versions, the API, and the routing.

Sticky sessions are the A/B half's promise: a user routed to a variant stays on it, and a test that
does not check that is a test of nothing.
"""

import sys
from pathlib import Path

import pytest

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root
sys.path.insert(0, str(backend_path))

from app.workflows.agent_versioning.registry import AgentRegistry, AgentConfig  # noqa: E402
from app.workflows.agent_versioning.ab_testing import ABTestManager, ABTestConfig, ABTestVariant  # noqa: E402


def test_agent_registry():
    """Test 1: Agent Registry CRUD operations."""
    print("\n" + "="*60)
    print("TEST 1: Agent Registry CRUD")
    print("="*60)
    
    failure = None
    try:
        # Reset registry
        AgentRegistry.reset()
        
        # Create agent configuration
        config = AgentConfig(
            id="agent-test-assistant",
            name="Test Assistant",
            version="1.0.0",
            description="Test agent for verification",
            role="Test Agent",
            goal="Pass all tests",
            backstory="You are a test agent designed to verify functionality.",
            llm_model="gpt-4o-mini",
            temperature=0.3,
            tools=["test_tool"],
        )
        
        # Register agent
        AgentRegistry.register(config)
        print(f"✅ Agent registered: {config.id} v{config.version}")
        
        # Retrieve agent
        retrieved = AgentRegistry.get("agent-test-assistant", "1.0.0")
        assert retrieved is not None, "Failed to retrieve agent"
        assert retrieved.name == "Test Assistant", "Agent name mismatch"
        print("✅ Agent retrieved successfully")
        
        # Get latest
        latest = AgentRegistry.get_latest("agent-test-assistant")
        assert latest is not None, "Failed to get latest version"
        print(f"✅ Latest version retrieved: {latest.version}")
        
        # List agents
        agents = AgentRegistry.list_agents()
        assert "agent-test-assistant" in agents, "Agent not in list"
        print(f"✅ Agent list working: {agents}")
        
        print("\n✅ TEST 1 PASSED - Agent Registry CRUD working")
        
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        failure = str(e)
    
    if failure:
        pytest.fail(failure)


def test_version_management():
    """Test 2: Version management."""
    print("\n" + "="*60)
    print("TEST 2: Version Management")
    print("="*60)
    
    failure = None
    try:
        # Reset registry
        AgentRegistry.reset()
        
        # Create multiple versions
        v1 = AgentConfig(
            id="agent-versioned",
            name="Versioned Agent",
            version="1.0.0",
            description="Version 1",
            llm_model="gpt-4o-mini",
        )
        
        v2 = AgentConfig(
            id="agent-versioned",
            name="Versioned Agent",
            version="2.0.0",
            description="Version 2 with improvements",
            llm_model="gpt-4o",
        )
        
        # Register both versions
        AgentRegistry.register(v1)
        print("✅ Version 1.0.0 registered")
        
        AgentRegistry.register(v2)
        print("✅ Version 2.0.0 registered")
        
        # Get all versions
        versions = AgentRegistry.get_all_versions("agent-versioned")
        assert len(versions) == 2, f"Expected 2 versions, got {len(versions)}"
        print(f"✅ All versions retrieved: {[v.version for v in versions]}")
        
        # Update status
        AgentRegistry.update_status("agent-versioned", "1.0.0", "archived")
        v1_meta = AgentRegistry.get_all_versions("agent-versioned")[0]
        assert v1_meta.status == "archived", "Status update failed"
        print("✅ Status updated to 'archived' for v1.0.0")
        
        # Set default
        AgentRegistry.set_default("agent-versioned", "2.0.0")
        default = AgentRegistry.get("agent-versioned")
        assert default.version == "2.0.0", "Default version not set correctly"
        print("✅ Default version set to 2.0.0")
        
        print("\n✅ TEST 2 PASSED - Version Management working")
        
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        failure = str(e)
    
    if failure:
        pytest.fail(failure)


def test_ab_testing():
    """Test 3: A/B Testing routing."""
    print("\n" + "="*60)
    print("TEST 3: A/B Testing Routing")
    print("="*60)
    
    failure = None
    try:
        # Reset managers
        ABTestManager.reset()
        AgentRegistry.reset()
        
        # Register two agent versions
        v1 = AgentConfig(
            id="agent-ab-v1",
            name="Agent V1",
            version="1.0.0",
            description="Control variant",
            llm_model="gpt-4o-mini",
        )
        
        v2 = AgentConfig(
            id="agent-ab-v2",
            name="Agent V2",
            version="2.0.0",
            description="Treatment variant",
            llm_model="gpt-4o",
        )
        
        AgentRegistry.register(v1)
        AgentRegistry.register(v2)
        print("✅ Two agent versions registered")
        
        # Create A/B test
        ab_test = ABTestConfig(
            id="ab-test-performance",
            name="Performance Test",
            description="Test v2 vs v1 performance",
            variants=[
                ABTestVariant(
                    agent_id="agent-ab-v1",
                    traffic_percentage=50,
                    name="Control (V1)"
                ),
                ABTestVariant(
                    agent_id="agent-ab-v2",
                    traffic_percentage=50,
                    name="Treatment (V2)"
                )
            ],
            status="draft",
        )
        
        ABTestManager.create_test(ab_test)
        print(f"✅ A/B test created: {ab_test.id}")
        
        # Start test
        ABTestManager.start_test("ab-test-performance")
        test = ABTestManager.get_test("ab-test-performance")
        assert test.status == "running", "Test not started"
        print("✅ A/B test started")
        
        # Test routing (random)
        agent_ids = set()
        for i in range(20):
            agent_id = ABTestManager.get_routed_agent("ab-test-performance")
            agent_ids.add(agent_id)
        
        assert len(agent_ids) > 1, "Routing not distributing traffic"
        print(f"✅ Traffic distribution working: {agent_ids}")
        
        # Test sticky sessions
        user1_routes = []
        for i in range(5):
            agent_id = ABTestManager.get_routed_agent("ab-test-performance", user_id="user-123")
            user1_routes.append(agent_id)
        
        assert len(set(user1_routes)) == 1, "Sticky session not working"
        print(f"✅ Sticky sessions working: user-123 always gets {user1_routes[0]}")
        
        print("\n✅ TEST 3 PASSED - A/B Testing working")
        
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        failure = str(e)
    
    if failure:
        pytest.fail(failure)


def test_api_endpoints() -> None:
    """The agent registry and A/B endpoints are registered on the app the server runs.

    Read from the MAIN app: `app.workflows.app` is a bare test app whose routers carry no `/api/v1`
    prefix, so every one of these paths reads as missing there — which is how this check used to
    report "partial" and pass anyway.
    """
    from app.main import app

    routes = {route.path for route in app.routes}
    required_endpoints = [
        "/api/v1/agents",
        "/api/v1/agents/{agent_id}",
        "/api/v1/agents/{agent_id}/versions",
        "/api/v1/agents/ab-tests",
        "/api/v1/agents/ab-tests/{test_id}",
        "/api/v1/agents/route",
    ]
    missing = [endpoint for endpoint in required_endpoints if endpoint not in routes]
    assert not missing, f"endpoints not registered: {missing}"


def test_agent_config_schema():
    """Test 5: Agent configuration schema validation."""
    print("\n" + "="*60)
    print("TEST 5: Agent Configuration Schema")
    print("="*60)
    
    failure = None
    try:
        # Test valid configuration
        config = AgentConfig(
            id="agent-schema-test",
            name="Schema Test Agent",
            version="1.0.0",
            description="Testing schema validation",
            role="Test Role",
            goal="Test Goal",
            backstory="Test Backstory",
            llm_model="gpt-4o-mini",
            temperature=0.5,
            tools=["tool1", "tool2"],
            metadata={"custom": "value"}
        )
        
        assert config.id == "agent-schema-test"
        assert config.temperature == 0.5
        assert len(config.tools) == 2
        print("✅ Valid configuration accepted")
        
        # Test temperature validation
        try:
            AgentConfig(
                id="agent-invalid",
                name="Invalid",
                version="1.0.0",
                description="Test",
                temperature=3.0,  # Invalid: > 2.0
            )
            print("❌ Invalid temperature accepted (should fail)")
            failure = "Invalid temperature was accepted (expected rejection)"
        except Exception:
            print("✅ Invalid temperature rejected (as expected)")
        
        if failure:
            pytest.fail(failure)
        
        # Test default values
        minimal_config = AgentConfig(
            id="agent-minimal",
            name="Minimal",
            version="1.0.0",
            description="Minimal config"
        )
        assert minimal_config.llm_model == "gpt-4o-mini"
        assert minimal_config.temperature == 0.0
        # NO `max_tokens` ASSERTION: the field was REMOVED from AgentConfig on
        # 2026-09-25 (the token-limits arc's G-I step) — a second declaration home,
        # in another domain, that nothing read, and that carried the silent 2000
        # default that arc spent its time deleting. A versioned agent's output
        # budget is declared where the resolver reads it (`agents.llm_spec.
        # max_output`), so there is no default here to assert. This assertion
        # outlived the field, which is why the suite went red.
        assert len(minimal_config.tools) == 0
        print("✅ Default values applied correctly")
        
        print("\n✅ TEST 5 PASSED - Schema validation working")
        
    except Exception as e:
        print(f"\n❌ TEST 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        failure = str(e)
    
    if failure:
        pytest.fail(failure)
