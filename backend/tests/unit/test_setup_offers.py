"""The setup offers — values a fresh install proposes and never assumes.

What these tests defend:

- an offer's model id PARSES as a litellm model string, so a typo fails the
  suite instead of a stranger's first chat (the offers cannot rot);
- a CHAT model is never offered for embeddings — the ruling's sharpest point is
  that "whatever is the default" must not stand in for a known capability, so
  the guarantee is structural (no entry) as well as probed (`_can_embed`);
- a capability nothing can resolve is REPORTED, not filled;
- the structure seed is idempotent and gives `embeddings` its KIND, which is what
  makes the embedding ladder refuse a chat provider at all.
"""

import pytest

from app.domain.providers import setup_offers
from app.domain.providers.capabilities import (
    CAPABILITY_SEED,
    KIND_EMBEDDING,
    ensure_capability_rows,
)
from app.domain.providers.litellm_route import litellm_model_string


def test_every_offer_parses_as_a_litellm_model_string():
    """The offers' ids are the ones a caller can actually dial."""
    import litellm

    checked = 0
    for capability, models in setup_offers.MODEL_FOR.items():
        for provider, model in models.items():
            string = litellm_model_string(provider, model)
            # raises for a string no provider can be resolved from
            litellm.get_llm_provider(string)
            checked += 1
    assert checked >= 1, "no offers to check — the table lost its entries"


def test_no_chat_model_is_offered_as_an_embedder():
    """Structural: `embeddings` has no keyed entries at all, because no embedding
    id here could be verified. Offering one would be the exact answer the ruling
    forbids."""
    assert setup_offers.MODEL_FOR["embeddings"] == {}


def test_keyed_offers_appear_only_with_their_key():
    env = {"DEEPSEEK_API_KEY": True, "OPENROUTER_API_KEY": False}
    offers = setup_offers._keyed_offers("chat", env)
    assert [o.key for o in offers] == ["chat-deepseek"]
    assert offers[0].model == "deepseek-v4-flash"
    assert offers[0].needs == "key:DEEPSEEK_API_KEY"
    assert "DEEPSEEK_API_KEY" in offers[0].reason


def test_a_completion_model_is_not_an_embedder():
    """The probe's own evidence decides — a server's capability list is truth,
    and a model NAME is only consulted when the list is absent."""
    assert setup_offers._can_embed({"id": "Bonsai-27B-Q1_0.gguf", "capabilities": ["completion", "multimodal"]}) is False
    assert setup_offers._can_embed({"id": "nomic-embed-text", "capabilities": ["embedding"]}) is True
    assert setup_offers._can_embed({"id": "all-minilm:latest", "capabilities": []}) is True
    assert setup_offers._can_embed({"id": "llama3:8b", "capabilities": []}) is False


def test_the_embedding_gap_says_what_is_off():
    gap = setup_offers._gap_for("embeddings", "embedding")
    assert "no embedding model" in gap
    assert "off" in gap


def test_the_seed_gives_embeddings_its_kind():
    """Without the row, `resolve()` defaults the kind to `llm` and an embedding
    capability inherits the chat default provider — the second answer the ruling
    removes. The row is what makes the refusal possible."""
    kinds = {key: kind for key, _label, kind in CAPABILITY_SEED}
    assert kinds["embeddings"] == KIND_EMBEDDING
    assert set(kinds) == {
        "title", "chat", "workflow-llm", "memory", "summary",
        "stt", "tts", "exa", "embeddings",
    }


@pytest.mark.asyncio
async def test_the_structure_seed_is_idempotent(test_session):
    """The seed creates what is missing ONCE and then stops — a re-run on a warm
    install adds nothing, and the end state is exactly the nine rows."""
    from sqlalchemy import select

    from app.infrastructure.database.models import Capability

    await ensure_capability_rows(test_session)          # creates whatever is absent
    assert await ensure_capability_rows(test_session) == []   # and then never again

    keys = set((await test_session.execute(select(Capability.key))).scalars().all())
    assert keys == {key for key, _label, _kind in CAPABILITY_SEED}


@pytest.mark.asyncio
async def test_probe_reports_a_gap_for_every_unresolved_capability(test_session):
    report = await setup_offers.probe(test_session)
    for state in report.states:
        if state.resolved:
            assert state.gap == ""
        else:
            assert state.gap, f"{state.capability} is unresolved with nothing said about it"


@pytest.mark.asyncio
async def test_an_unknown_accept_writes_nothing(test_session):
    """An offer key that does not apply is REPORTED, never fuzzily applied."""
    before = await setup_offers.probe(test_session)
    _report, log = await setup_offers.apply(test_session, ["chat-not-a-real-offer"])
    after = await setup_offers.probe(test_session)

    assert any("skipped" in line for line in log)
    assert [s.to_dict() for s in before.states] == [s.to_dict() for s in after.states]
