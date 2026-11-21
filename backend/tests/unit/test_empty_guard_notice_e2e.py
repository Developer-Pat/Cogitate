"""END-TO-END: the empty-completion guard is VISIBLE in the stream.

THE VISIBILITY FIX (2026-09-10, the user's "she died again, no warning
or messages"): the finalize guard refuses to persist an empty assistant
message (correct) — and the refusal used to tell NOBODY. This drives the
REAL `generate_stream` through the empty path (both LLM passes come back
empty) and asserts the user-visible `event: error` frame is emitted, in
the frontend's existing error convention (F1, 2026-08-03), BEFORE the
final done frame.

The bug being pinned: remove the `if metadata.get("empty_guard")` branch
in router.generate_stream and this test fails (the stream ends with the
bare done frame — a turn that produced nothing, silently).
"""

import json
from types import SimpleNamespace

import pytest

from app.domain.chat.services import ChatService
from app.infrastructure.database.models import Agent


def _fake_llm_response(content: str = ""):
    """A non-streamed completion shape (the fallback reads .choices)."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


@pytest.mark.anyio
async def test_generate_stream_surfaces_the_empty_guard(test_session, monkeypatch):
    """The empty turn must SAY so — not end in silence."""
    from app.api.v1.chat import router as mod
    from app.api.v1.chat import llm_utils
    from app.api.v1.chat.error_handling import EMPTY_COMPLETION_NOTICE

    agent = Agent(
        name="Guard Agent",
        provider="deepseek",
        model="deepseek-v4-flash",
        system_prompt="You are a test agent.",
        is_active=True,
    )
    test_session.add(agent)
    await test_session.commit()
    await test_session.refresh(agent)

    # Pass 1 (the main stream): chunks but NO content, NO tool calls —
    # the wrapper flags the empty completion.
    async def fake_stream(request_kwargs, context, logger_service, start_time, service,
                     result_holder, path="", supersedes=False):
        result_holder["result"] = None
        result_holder["empty_completion"] = True
        result_holder["empty_chunk_count"] = 3
        result_holder["empty_invalid_chunks"] = 0
        return
        yield  # pragma: no cover — makes this an async generator

    monkeypatch.setattr(mod, "_stream_llm_response", fake_stream)

    # The retry + the visible fallback: BOTH come back empty (the
    # deterministic reasoning-budget variant) — this is what lands on
    # the finalize guard.
    async def fake_completion(**kwargs):
        return _fake_llm_response("")

    monkeypatch.setattr(llm_utils, "acompletion_with_retry", fake_completion)

    request = SimpleNamespace(
        agent_id=agent.id,
        message="are you alive?",
        session_id=None,
        attachment_ids=None,
        generate_title=False,
    )

    service = ChatService(test_session)
    frames = [chunk async for chunk in mod.generate_stream(request, service)]

    error_frames = [f for f in frames if f.startswith("event: error")]
    assert error_frames, (
        "NO event:error frame — the empty turn ended in silence again. "
        f"frames={frames[-6:]}"
    )

    payload = json.loads(error_frames[0].split("data: ", 1)[1].strip())
    assert payload["error"]["type"] == "empty_completion"
    assert payload["error"]["message"] == EMPTY_COMPLETION_NOTICE

    # THE ORDERING RULE: the frontend stops reading at the error frame, so
    # it must precede the final done frame.
    done_idx = next(i for i, f in enumerate(frames) if '"done": true' in f)
    err_idx = frames.index(error_frames[0])
    assert err_idx < done_idx

    # The guard is UNCHANGED — no empty assistant row was persisted.
    from sqlalchemy import select
    from app.infrastructure.database.models import ChatMessage

    rows = (await test_session.execute(
        select(ChatMessage).where(ChatMessage.role == "assistant")
    )).scalars().all()
    assert rows == []
