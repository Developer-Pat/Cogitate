"""THE EMBEDDING MODEL AND ITS DIMS — the `embeddings` capability (the service-literals arc).

`wiki/issues/resolved/embedded-service-literals/embedding-model-and-dims.md`, RULED **option C** — the second half of the embedding
family, whose ADDRESS half landed separately:

- which server answers  → the capability's provider ROW (the address half's rule, reused);
- which model runs      → the capability's own candidate (a pinned model beats the row's default);
- how wide the vectors  → DERIVED from the model, through ONE map (`EMBEDDING_DIMS_BY_MODEL`).

What this replaces: `nomic-embed-text` and `768` written into SIX places (three vector stores, twice
in `doc_reader.py`, the system-manager defaults, the rag health schema), each pair independent, so a
model changed without its dims wrote the wrong width into an index that accepts it.

TWO RULES THIS FILE PINS, both from the ruling (EXA'S INSTALLATION SKILL):

1. **The seed ships STRUCTURE, never a value.** The `embeddings` capability exists; it names no
   model. A migration cannot be declined, which is why a model may not live in one.
2. **The app REPORTS the gap, never guesses it.** An unconfigured install answers
   `no embedding model: indexing and search are off` — and in particular the CHAT default row does
   NOT answer for an embedding capability: that row is an LLM, and inheriting it would be the app
   deciding which server embeds.

The resolution is exercised against the TEST DATABASE with the REAL resolver, on rows this file
creates (unique `zz-` keys), so nothing here depends on the seeded capability rows or on the live
provider list. Discriminators: each test goes red when its behaviour is reverted.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, Optional

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers import capabilities as cap
from app.domain.providers import embeddings as emb
from app.domain.providers.config_service import DefaultProviderService
from app.infrastructure.database.models import Capability, CapabilityService, Provider


async def _provider_row(
    session: AsyncSession,
    name: str,
    base_url: Optional[str] = "http://127.0.0.1:9999",
    default_model: Optional[str] = "nomic-embed-text",
) -> Provider:
    """An embedding-server row: an `ollama`-class row, whose endpoint is the address."""
    row = Provider(
        name=name,
        display_name=name,
        provider_type="ollama",
        base_url=base_url,
        is_active=True,
        priority=99,
        config={"default_model": default_model} if default_model else {},
    )
    session.add(row)
    await session.flush()
    return row


async def _capability(
    session: AsyncSession,
    key: str,
    kind: str,
    candidates: Optional[list[dict[str, Any]]] = None,
) -> str:
    """A capability of the given kind, with the candidates supplied (none by default)."""
    row = Capability(key=key, label="Test embeddings", kind=kind, enabled=True)
    session.add(row)
    await session.flush()
    for ordinal, spec in enumerate(candidates or []):
        session.add(CapabilityService(capability_id=row.id, ordinal=ordinal, enabled=True, **spec))
    await session.flush()
    return key


def _a_chat_default_row() -> SimpleNamespace:
    """The global default provider row, stubbed: an LLM row, and not an embedding server."""
    return SimpleNamespace(
        id=999_001,
        name="zz-chat-default",
        provider_type="groq",
        default_model="zz-chat-model",
        location="cloud",
    )


def _no_default_row(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _none(self: DefaultProviderService, db: AsyncSession) -> None:
        return None

    monkeypatch.setattr(DefaultProviderService, "get_default_provider", _none)


def _a_default_row(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _one(self: DefaultProviderService, db: AsyncSession) -> SimpleNamespace:
        return _a_chat_default_row()

    monkeypatch.setattr(DefaultProviderService, "get_default_provider", _one)


# ── the three facts, resolved in one place ───────────────────────────────────


@pytest.mark.asyncio
async def test_the_capability_names_the_model_and_the_row_names_the_address(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row carries the address, the capability carries the model, the map carries the width."""
    row = await _provider_row(test_session, f"zz-emb-{uuid.uuid4().hex[:6]}")
    key = await _capability(
        test_session, f"zz-emb-cap-{uuid.uuid4().hex[:6]}", cap.KIND_EMBEDDING,
        [{"provider_id": row.id}],
    )
    monkeypatch.setattr(emb, "EMBEDDINGS_CAPABILITY_KEY", key)

    service = await emb.resolve_embedding_service(test_session)

    assert service.address == "http://127.0.0.1:9999"
    assert service.model == "nomic-embed-text"
    assert service.dims == 768
    assert service.resolved is True


@pytest.mark.asyncio
async def test_a_pinned_model_beats_the_rows_default_and_brings_its_dims(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dims FOLLOW the model — the one pairing the old six literals could not keep."""
    row = await _provider_row(test_session, f"zz-emb-{uuid.uuid4().hex[:6]}")
    key = await _capability(
        test_session, f"zz-emb-cap-{uuid.uuid4().hex[:6]}", cap.KIND_EMBEDDING,
        [{"provider_id": row.id, "model": "mxbai-embed-large"}],
    )
    monkeypatch.setattr(emb, "EMBEDDINGS_CAPABILITY_KEY", key)

    service = await emb.resolve_embedding_service(test_session)

    assert service.model == "mxbai-embed-large"
    assert service.dims == 1024, "the width must follow the PINNED model, not the row's default"
    assert service.address == "http://127.0.0.1:9999"


@pytest.mark.asyncio
async def test_an_unknown_model_reports_no_dims_rather_than_a_guessed_one(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A model whose width this app does not know is NOT assumed to be 768 wide."""
    row = await _provider_row(test_session, f"zz-emb-{uuid.uuid4().hex[:6]}")
    key = await _capability(
        test_session, f"zz-emb-cap-{uuid.uuid4().hex[:6]}", cap.KIND_EMBEDDING,
        [{"provider_id": row.id, "model": "zz-mystery-embed"}],
    )
    monkeypatch.setattr(emb, "EMBEDDINGS_CAPABILITY_KEY", key)

    service = await emb.resolve_embedding_service(test_session)

    assert service.model == "zz-mystery-embed"
    assert service.dims is None
    assert service.resolved is False
    assert "dims" in service.missing()


@pytest.mark.asyncio
async def test_a_row_with_no_model_is_not_fully_resolved(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An endpoint with no model is HALF an answer — and half is reported, not completed."""
    row = await _provider_row(test_session, f"zz-emb-{uuid.uuid4().hex[:6]}", default_model=None)
    key = await _capability(
        test_session, f"zz-emb-cap-{uuid.uuid4().hex[:6]}", cap.KIND_EMBEDDING,
        [{"provider_id": row.id}],
    )
    monkeypatch.setattr(emb, "EMBEDDINGS_CAPABILITY_KEY", key)

    service = await emb.resolve_embedding_service(test_session)

    assert service.address == "http://127.0.0.1:9999"
    assert service.model is None
    assert service.dims is None
    assert service.resolved is False
    assert "model" in service.missing()


# ── the unconfigured install REPORTS (the seed ships structure, never a value) ─


@pytest.mark.asyncio
async def test_no_capability_reports_and_names_no_model(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing configured: the answer names NO model — `nomic-embed-text` may not survive as one."""
    _no_default_row(monkeypatch)
    monkeypatch.setattr(emb, "EMBEDDINGS_CAPABILITY_KEY", f"zz-missing-{uuid.uuid4().hex[:8]}")

    service = await emb.resolve_embedding_service(test_session)

    assert service.model is None
    assert service.dims is None
    assert service.address is None
    assert service.resolved is False
    assert emb.NO_EMBEDDING_MODEL in service.report()


@pytest.mark.asyncio
async def test_an_empty_capability_does_NOT_inherit_the_chat_default_row(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seed ships the capability EMPTY — and empty must not mean \"the chat default embeds\".

    This is the ruling's second rule: the global default row is the CHAT default (an LLM). Letting it
    answer \"which server runs my embedding model\" would be the app deciding, and it would show up as
    an embedding capability quietly served by whatever chat model the install happened to choose.
    """
    _a_default_row(monkeypatch)
    monkeypatch.setattr(emb, "EMBEDDINGS_CAPABILITY_KEY", f"zz-empty-{uuid.uuid4().hex[:8]}")
    await _capability(test_session, emb.EMBEDDINGS_CAPABILITY_KEY, cap.KIND_EMBEDDING)

    service = await emb.resolve_embedding_service(test_session)

    assert service.model is None
    assert service.address is None
    assert service.resolved is False
    assert service.reason == cap.REASON_NONE


@pytest.mark.asyncio
async def test_an_llm_capability_STILL_inherits_the_default_row(
    test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The control: the ladder's last rung is unchanged for the kind it was written for."""
    _a_default_row(monkeypatch)
    key = await _capability(test_session, f"zz-llm-{uuid.uuid4().hex[:8]}", cap.KIND_LLM)

    resolved = await cap.resolve(test_session, key)

    assert resolved.reason == cap.REASON_GLOBAL_DEFAULT
    assert resolved.primary is not None
    assert resolved.primary.model == "zz-chat-model"


# ── the definition, and the vocabulary ───────────────────────────────────────


def test_the_dims_map_is_the_one_definition_of_a_models_width() -> None:
    """`nomic-embed-text` IS 768 wide — one entry, one home, and the note lives with it."""
    assert emb.EMBEDDING_DIMS_BY_MODEL["nomic-embed-text"] == 768
    assert emb.EMBEDDING_DIMS_BY_MODEL["mxbai-embed-large"] == 1024


def test_the_embeddings_kind_is_in_the_vocabulary() -> None:
    """The read-out serves `KINDS` — a kind not in it is a capability the page cannot label."""
    assert cap.KIND_EMBEDDING in cap.KINDS
    assert cap.EMBEDDINGS_CAPABILITY_KEY == "embeddings"
