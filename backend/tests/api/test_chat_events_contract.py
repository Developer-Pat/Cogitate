"""The chat-event contract matches the legacy names and topics, including trace-complete.

THE ROADMAP'S RULE: the contract's SSE output must be IDENTICAL
to the current emitters (any diff is a bug, not a change). These
tests build the same events through BOTH paths + assert equality.
"""

from app.api.v1.chat import chat_events
from app.api.v1.chat import cognitive_sse
from app.services.cognitive_pipeline.models import (
    CognitiveResult, ComponentTrace, CognitiveTrace,
    CognitiveMetrics, MemoryDelta,
)


def _mk_trace(**over):
    base = dict(
        strategy="test", duration_ms=12, tokens_used=34,
        metadata={"sources": ["a.md"], "compaction_triggered": False, "stored_keys": ["k1"]},
        error=None,
    )
    base.update(over)
    return ComponentTrace(**base)


def _mk_result():
    trace = CognitiveTrace(
        context_builder=_mk_trace(),
        executor=_mk_trace(strategy="hybrid"),
        memory_manager=_mk_trace(),
        response_formatter=_mk_trace(),
    )
    metrics = CognitiveMetrics(
        total_duration_ms=12, total_tokens=34, llm_calls=1,
        tool_calls=0, cache_hits=0,
    )
    delta = MemoryDelta(stored_keys=["k1"], evicted_keys=[], compaction_triggered=False)
    return CognitiveResult(response="hello", trace=trace, metrics=metrics, memory_delta=delta)


def _test_one(kind_build, legacy_emit, *args):
    """Both paths must produce the SAME SSE string."""
    topic, payload = kind_build("sess-1", *args)
    contract_sse = chat_events.sse_from_builder((topic, payload))
    legacy_sse = legacy_emit(*args)
    assert contract_sse == legacy_sse, (
        f"CONTRACT DIFF for {topic}:\n"
        f"  contract: {contract_sse!r}\n"
        f"  legacy:   {legacy_sse!r}"
    )


def test_contract_matches_legacy_all_events():
    t = _mk_trace()
    _test_one(chat_events.build_context_built, cognitive_sse.emit_cognitive_context_built, t)
    _test_one(chat_events.build_executor_started, cognitive_sse.emit_cognitive_executor_started, "test")
    _test_one(chat_events.build_executor_progress, cognitive_sse.emit_cognitive_executor_progress, 5, 2, "streaming")
    _test_one(chat_events.build_executor_completed, cognitive_sse.emit_cognitive_executor_completed, t)
    _test_one(chat_events.build_memory_updated, cognitive_sse.emit_cognitive_memory_updated, t)
    _test_one(chat_events.build_response_formatted, cognitive_sse.emit_cognitive_response_formatted, t)


def test_trace_complete_matches():
    r = _mk_result()
    topic, payload = chat_events.build_trace_complete("sess-1", r)
    contract_sse = chat_events.sse_from_builder((topic, payload))
    legacy_sse = cognitive_sse.emit_cognitive_trace_complete(r)
    assert contract_sse == legacy_sse


def test_topic_convention():
    topic, _ = chat_events.build_executor_started("sess-42", "test")
    assert topic == "chat:sess-42:executor_started"


def test_legacy_names_map():
    topic, payload = chat_events.build_context_built("sess-1", _mk_trace())
    sse = chat_events.sse_from_builder((topic, payload))
    assert "event: cognitive_context_built" in sse
