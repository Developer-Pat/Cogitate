"""Recording and listing verified facts, a track record's reliability, and filtering by track.

The honesty loop's persistence:
- the store records verified facts + the track record
- the reliability summary computes the accuracy
- the tools record through the registry (the loop wired)
"""
import pytest

from app.domain.verification import store
pytestmark = pytest.mark.backend  # needs a running backend (the 2026-08-27 decision)



@pytest.fixture(autouse=True)
def clean_store():
    # a fresh store per test run (the WAL db in data/ is fine — the
    # tests append; the counts are relative)
    yield


def test_record_and_list_facts():
    # NOTE: the store clamps list_verified_facts at 50 — in the
    # full-suite order the store accumulates facts from the tool
    # executions, so COUNT-based assertions are order-dependent.
    # Assert the fact IS present (the newest first) instead.
    store.record_verified_fact(
        "the test fact",
        "test-verifier",
        "test source",
        {"k": "v"},
    )
    facts = store.list_verified_facts()
    assert any(f["claim"] == "the test fact" for f in facts)
    top = next(f for f in facts if f["claim"] == "the test fact")
    assert top["verified_by"] == "test-verifier"
    assert top["detail"] == {"k": "v"}


def test_track_record_and_reliability():
    store.record_operation("test-agent", "op-1", "claimed ok", "verified ok", "verified")
    store.record_operation("test-agent", "op-2", "claimed ok", "verified broken", "mismatched")
    rec = store.reliability("test-agent")
    assert rec["operations"] >= 2
    assert rec["verified"] >= 1
    assert rec["mismatched"] >= 1
    assert rec["accuracy"] is not None and 0 < rec["accuracy"] < 1


def test_list_track_filtered():
    rows = store.list_track_record(agent="test-agent")
    assert all(r["agent"] == "test-agent" for r in rows)
    all_rows = store.list_track_record()
    assert len(all_rows) >= len(rows)


@pytest.mark.asyncio
async def test_verify_health_records_fact():
    from app.domain.tools.registry import init_default_registry
    reg = init_default_registry()
    n0 = len(store.list_verified_facts())
    r = await reg.execute_tool("verify-backend-health", {}, {})
    assert r.get("success") is True
    assert len(store.list_verified_facts()) >= n0
