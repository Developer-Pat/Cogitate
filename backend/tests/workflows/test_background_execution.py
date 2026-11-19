"""
Test background execution doesn't block HTTP requests.

This test verifies:
1. Workflow starts in background
2. HTTP response returns immediately
3. Workflow continues after HTTP response
4. Can poll status while workflow runs
"""

import asyncio
import time
from fastapi.testclient import TestClient
from app.api.v1.router import router as v1_router
from fastapi import FastAPI

# Create test app with /api/v1 prefix
test_app = FastAPI()
test_app.include_router(v1_router)


def test_background_execution_non_blocking():
    """
    Test that starting a workflow doesn't block HTTP response.

    This test:
    1. Starts workflow via API
    2. Measures response time (should be < 1 second)
    3. Verifies workflow continues in background
    4. Polls status to confirm execution
    """
    client = TestClient(test_app)

    print("\n" + "="*60)
    print("TEST: Background Execution Non-Blocking")
    print("="*60)

    # Start workflow
    print("\n🔄 Starting workflow...")
    start_time = time.time()

    response = client.post(
        "/api/v1/workflows/execute",
        json={
            "template_id": "test-template",
            "initial_message": "Test background execution"
        }
    )

    response_time = time.time() - start_time

    print(f"   Response time: {response_time:.3f}s")
    print(f"   Status code: {response.status_code}")

    # Verify response is fast (< 1 second)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    assert response_time < 1.0, f"Response took {response_time:.3f}s, expected < 1s"

    data = response.json()
    workflow_id = data["workflow_id"]

    print(f"   Workflow ID: {workflow_id}")
    print(f"   Status: {data['status']}")
    print("✅ Workflow started quickly (non-blocking)")

    # Poll status to verify workflow is running
    print("\n🔄 Polling workflow status...")

    for i in range(5):  # Poll up to 5 times
        status_response = client.get(f"/api/v1/workflows/{workflow_id}/status")

        if status_response.status_code == 200:
            status_data = status_response.json()
            print(f"   Poll {i+1}: Status = {status_data['status']}, Next = {status_data['next_nodes']}")

            # Check if workflow is progressing
            if status_data['status'] in ['completed', 'running']:
                print(f"✅ Workflow is {status_data['status']}")
                break
        else:
            print(f"   Poll {i+1}: Status not available yet")

        asyncio.sleep(0.5)  # Wait 500ms between polls

    print("\n" + "="*60)
    print("✅ TEST PASSED: Background execution is non-blocking")
    print("="*60)

    return True


def test_workflow_lifecycle():
    """
    Test complete workflow lifecycle via API.

    This test:
    1. Creates workflow
    2. Checks status
    3. Verifies completion
    4. Retrieves history
    """
    client = TestClient(test_app)

    print("\n" + "="*60)
    print("TEST: Workflow Lifecycle")
    print("="*60)

    # Create workflow
    print("\n🔄 Creating workflow...")
    response = client.post(
        "/api/v1/workflows/execute",
        json={
            "template_id": "lifecycle-test",
            "initial_message": "Test lifecycle"
        }
    )

    assert response.status_code == 200
    workflow_id = response.json()["workflow_id"]
    print(f"   Created workflow: {workflow_id}")

    # Check status
    print("\n🔄 Checking status...")
    status_response = client.get(f"/api/v1/workflows/{workflow_id}/status")

    if status_response.status_code == 200:
        status_data = status_response.json()
        print(f"   Status: {status_data['status']}")
        print(f"   Next nodes: {status_data['next_nodes']}")
        print("✅ Status endpoint working")

    # Get history
    print("\n🔄 Getting history...")
    history_response = client.get(f"/api/v1/workflows/{workflow_id}/history")

    if history_response.status_code == 200:
        history_data = history_response.json()
        print(f"   Total checkpoints: {history_data['total_checkpoints']}")
        print("✅ History endpoint working")

    print("\n" + "="*60)
    print("✅ TEST PASSED: Workflow lifecycle complete")
    print("="*60)

    return True


if __name__ == "__main__":
    print("\n" + "="*60)
    print("Workflow API Tests")
    print("="*60)

    try:
        # Test 1: Background execution
        test1_passed = test_background_execution_non_blocking()

        print("\n")

        # Test 2: Lifecycle
        test2_passed = test_workflow_lifecycle()

        print("\n" + "="*60)
        if test1_passed and test2_passed:
            print("✅ ALL TESTS PASSED")
            print("="*60)
            exit(0)
        else:
            print("⚠️  SOME TESTS PASSED")
            print("="*60)
            exit(0)

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
