"""The local llama.cpp server, driven through OUR factory — the conditional live test.

WHY IT EXISTS. The app's "which service answers this?" path has to work against a service we
control, offline, with no key and no spend. This is that test bed: the user's local llama.cpp
server (the llama.cpp OpenAI-compatible endpoint, `127.0.0.1:8080` by default).

THE GATE IS THE HOUSE'S OWN. `external("llama-cpp")` is the generic external tier: a probe
registered in `EXTERNAL_PROBES` answers "is the local llama.cpp server up?", this file SKIPS with
that reason when it is not, and an unregistered dependency name FAILS the test rather than passing
it. So the file is green-with-a-visible-skip on a machine with no local model server, and green for
real on one that has it — never a silent pass and never a hang. Override the address with
`LLAMA_CPP_URL` (the probe reads it too).

WHAT IT PROVES: the app's own construction path — the one the resolver, the workflow factories and
the title service all end at — builds a client against a LOOPBACK row and gets an answer back with
token usage. Two shapes, because two different things can break: the CONSTRUCTION (no database) and
the arc's own seam (capability → resolver → factory → answer).

WHAT IT DELIBERATELY DOES NOT PROVE: answer QUALITY. The model is whatever the server has loaded —
a 1-bit 27B quant on this machine answers "ok" and would fail a prose assertion on the next prompt —
so every assertion is about SHAPE (a response arrived, tokens were counted). A test that graded the
words would be measuring someone else's model, not our code.
"""

from __future__ import annotations

import json
import os
import urllib.request
import uuid

import pytest
from sqlalchemy import select

from app.domain.providers import capabilities as cap
from app.domain.providers.config_service import ProviderConfig
from app.domain.providers.llm_factory import (
    LOCAL_KEY_PLACEHOLDER,
    get_llm_for_capability,
    get_llm_from_config,
)
from app.infrastructure.database.models import Capability, CapabilityService, Provider

pytestmark = pytest.mark.external("llama-cpp")

#: The default address the app's own `llama` provider row carries (read 2026-09-30). `LLAMA_CPP_URL`
#: overrides it — the SAME variable the registered probe reads, so a test and its gate can never
#: disagree about which server they are talking to.
BASE = os.environ.get("LLAMA_CPP_URL", "http://127.0.0.1:8080").rstrip("/") + "/v1"
PROMPT = "Reply with the single word: ok"


def _served_model() -> str:
    """The model the local server has loaded, named the way the app's rows name it.

    READ, never hardcoded: the server is whatever the user started, and a test that named a `.gguf`
    would break the day they load a different one. llama.cpp also accepts any model string while
    exactly one model is loaded, so the basename is a label rather than a dispatch key.
    """
    with urllib.request.urlopen(f"{BASE}/models", timeout=5) as resp:
        payload = json.loads(resp.read())
    return payload["data"][0]["id"].rsplit("/", 1)[-1]


def _assert_an_answer_came_back(result) -> None:
    """The shape assertion both tests share — a response AND its token accounting."""
    assert isinstance(result.content, str) and result.content.strip(), "no content came back"
    usage = getattr(result, "usage_metadata", None) or {}
    assert usage.get("total_tokens", 0) > 0, f"no token usage reported: {usage!r}"


async def _local_row(session, model: str) -> Provider:
    """The `llama` row — reused when the copied test database already carries one.

    `conftest` copies a real installation, so a row named `llama` usually exists; this keeps the
    address and model of the row the test uses under the TEST's control either way.
    """
    row = (
        await session.execute(select(Provider).where(Provider.name == "llama"))
    ).scalar_one_or_none()
    if row is None:
        row = Provider(
            name="llama",
            display_name="Llama Server",
            provider_type="openai",
            base_url=BASE,
            is_active=True,
            priority=99,
        )
        session.add(row)
    row.base_url = BASE
    row.config = {"default_model": model}
    await session.flush()
    return row


@pytest.mark.anyio
async def test_the_factory_builds_a_client_that_answers_from_the_local_server() -> None:
    """The CONSTRUCTION path, no database: a loopback row → a real completion.

    The key is passed explicitly because that is the house contract for a loopback row: the
    openai-shaped adapter refuses to construct without a non-empty value, and the app's own path
    supplies `LOCAL_KEY_PLACEHOLDER` for it (`get_llm_for_capability` fetches the stored key first
    and falls back to the placeholder when the row is local). A new caller that forgets it dies at
    `Missing credentials` — measured, on the default row, before that seam existed.
    """
    model = _served_model()
    config = ProviderConfig(
        name="llama",
        provider_type="openai",
        base_url=BASE,
        config={"default_model": model},
    )

    llm = get_llm_from_config(
        config, temperature=0.0, max_tokens=16, api_key=LOCAL_KEY_PLACEHOLDER
    )
    _assert_an_answer_came_back(await llm.ainvoke(PROMPT))


@pytest.mark.anyio
async def test_a_capability_pointing_at_the_local_row_answers_through_the_resolver(
    test_session,
) -> None:
    """The arc's own seam: capability → resolver → factory → the local server's answer.

    The rows are built HERE rather than read from the live wiring, so the test means the same thing
    on a machine that has never run the arc's own local-provider setup script.
    """
    model = _served_model()
    provider = await _local_row(test_session, model)

    capability = Capability(
        key=f"zz-local-{uuid.uuid4().hex[:8]}", label="Local test", kind=cap.KIND_LLM, enabled=True
    )
    test_session.add(capability)
    await test_session.flush()
    test_session.add(
        CapabilityService(
            capability_id=capability.id,
            ordinal=0,
            provider_id=provider.id,
            model=model,
            enabled=True,
        )
    )
    await test_session.commit()

    llm = await get_llm_for_capability(test_session, capability.key, max_tokens=16)

    # None here would mean the resolution found nothing attemptable — the failure this test is
    # looking for is a client that cannot reach the local server, not a missing resolution.
    assert llm is not None
    _assert_an_answer_came_back(await llm.ainvoke(PROMPT))
