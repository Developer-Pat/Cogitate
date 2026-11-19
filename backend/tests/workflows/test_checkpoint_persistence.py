"""
Test checkpoint persistence across process restarts.

This is a critical test verifying that LangGraph checkpoints
survive process restarts, enabling workflow durability.
"""

from app.workflows import create_simple_workflow, CheckpointerConfig
from app.workflows.state import RunMetadata
import tempfile
import os


def test_checkpoint_persistence():
    """
    Verify checkpoint survives process restart.

    This test:
    1. Executes a workflow with checkpointing
    2. Simulates process restart (new graph instance)
    3. Verifies state can be retrieved from checkpoint

    Returns:
        True if test passes, False otherwise
    """
    db_path = os.path.join(tempfile.mkdtemp(prefix="cogitate-ckpt-"), "test_persistence_checkpoints.db")

    # Clean up any existing test DB
    if os.path.exists(db_path):
        for suffix in ("", "-wal", "-shm"):
            p = f"{db_path}{suffix}"
            if os.path.exists(p):
                os.remove(p)
        print("🧹 Cleaned up existing test database")

    try:
        # Process 1 - Execute workflow
        print("\n🔄 Process 1: Starting workflow...")

        graph = create_simple_workflow()

        # A private database is asked for BY PATH, never by re-pointing the
        # process-wide WORKFLOW_CHECKPOINT_DB: that overlay belongs to the test
        # session (tests/workflows/conftest.py), and a test that takes it and
        # then deletes the file leaves the shared checkpointer bound to a
        # database that no longer exists — every later default-path caller gets
        # `sqlite3.OperationalError: disk I/O error` (measured 2026-10-15).
        checkpointer = CheckpointerConfig.get_checkpointer(db_path=db_path)
        compiled = graph.compile(checkpointer=checkpointer)

        initial_state = {
            "workflow_id": "persistence-test",
            "template_id": "template-1",
            "messages": [],
            "current_step": None,
            "execution_result": None,
            "approval_required": False,
            "approval_status": None,
            "metadata": RunMetadata(
                workflow_id="persistence-test",
                template_id="template-1"
            )
        }

        config = {"configurable": {"thread_id": "persistence-test"}}
        result = compiled.invoke(initial_state, config)

        print("✅ Process 1 complete")
        print(f"   Execution result: {result['execution_result']['result']}")
        print(f"   Status: {result['metadata'].status}")

        # Simulate process restart - create completely new graph instance
        print("\n🔄 Process 2: Simulating restart (new graph instance)...")

        # Create new graph (simulates fresh process)
        graph2 = create_simple_workflow()

        checkpointer2 = CheckpointerConfig.get_checkpointer(db_path=db_path)
        compiled2 = graph2.compile(checkpointer=checkpointer2)

        # Try to get state from checkpoint
        config = {"configurable": {"thread_id": "persistence-test"}}
        state = compiled2.get_state(config)

        if state and state.values:
            print("✅ Checkpoint survived process restart!")
            print(f"   Retrieved status: {state.values['metadata'].status}")
            print(f"   Retrieved result: {state.values['execution_result']['result']}")

            # Verify the data is correct
            assert state.values['metadata'].status == "completed"
            assert state.values['execution_result']['result'] == "Workflow executed successfully"

            print("\n✅ TEST PASSED: Checkpoint persistence verified")
            return True
        else:
            print("❌ Checkpoint not found after restart")
            print("\n❌ TEST FAILED: Checkpoint persistence failed")
            return False

    finally:
        # Hand the manager back BEFORE the files go: reset() closes the
        # connection this test opened, so the next caller re-derives from the
        # session's own overlay instead of holding a database that is gone.
        CheckpointerConfig.reset()
        # Cleanup (db + wal + shm)
        for suffix in ("", "-wal", "-shm"):
            p = f"{db_path}{suffix}"
            if os.path.exists(p):
                os.remove(p)
        print("\n🧹 Cleaned up test database")


if __name__ == "__main__":
    success = test_checkpoint_persistence()
    exit(0 if success else 1)
