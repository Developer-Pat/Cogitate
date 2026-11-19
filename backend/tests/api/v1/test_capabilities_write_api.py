"""The capability EDIT path over HTTP — phase 6, group 1 (the API half).

`PUT /providers/capabilities/{key}` replaces a capability's whole ordered chain. These tests pin
what a client can rely on: the round trip (write, then read back through the same read-out the
surfaces use), the two refusal codes — **404** for a key that is not a capability, **400** for a
candidate that cannot be attempted — and the fact that a refusal stores NOTHING.

**Every test provisions what it reads.** The suite's `auto_clean_tables` fixture truncates all ORM
tables after each test, so the provider row and the `tts` capability below are created (or REUSED, by
their natural key) by the test that needs them rather than assumed from the seeded copy.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Paths
from app.domain.providers.capabilities import KIND_EMBEDDING, KIND_LLM, KIND_SPEECH, REASON_DISABLED
from app.domain.providers.embeddings import EMBEDDINGS_CAPABILITY_KEY, EmbeddingService
from app.domain.tools.builtin.doc_vector_store import DocVectorStore
from app.infrastructure.database.models import Capability, CapabilityService, Provider


async def _capability(session: AsyncSession, *, kind: str = KIND_LLM) -> Capability:
    """A throwaway capability for the request to aim at."""
    row = Capability(
        key=f"zz-api-write-{uuid.uuid4().hex[:8]}",
        label="API write-path test capability",
        kind=kind,
        enabled=True,
    )
    session.add(row)
    await session.flush()
    session.add(
        CapabilityService(capability_id=row.id, ordinal=0, service_name="zz-original-engine")
    )
    await session.commit()
    return row


async def _provider(session: AsyncSession, *, base_url: str = "https://example.invalid/v1") -> Provider:
    """A provider row of this test's own (committed: the route reads it on another session)."""
    row = Provider(
        name=f"zz-api-prov-{uuid.uuid4().hex[:8]}",
        display_name="API write-path test provider",
        provider_type="openai",
        base_url=base_url,
        is_active=True,
        priority=99,
        is_default=False,
        config={"default_model": "zz-provider-model"},
    )
    session.add(row)
    await session.commit()
    return row


async def _tts(session: AsyncSession) -> tuple[Capability, bool]:
    """The installation's `tts` capability — reused when present, provisioned when truncated."""
    row = (
        await session.execute(select(Capability).where(Capability.key == "tts"))
    ).scalar_one_or_none()
    if row is not None:
        return row, False
    row = Capability(key="tts", label="Speech engine selection", kind=KIND_SPEECH, enabled=True)
    session.add(row)
    await session.flush()
    session.add(CapabilityService(capability_id=row.id, ordinal=0, service_name="edge"))
    await session.commit()
    return row, True


@pytest.mark.anyio
async def test_a_chain_is_replaced_and_reads_back_in_order(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Write a two-candidate chain, then read it through the SAME surface the page reads."""
    row = await _capability(test_session)
    provider = await _provider(test_session)
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={
                "candidates": [
                    {"service_name": "zz-api-engine"},
                    {"provider_id": provider.id, "model": "zz-api-model", "thinking": "low"},
                ]
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["key"] == row.key
        assert body["reason"] == "capability config"
        assert body["chain"] == f"zz-api-engine -> {provider.name}/zz-api-model"
        assert body["primary"]["ordinal"] == 0
        assert body["primary"]["service_name"] == "zz-api-engine"
        assert body["backups"][0]["ordinal"] == 1
        assert body["backups"][0]["provider_id"] == provider.id
        assert body["backups"][0]["model"] == "zz-api-model"

        reread = await client.get(f"/api/v1/providers/capabilities/{row.key}")
        assert reread.status_code == 200
        assert reread.json() == body, "the write's own response disagrees with the read-out"
    finally:
        await test_session.delete(row)
        await test_session.delete(provider)
        await test_session.commit()


@pytest.mark.anyio
async def test_a_class_candidate_reads_back_as_the_class_it_was_written_as(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """The read-out MIRRORS the write: a chain read from the API can be sent straight back.

    Without the class on the wire, an editor holding an expanded row could only write back "this
    one row that happens to be local" — a different configuration from "prefer local", and one that
    would stop following the installation as its local inventory changes.
    """
    row = await _capability(test_session)
    local = await _provider(test_session, base_url="http://127.0.0.1:9/v1")
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={"candidates": [{"require_location": "local"}]},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["primary"] is not None, "the local provider this test created did not expand"
        assert body["primary"]["require_location"] == "local"
        assert body["primary"]["source"] == "class"
        assert body["primary"]["provider_id"] == local.id
    finally:
        await test_session.delete(row)
        await test_session.delete(local)
        await test_session.commit()


@pytest.mark.anyio
async def test_the_stored_chain_is_served_beside_the_resolution(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """An editor reads `configured`; the RESOLUTION is a different thing and cannot be written back.

    Measured difference, in one payload: a class candidate is served AS a class (not expanded into
    the rows it happens to match), and a row switched OFF is INCLUDED in `configured` while the
    resolution filters it out entirely. An editor fed by `primary`/`backups` would therefore drop the
    disabled row and rewrite expanded rows as if they were the stored ones.
    """
    row = await _capability(test_session)
    local = await _provider(test_session, base_url="http://127.0.0.1:9/v1")
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={
                "candidates": [
                    {"require_location": "local"},
                    {"service_name": "zz-off-engine", "enabled": False},
                ]
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()

        # the stored chain: two rows, as written, the second one off
        assert len(body["configured"]) == 2
        assert [c["source"] for c in body["configured"]] == ["stored", "stored"]
        assert body["configured"][0]["require_location"] == "local"
        assert body["configured"][0]["service_name"] is None
        assert body["configured"][1]["service_name"] == "zz-off-engine"
        assert body["configured"][1]["enabled"] is False

        # the resolution: the class EXPANDED, and the off row nowhere in it
        assert body["primary"]["source"] == "class"
        assert body["primary"]["require_location"] == "local"
        assert body["primary"]["provider_id"] == local.id
        served = [c["service_name"] for c in [body["primary"], *body["backups"]]]
        assert "zz-off-engine" not in served
    finally:
        await test_session.delete(row)
        await test_session.delete(local)
        await test_session.commit()


@pytest.mark.anyio
async def test_the_off_switch_reads_back_as_disabled_with_nothing_resolved(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """`enabled=false` is the availability ruling's "the agent is disabled" — a state, not a hint."""
    row = await _capability(test_session)
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={"enabled": False, "candidates": []},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["enabled"] is False
        assert body["reason"] == REASON_DISABLED
        assert body["primary"] is None
        assert body["backups"] == []
    finally:
        await test_session.delete(row)
        await test_session.commit()


@pytest.mark.anyio
async def test_a_refused_candidate_is_a_400_and_stores_nothing(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """The stored chain is what the reader saw before the failed request."""
    row = await _capability(test_session)
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={"candidates": [{"provider_id": 999999}]},
        )

        assert response.status_code == 400
        assert "999999" in response.json()["detail"]

        reread = await client.get(f"/api/v1/providers/capabilities/{row.key}")
        assert reread.json()["chain"] == "zz-original-engine", (
            "a refused write reached the stored chain"
        )

        two_forms = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={"candidates": [{"service_name": "zz-x", "require_location": "local"}]},
        )
        assert two_forms.status_code == 400
        assert "exactly ONE" in two_forms.json()["detail"]
    finally:
        await test_session.delete(row)
        await test_session.commit()


@pytest.mark.anyio
async def test_an_unknown_key_is_a_404_not_a_new_capability(client: AsyncClient) -> None:
    """Capabilities are seeded vocabulary: the write answers like the read does, and creates none."""
    response = await client.put(
        "/api/v1/providers/capabilities/zz-no-such-capability",
        json={"candidates": []},
    )

    assert response.status_code == 404
    assert "zz-no-such-capability" in response.json()["detail"]


@pytest.mark.anyio
async def test_a_speech_engine_no_registry_can_build_is_refused_and_the_row_is_unchanged(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """The named form, over HTTP: the engine's own vocabulary is the registry's.

    Aimed at `tts` because that is the key whose names have a registry — and it is a REFUSAL, so
    nothing is written: the row's chain reads back exactly as it did before the request.
    """
    row, created = await _tts(test_session)
    try:
        before = await client.get("/api/v1/providers/capabilities/tts")
        assert before.status_code == 200

        response = await client.put(
            "/api/v1/providers/capabilities/tts",
            json={"candidates": [{"service_name": "zz-not-an-engine"}]},
        )

        assert response.status_code == 400
        assert "TTS" in response.json()["detail"]
        after = await client.get("/api/v1/providers/capabilities/tts")
        assert after.json() == before.json(), "a refused speech write reached the stored row"
    finally:
        if created:
            await test_session.delete(row)
            await test_session.commit()


@pytest.mark.anyio
async def test_the_candidate_list_is_required(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """A replace must be told the chain: omitting it is a 422, never a silent keep."""
    row = await _capability(test_session)
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}", json={"label": "no chain here"}
        )
        assert response.status_code == 422
    finally:
        await test_session.delete(row)
        await test_session.commit()


# ─── The note: the one save the running process will not read (option C, 2026-10-12) ────────────


async def _embeddings_capability(session: AsyncSession) -> tuple[Capability, bool]:
    """The REAL `embeddings` capability — created only if the copied database does not carry it.

    The note fires on this key and no other (the RAG stores capture its answer at first construction),
    so the test aims at the row the install has rather than a throwaway key of its own. The bool says
    whether THIS test must remove it again.
    """
    existing = (
        await session.execute(
            select(Capability).where(Capability.key == EMBEDDINGS_CAPABILITY_KEY)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    row = Capability(
        key=EMBEDDINGS_CAPABILITY_KEY, label="Embeddings", kind=KIND_EMBEDDING, enabled=True
    )
    session.add(row)
    await session.commit()
    return row, True


def _a_service(dims: int = 768) -> EmbeddingService:
    """A resolved embedding service for the store this test builds — the store's one dependency."""
    return EmbeddingService(address="http://127.0.0.1:11434", model="nomic-embed-text", dims=dims)


def _an_index_at(path, dims: int = 768) -> None:
    """Create a REAL index whose vec table was created at `dims`, then drop the singleton."""
    DocVectorStore.reset_instance()
    DocVectorStore.get_instance(db_path=str(path), embedding=_a_service(dims)).init_db()
    DocVectorStore.reset_instance()


@pytest.mark.anyio
async def test_saving_a_model_the_index_cannot_hold_is_reported_at_the_save(
    client: AsyncClient, test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The ONE thing a save cannot fix (2026-10-12): the index keeps the width it was CREATED at.

    The write resets the stores (option A), so a saved model reaches the process — but a model of
    another width leaves the index behind, and the response says so where the model is chosen.
    """
    index = tmp_path / "system_docs_vector.db"
    _an_index_at(index, dims=768)
    monkeypatch.setattr(Paths, "rag_index_path", index)

    row, created = await _embeddings_capability(test_session)
    provider = await _provider(test_session)
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={"candidates": [{"provider_id": provider.id, "model": "mxbai-embed-large"}]},
        )

        assert response.status_code == 200, response.text
        note = response.json()["note"]
        assert note is not None
        assert "the index is 768 wide" in note
        assert "1024" in note  # mxbai-embed-large
        assert "re-run the ingest" in note
    finally:
        await test_session.delete(provider)
        if created:
            await test_session.delete(row)
        await test_session.commit()


@pytest.mark.anyio
async def test_a_save_the_index_can_hold_carries_no_note(
    client: AsyncClient, test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """The control: a 768-wide model against a 768-wide index has nothing to warn about."""
    index = tmp_path / "system_docs_vector.db"
    _an_index_at(index, dims=768)
    monkeypatch.setattr(Paths, "rag_index_path", index)

    row, created = await _embeddings_capability(test_session)
    provider = await _provider(test_session)
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={"candidates": [{"provider_id": provider.id, "model": "nomic-embed-text"}]},
        )

        assert response.status_code == 200, response.text
        assert response.json()["note"] is None
    finally:
        await test_session.delete(provider)
        if created:
            await test_session.delete(row)
        await test_session.commit()


@pytest.mark.anyio
async def test_saving_the_embeddings_chain_drops_the_rag_stores(
    client: AsyncClient, test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Option A (2026-10-12): the write path RESETS the singletons, so the next use rebuilds them.

    Without this the stores keep the service they were built with, and the save waits for a restart —
    which is exactly what the surfaces used to have to say.
    """
    # The save also ASKS the index for its width (to say when a model will not fit it), and in a test
    # the installation's index is the OPERATOR's — which the suite's `SharedDbGuard` forbids reading.
    monkeypatch.setattr(Paths, "rag_index_path", tmp_path / "system_docs_vector.db")

    DocVectorStore.reset_instance()
    DocVectorStore.get_instance(db_path=str(tmp_path / "index.db"), embedding=_a_service())
    assert DocVectorStore.current_service() is not None

    row, created = await _embeddings_capability(test_session)
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}", json={"candidates": []}
        )

        assert response.status_code == 200, response.text
        assert DocVectorStore.current_service() is None  # dropped — the next use builds a fresh one
    finally:
        DocVectorStore.reset_instance()
        if created:
            await test_session.delete(row)
        await test_session.commit()


@pytest.mark.anyio
async def test_another_capability_leaves_the_rag_stores_alone(
    client: AsyncClient, test_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    """Only the `embeddings` chain decides that service — every other kind is resolved per call."""
    monkeypatch.setattr(Paths, "rag_index_path", tmp_path / "system_docs_vector.db")

    DocVectorStore.reset_instance()
    DocVectorStore.get_instance(db_path=str(tmp_path / "index.db"), embedding=_a_service())

    row = await _capability(test_session)
    provider = await _provider(test_session)
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={"candidates": [{"provider_id": provider.id, "model": "zz-api-model"}]},
        )

        assert response.status_code == 200, response.text
        assert DocVectorStore.current_service() is not None  # untouched
    finally:
        DocVectorStore.reset_instance()
        await test_session.delete(row)
        await test_session.delete(provider)
        await test_session.commit()


@pytest.mark.anyio
async def test_another_capability_carries_no_note(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """Every other kind is resolved per call, so its saves DO reach the process — no note."""
    row = await _capability(test_session)
    provider = await _provider(test_session)
    try:
        response = await client.put(
            f"/api/v1/providers/capabilities/{row.key}",
            json={"candidates": [{"provider_id": provider.id, "model": "zz-api-model"}]},
        )

        assert response.status_code == 200, response.text
        assert response.json()["note"] is None
    finally:
        await test_session.delete(row)
        await test_session.delete(provider)
        await test_session.commit()
