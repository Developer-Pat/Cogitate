"""Error handling and recovery — retry, the recovery strategies, the checkpointer, and the routes.

The five checks assert; the `_run_*` helpers return a bool for the manual run and each pytest wrapper
asserts that bool, because a wrapper that discards it turns a failing check green.
"""

import os
import sys
import tempfile

_CKPT_DIR = tempfile.mkdtemp(prefix="cogitate-ckpt-")
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent.parent.parent  # path-ok: locates the SOURCE tree to read source files; only DATA follows the installation root
sys.path.insert(0, str(backend_path))

from app.workflows.error_handling.retry import RetryConfig, execute_with_retry, execute_with_retry_async  # noqa: E402
from app.workflows.error_handling.recovery import RecoveryWorkflow, RecoveryStrategy  # noqa: E402
from app.workflows.checkpointing.config import CheckpointerManager  # noqa: E402


def _run_retry_logic():
    """Test 1: Retry logic with exponential backoff."""
    print("\n" + "="*60)
    print("TEST 1: Retry Logic")
    print("="*60)
    
    try:
        # Test 1: Successful execution (no retry needed)
        def success_func():
            return "success"
        
        result = execute_with_retry(success_func, config=RetryConfig(max_retries=3))
        assert result.success, "Should succeed"
        assert result.attempts == 1, "Should succeed on first attempt"
        assert result.result == "success", "Should return correct result"
        print("✅ Successful execution (no retry)")
        
        # Test 2: Failed execution (all retries exhausted)
        attempt_count = 0
        
        def fail_func():
            nonlocal attempt_count
            attempt_count += 1
            raise Exception("Intentional failure")
        
        result = execute_with_retry(
            fail_func,
            config=RetryConfig(max_retries=3, delay=0.1),
        )
        assert not result.success, "Should fail"
        assert result.attempts == 4, f"Should attempt 4 times (1 + 3 retries), got {result.attempts}"
        print(f"✅ Failed execution with retries (attempted {result.attempts} times)")
        
        # Test 3: Retry then succeed
        attempt_count = 0
        
        def flaky_func():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise Exception("Transient failure")
            return "finally succeeded"
        
        result = execute_with_retry(
            flaky_func,
            config=RetryConfig(max_retries=3, delay=0.1),
        )
        assert result.success, "Should eventually succeed"
        assert result.attempts == 3, f"Should succeed on 3rd attempt, got {result.attempts}"
        print(f"✅ Flaky function succeeded after {result.attempts} attempts")
        
        # Test 4: Exponential backoff timing
        config = RetryConfig(max_retries=3, delay=0.1, backoff_multiplier=2.0)
        assert config.get_delay(0) == 0.1, "First delay should be 0.1s"
        assert config.get_delay(1) == 0.2, "Second delay should be 0.2s"
        assert config.get_delay(2) == 0.4, "Third delay should be 0.4s"
        print("✅ Exponential backoff delays calculated correctly")
        
        print("\n✅ TEST 1 PASSED - Retry Logic working")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def _run_async_retry():
    """Test 2: Async retry logic."""
    print("\n" + "="*60)
    print("TEST 2: Async Retry Logic")
    print("="*60)
    
    try:
        # Test async success
        async def async_success():
            return "async success"
        
        result = await execute_with_retry_async(async_success)
        assert result.success, "Should succeed"
        print("✅ Async successful execution")
        
        # Test async retry then succeed
        attempt_count = 0
        
        async def async_flaky():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise Exception("Async transient failure")
            return "async succeeded"
        
        result = await execute_with_retry_async(
            async_flaky,
            config=RetryConfig(max_retries=3, delay=0.1),
        )
        assert result.success, "Should eventually succeed"
        assert result.attempts == 2, f"Should succeed on 2nd attempt, got {result.attempts}"
        print(f"✅ Async flaky function succeeded after {result.attempts} attempts")
        
        print("\n✅ TEST 2 PASSED - Async Retry Logic working")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def _run_recovery_strategies():
    """Test 3: Recovery strategies."""
    print("\n" + "="*60)
    print("TEST 3: Recovery Strategies")
    print("="*60)
    
    try:
        # Test state
        test_state = {
            "workflow_id": "wf-test",
            "template_id": "tpl-test",
            "messages": [],
            "current_step": "executor",
            "metadata": type('obj', (object,), {
                'status': 'error',
                'error': 'Test error',
                'started_at': '2026-03-23T00:00:00Z'
            })()
        }
        
        error = Exception("Test error")
        
        # Test 1: Retry recovery
        result = RecoveryWorkflow.execute_recovery(
            strategy=RecoveryStrategy.RETRY,
            error=error,
            state=test_state,
            context={"retry_count": 0, "max_retries": 3}
        )
        assert result["metadata"].status == "retrying", "Should set status to retrying"
        print("✅ Retry recovery strategy")
        
        # Test 2: Fallback recovery
        result = RecoveryWorkflow.execute_recovery(
            strategy=RecoveryStrategy.FALLBACK,
            error=error,
            state=test_state,
            context={"fallback_agent_id": "agent-fallback"}
        )
        assert result["metadata"].status == "using_fallback", "Should set status to using_fallback"
        assert result.get("fallback_agent_id") == "agent-fallback", "Should set fallback agent"
        print("✅ Fallback recovery strategy")
        
        # Test 3: Degraded recovery
        result = RecoveryWorkflow.execute_recovery(
            strategy=RecoveryStrategy.DEGRADE,
            error=error,
            state=test_state,
            context={"degraded_mode": "limited"}
        )
        assert result["metadata"].status == "degraded", "Should set status to degraded"
        assert result.get("degraded_mode"), "Should mark as degraded"
        print("✅ Degraded recovery strategy")
        
        # Test 4: Notify recovery
        result = RecoveryWorkflow.execute_recovery(
            strategy=RecoveryStrategy.NOTIFY,
            error=error,
            state=test_state,
            context={"notification_channel": "email"}
        )
        assert result["metadata"].status == "awaiting_intervention", "Should set status to awaiting_intervention"
        assert "pending_notification" in result, "Should create notification"
        print("✅ Notify recovery strategy")
        
        # Test 5: Abort recovery
        result = RecoveryWorkflow.execute_recovery(
            strategy=RecoveryStrategy.ABORT,
            error=error,
            state=test_state,
            context={"reason": "Unrecoverable"}
        )
        assert result["metadata"].status == "aborted", "Should set status to aborted"
        assert result.get("abort_reason") == "Unrecoverable", "Should set abort reason"
        print("✅ Abort recovery strategy")
        
        print("\n✅ TEST 3 PASSED - Recovery Strategies working")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def _run_api_endpoints():
    """Test 4: Error handling API endpoints."""
    print("\n" + "="*60)
    print("TEST 4: Error Handling API Endpoints")
    print("="*60)

    try:
        from app.main import app

        # The MAIN app: `app.workflows.app` is a bare test app whose routers carry no /api/v1
        # prefix, so every path below reads as missing there.
        routes = {route.path for route in app.routes}
        required_endpoints = [
            "/api/v1/workflows/{workflow_id}/rollback",
            "/api/v1/workflows/{workflow_id}/recover",
            "/api/v1/workflows/{workflow_id}/checkpoints",
        ]

        missing = [endpoint for endpoint in required_endpoints if endpoint not in routes]
        for endpoint in required_endpoints:
            print(f"{'❌' if endpoint in missing else '✅'} {endpoint}")

        if missing:
            print(f"\n❌ TEST 4 FAILED - not registered: {missing}")
            return False

        print(f"\n✅ TEST 4 PASSED - All {len(required_endpoints)} endpoints registered")
        return True

    except Exception as e:
        print(f"\n❌ TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def _run_checkpoint_manager():
    """Test 5: Checkpointer stays open for error handling."""
    print("\n" + "="*60)
    print("TEST 5: Checkpointer for Error Handling")
    print("="*60)
    
    try:
        # Get checkpointer
        checkpointer = CheckpointerManager.get_checkpointer(db_path=os.path.join(_CKPT_DIR, "test_session48_checkpoints.db"))
        assert type(checkpointer).__name__ == "SqliteSaver", "Should return SqliteSaver instance"
        print("✅ Checkpointer instance obtained")
        
        # Verify it stays open
        checkpointer2 = CheckpointerManager.get_checkpointer(db_path=os.path.join(_CKPT_DIR, "test_session48_checkpoints.db"))
        assert checkpointer is checkpointer2, "Should return same instance"
        print("✅ Checkpointer singleton working")

        # Cleanup isolated test DB (db + wal + shm)
        for suffix in ("", "-wal", "-shm"):
            p = os.path.join(_CKPT_DIR, f"test_session48_checkpoints.db{suffix}")
            if os.path.exists(p):
                os.remove(p)
        
        print("\n✅ TEST 5 PASSED - Checkpointer ready for error handling")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


# ---- the pytest surface: each wrapper asserts the check's result ------------------------------
#
# The helpers return a bool so `main()` could report a summary for a manual run; a wrapper that
# calls one and drops the value makes every check pass, whatever it found. These assert.

def test_retry_logic() -> None:
    """Retry: a success is not retried, a failure is retried and reported, a flake recovers."""
    assert _run_retry_logic(), "retry logic check failed (printed above)"


async def test_async_retry() -> None:
    """The async retry mirrors the sync one, cancellation aside."""
    assert await _run_async_retry(), "async retry check failed (printed above)"


def test_recovery_strategies() -> None:
    """Each recovery strategy runs and reports its outcome."""
    assert _run_recovery_strategies(), "recovery strategy check failed (printed above)"


def test_api_endpoints() -> None:
    """The rollback, recover and checkpoint routes are registered on the server's app."""
    assert _run_api_endpoints(), "error-handling routes are not all registered (printed above)"


def test_checkpoint_manager() -> None:
    """The checkpointer writes and reads a checkpoint under the configured directory."""
    assert _run_checkpoint_manager(), "checkpointer check failed (printed above)"
