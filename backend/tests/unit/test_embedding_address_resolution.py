"""THE EMBEDDING SERVER'S ADDRESS — the `ollama` ROW is the one home (the service-literals arc).

`wiki/issues/resolved/embedded-service-literals/local-embedding-server.md`, RULED **option C, staged**: the ADDRESS resolves through the
provider ROW, whose endpoint the app resolves by ONE rule (`provider_endpoints.resolve_endpoint`).

What this replaces is a second family of homes for that one address:

- `core/config.py:366` — `settings.ollama_base_url`, the field that LOOKS configurable and is not;
- `api/v1/rag/router.py:43` — `_get_ollama_base(config)`, which ignored its argument and returned a
  literal while its docstring claimed to resolve;
- `domain/chat/services.py:173` — `self.ollama_base_url`, a class attribute;
- `domain/rag/service.py:337,378` — two `getattr(config, "ollama_base_url", <literal>)` fallbacks against
  a field `SystemManagerConfig` does not even have, so the literal was always the live value.

`None` is an ANSWER: no row declares an endpoint, so the caller reports it. Nothing dials a guess.
"""

from __future__ import annotations

import uuid

import pytest

from app.domain.providers.capabilities import KIND_EMBEDDING
from app.domain.providers.config_service import resolve_named_row_endpoint
from app.infrastructure.database.models import Capability, CapabilityService

from tests import conftest as cf


async def _an_ollama_row(session, base_url: str | None):
    """The `ollama` row the test is about — the copy usually carries one (`conftest`).

    Update-an-existing-or-insert is `cf.get_or_create_provider`, where the rule and its reason
    (the copied test database) are written down once.
    """
    return await cf.get_or_create_provider(
        session,
        name="ollama",
        provider_type="ollama",
        display_name="Ollama (Local)",
        base_url=base_url,
        is_active=True,
        priority=1,
        config={},
    )


async def _an_embeddings_capability(
    session, provider_row_id: int, model: str = "nomic-embed-text"
) -> str:
    """The `embeddings` capability pointing at a row AND naming a model — the ONE path a real install
    configures.

    The address half resolved the `ollama` ROW by NAME, written in the caller; the model half
    (`wiki/issues/resolved/embedded-service-literals/embedding-model-and-dims.md`) moved that too: the capability names the row AND the
    model, so the row's name is configuration rather than a literal. The key is unique per call, as
    every capability test does, so nothing here depends on the seeded rows.
    """
    key = f"zz-embeddings-{uuid.uuid4().hex[:8]}"
    row = Capability(key=key, label="Test embeddings", kind=KIND_EMBEDDING, enabled=True)
    session.add(row)
    await session.flush()
    session.add(
        CapabilityService(
            capability_id=row.id, ordinal=0, enabled=True, provider_id=provider_row_id, model=model
        )
    )
    await session.flush()
    return key


# ── the rule's lookup ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_row_is_the_address(test_session):
    await _an_ollama_row(test_session, "http://127.0.0.1:9999")

    assert await resolve_named_row_endpoint(test_session, "ollama") == "http://127.0.0.1:9999"


@pytest.mark.asyncio
async def test_no_row_resolves_to_no_endpoint_not_to_a_literal(test_session):
    assert await resolve_named_row_endpoint(test_session, "ollama") is None


# ── the rag health response reports what is dialled ──────────────────────────


@pytest.mark.asyncio
async def test_the_rag_health_reports_the_rows_address(
    test_session, monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """The health reports what the `embeddings` capability resolves: the row's address AND the model.

    The address half passed the endpoint in as a bare string; the model half hands the whole service
    in, because the model and the dims ride with it (one decision, one answer).
    """
    from app.core.config import Paths
    from app.core.system_manager import SystemManagerConfig
    from app.domain.providers import embeddings as emb
    from app.domain.rag.service import RagIngestService

    # THE HEALTH READ RESOLVES THE INSTALLATION'S INDEX (2026-10-12) — and in a test the installation
    # is the OPERATOR's, which the suite's `SharedDbGuard` forbids reading. Point it at this test's own
    # empty path: the counts are not this test's subject, the address and the model are.
    monkeypatch.setattr(Paths, "rag_index_path", tmp_path / "system_docs_vector.db")

    row = await _an_ollama_row(test_session, "http://127.0.0.1:9999")
    key = await _an_embeddings_capability(test_session, row.id)
    monkeypatch.setattr(emb, "EMBEDDINGS_CAPABILITY_KEY", key)

    embedding = await emb.resolve_embedding_service(test_session)
    health = RagIngestService.get_index_health(SystemManagerConfig.defaults(), embedding)

    assert health.config.ollama_base_url == "http://127.0.0.1:9999"
    assert health.config.embedding_model == "nomic-embed-text"


@pytest.mark.asyncio
async def test_the_rag_health_reports_no_address_rather_than_the_literal(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """An unconfigured install must SAY so: the response may not fall back to `localhost:11434`.

    The address half could only report a missing ENDPOINT; with the model and the dims in the same
    answer, "not configured" is now a whole service — and the health response says so on every part.
    """
    from app.core.config import Paths
    from app.core.system_manager import SystemManagerConfig
    from app.domain.providers.embeddings import EmbeddingService
    from app.domain.rag.service import RagIngestService

    # See the sibling above: the read must stay inside the test installation.
    monkeypatch.setattr(Paths, "rag_index_path", tmp_path / "system_docs_vector.db")

    health = RagIngestService.get_index_health(
        SystemManagerConfig.defaults(), EmbeddingService()
    )

    assert health.config.ollama_base_url is None
    assert health.config.embedding_model is None


# ── the chat service's local Ollama path ─────────────────────────────────────


@pytest.mark.asyncio
async def test_the_chat_service_resolves_the_rows_address(test_session):
    from app.domain.chat.services import ChatService

    await _an_ollama_row(test_session, "http://127.0.0.1:9998")

    assert await ChatService(test_session)._ollama_endpoint() == "http://127.0.0.1:9998"


# ── the retired home ─────────────────────────────────────────────────────────


def test_the_settings_field_is_retired():
    """A settings field for an address a ROW owns is the second home the arc removes."""
    from app.core.config import get_settings

    assert not hasattr(get_settings(), "ollama_base_url")
