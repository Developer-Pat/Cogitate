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
from sqlalchemy import delete, select

from app.domain.providers import setup_offers
from app.domain.providers.capabilities import (
    CAPABILITY_SEED,
    KIND_EMBEDDING,
    ensure_capability_rows,
)
from app.domain.providers.litellm_route import litellm_model_string
from app.infrastructure.database.models import Provider


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


async def _isolate_provider(db, name: str = "deepseek") -> None:
    """Put the database in a state this test can NAME, instead of inheriting one.

    `apply()` COMMITS, so a row written by an earlier test can survive in the test database
    and silently flip which branch is exercised — measured: this file passed 10/10 on three
    consecutive runs while its own acceptance test, run alone, was red on the log assertion.
    Every test below therefore deletes the row it is about and clears any default provider,
    because the inheritance branch fires only when NONE exists.
    """
    await db.execute(delete(Provider).where(Provider.name == name))
    for row in (await db.execute(select(Provider))).scalars().all():
        row.is_default = False
    await db.commit()


def _chat_offer() -> setup_offers.Offer:
    return setup_offers.Offer(
        key="chat-deepseek",
        capability="chat",
        provider="deepseek",
        provider_type="deepseek",
        model="deepseek-v4-flash",
        reason="the test's offer",
        needs="key:DEEPSEEK_API_KEY",
    )


def _report_with(offer: setup_offers.Offer) -> setup_offers.SetupReport:
    return setup_offers.SetupReport(
        states=[
            setup_offers.CapabilityState(
                capability="chat",
                kind="llm",
                resolved=False,
                detail="nothing resolves",
                offers=[offer],
                gap="no model resolves for 'chat'",
            )
        ]
    )


async def test_accepting_chat_puts_the_model_on_the_default_provider_row(test_session, monkeypatch):
    """The inheritance must be REAL: the resolver's last rung reads `config.default_model`.

    Measured on a fresh install (2026-11-19): `--accept-defaults` printed
    `✓ title deepseek (global default)` while the provider row's config was `{}`, so every
    session's title generation 500'd with "TitleService has no model configured".

    This is the row ALREADY EXISTS, bare — the shape the live install had.
    """
    await ensure_capability_rows(test_session)
    await _isolate_provider(test_session)
    test_session.add(
        Provider(
            name="deepseek",
            display_name="Deepseek",
            provider_type="deepseek",
            base_url="https://api.deepseek.com",
            is_active=True,
            config={},
        )
    )
    await test_session.commit()

    offer = _chat_offer()
    async def fake_probe(db, env_path=None):
        return _report_with(offer)

    monkeypatch.setattr(setup_offers, "probe", fake_probe)
    _report, log = await setup_offers.apply(test_session, ["chat-deepseek"])

    row = (
        await test_session.execute(select(Provider).where(Provider.name == "deepseek"))
    ).scalars().one()
    assert row.is_default, "the accepted chat offer names the default provider"
    assert (row.config or {}).get("default_model") == "deepseek-v4-flash", (
        "without the model on the row, the other LLM capabilities resolve to a provider that "
        "cannot be called — the '✓ title' that 500'd on the fresh install"
    )
    assert any("default model" in line for line in log), (
        "the accept must SAY it named the default and put the model there — the line a "
        "person reads while accepting is part of the behaviour"
    )


async def test_a_created_provider_row_carries_the_model_and_becomes_the_default(
    test_session, monkeypatch
):
    """The other shape: NO row at all, so `apply` creates it — and the model must ride it.

    The creation path is a separate write (`_provider_row`), so a bare-row test cannot prove
    it: this one deletes the row first and asserts the row that comes back is dialable.
    """
    await ensure_capability_rows(test_session)
    await _isolate_provider(test_session)
    assert (
        await test_session.execute(select(Provider).where(Provider.name == "deepseek"))
    ).scalar_one_or_none() is None, "the fixture cleanup left a row — the create path is untested"

    offer = _chat_offer()
    async def fake_probe(db, env_path=None):
        return _report_with(offer)

    monkeypatch.setattr(setup_offers, "probe", fake_probe)
    _report, _log = await setup_offers.apply(test_session, ["chat-deepseek"])

    row = (
        await test_session.execute(select(Provider).where(Provider.name == "deepseek"))
    ).scalars().one()
    assert row.is_default
    assert (row.config or {}).get("default_model") == "deepseek-v4-flash"
