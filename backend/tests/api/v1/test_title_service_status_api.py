"""`title-service/status` reports the CAPABILITY's answer, not the global default row.

Why this file exists: the two fields `default_provider_ready` / `default_provider` used to describe
the database's DEFAULT provider row — a row the title only uses when its own capability resolves to
nothing. That made the Local Services page and the Capabilities page able to show two different
answers to one question. Phase 6's G2-F5 repointed them at the `title` capability's resolution,
keeping the KEYS (readers depend on them).

The tests below make the two answers DIFFER on purpose: the capability is aimed at a provider of the
test's own, so a run against the default row cannot pass.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.providers.capabilities import KIND_LLM
from app.infrastructure.database.models import Capability, CapabilityService, Provider

STATUS = "/api/v1/chat/title-service/status"


async def _provider(session: AsyncSession) -> Provider:
    """A provider row of this test's own — deliberately NOT the default row."""
    row = Provider(
        name=f"zz-title-status-{uuid.uuid4().hex[:8]}",
        display_name="Title-status test provider",
        provider_type="openai",
        base_url="https://example.invalid/v1",
        is_active=True,
        priority=97,
        is_default=False,
        config={"default_model": "zz-title-model"},
    )
    session.add(row)
    await session.commit()
    return row


async def _title_capability(
    session: AsyncSession, provider_id: int, *, enabled: bool = True
) -> None:
    """Aim the installation's `title` capability at a provider of this test's own.

    Reused when the copy still carries it (only a session's FIRST test sees the copied rows; every
    later test starts from truncated tables), created when it does not. Two shapes on purpose:
    a REUSED row has its `services` loaded eagerly (clearing a lazy collection would be an async load
    from a sync context — the house's `MissingGreenlet` trap), while a CREATED row gets its candidate
    by `capability_id`, so no collection is touched before it is loaded.
    """
    row = (
        await session.execute(
            select(Capability)
            .options(selectinload(Capability.services))
            .where(Capability.key == "title")
        )
    ).scalar_one_or_none()
    if row is None:
        row = Capability(key="title", label="Title service", kind=KIND_LLM, enabled=enabled)
        session.add(row)
        await session.flush()
        session.add(CapabilityService(capability_id=row.id, ordinal=0, provider_id=provider_id))
    else:
        row.enabled = enabled
        row.services.clear()
        row.services.append(CapabilityService(ordinal=0, provider_id=provider_id))
    await session.commit()


@pytest.mark.anyio
async def test_the_status_reports_the_capability_not_the_global_default_row(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """The field names the provider the CAPABILITY resolved to — not whichever row is default."""
    provider = await _provider(test_session)
    await _title_capability(test_session, provider.id)

    response = await client.get(STATUS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["default_provider_ready"] is True
    assert body["default_provider"]["id"] == provider.id
    assert body["default_provider"]["name"] == provider.name
    # the row's OWN default model, which is what the title would send
    assert body["default_provider"]["model"] == "zz-title-model"
    assert body["default_provider_issues"] == []


@pytest.mark.anyio
async def test_a_disabled_capability_reads_as_not_ready_with_the_reason(
    client: AsyncClient, test_session: AsyncSession
) -> None:
    """The off state reaches this surface too: no answer, and the issue names the capability."""
    provider = await _provider(test_session)
    await _title_capability(test_session, provider.id, enabled=False)

    response = await client.get(STATUS)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["default_provider_ready"] is False
    assert body["default_provider"] is None
    assert len(body["default_provider_issues"]) == 1
    issue = body["default_provider_issues"][0]
    assert "title" in issue and "disabled" in issue, issue
