"""The capability WRITE path — phase 6, group 1 (the DOMAIN half).

Until this landed the sub-area was read-only and the speech shim was its only writer, so nothing
could add, reorder, disable or re-point a capability. These tests pin the contract BEFORE a surface
consumes it:

* the chain is written as a UNIT — the list's position IS the stored ordinal, and a refused request
  leaves the previous chain exactly as it was (never half-applied);
* **"off" and "configures nothing" are DIFFERENT states** — `enabled=False` must NOT fall through to
  the global default row (that is the second answer this arc removes, and the availability ruling's
  refusal needs a real off state), while an empty chain legitimately continues down the ladder;
* a candidate the resolver could never attempt is refused WITH ITS REASON at the write, never stored
  to fail at a turn.

**Every test provisions what it reads.** `auto_clean_tables` truncates all ORM tables after each
test, so only a session's FIRST test still sees the rows the test database was copied with — a test
asserting against those passes alone and fails in a group. So the providers, the default row and the
`tts` capability below are created (or REUSED, by their natural key) by the test that needs them,
and the one test that writes to `tts` snapshots and restores its chain.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.capabilities import (
    KIND_LLM,
    KIND_SPEECH,
    REASON_CAPABILITY,
    REASON_DISABLED,
    REASON_GLOBAL_DEFAULT,
    CandidateSpec,
    UnknownCapabilityError,
    replace_chain,
    resolve,
    resolve_named_service,
)
from app.infrastructure.database.models import Capability, CapabilityService, Provider


async def _capability(
    session: AsyncSession, *, kind: str = KIND_LLM, enabled: bool = True
) -> Capability:
    """A throwaway capability to write against."""
    row = Capability(
        key=f"zz-write-{uuid.uuid4().hex[:8]}",
        label="Write-path test capability",
        kind=kind,
        enabled=enabled,
    )
    session.add(row)
    await session.flush()
    return row


async def _provider(
    session: AsyncSession,
    *,
    base_url: str = "https://example.invalid/v1",
    is_default: bool = False,
    provider_type: str = "openai",
) -> Provider:
    """A provider row this test owns — the suite's tables are empty by the second test onwards."""
    row = Provider(
        name=f"zz-prov-{uuid.uuid4().hex[:8]}",
        display_name="Write-path test provider",
        provider_type=provider_type,
        base_url=base_url,
        is_active=True,
        priority=99,
        is_default=is_default,
        config={"default_model": "zz-provider-model"},
    )
    session.add(row)
    await session.flush()
    return row


async def _speech_capability(
    session: AsyncSession, key: str
) -> tuple[Capability, Optional[list[dict[str, Any]]]]:
    """The installation's speech capability, provisioned when the session has already truncated it.

    Reuse-or-create by the NATURAL key (a bare insert collides with the seeded row when a test IS
    the session's first). The returned snapshot is `None` when this test created the row — restoring
    then means removing it.
    """
    row = (
        await session.execute(select(Capability).where(Capability.key == key))
    ).scalar_one_or_none()
    if row is None:
        row = Capability(key=key, label="Speech engine selection", kind=KIND_SPEECH, enabled=True)
        session.add(row)
        await session.flush()
        return row, None

    await session.refresh(row, ["services"])
    snapshot = [
        {
            "ordinal": service.ordinal,
            "provider_id": service.provider_id,
            "require_location": service.require_location,
            "service_name": service.service_name,
            "model": service.model,
            "thinking": service.thinking,
            "enabled": service.enabled,
        }
        for service in sorted(row.services, key=lambda service: service.ordinal)
    ]
    return row, snapshot


async def _restore_speech(
    session: AsyncSession,
    row: Capability,
    snapshot: Optional[list[dict[str, Any]]],
) -> None:
    """Put the speech capability back exactly as this test found it (and prove the restore)."""
    if snapshot is None:
        await session.delete(row)
        await session.commit()
        return
    row.services.clear()
    for stored in snapshot:
        row.services.append(CapabilityService(**stored))
    await session.commit()
    await session.refresh(row, ["services"])
    assert [
        (service.ordinal, service.service_name, service.provider_id)
        for service in sorted(row.services, key=lambda service: service.ordinal)
    ] == [
        (stored["ordinal"], stored["service_name"], stored["provider_id"]) for stored in snapshot
    ], "the speech capability was not restored to what it held"


@pytest.mark.anyio
async def test_the_lists_position_is_the_stored_chain_and_the_resolver_reads_it_back(
    test_session: AsyncSession,
) -> None:
    """Order in, order stored, order resolved — the chain is what a failure path names."""
    row = await _capability(test_session)
    provider = await _provider(test_session)
    await test_session.commit()
    try:
        await replace_chain(
            test_session,
            row.key,
            [
                CandidateSpec(service_name="zz-named-engine"),
                CandidateSpec(provider_id=provider.id, model="zz-explicit", thinking="mandatory"),
                # No model: the provider row's own default_model answers (and must not be
                # overwritten by an empty string).
                CandidateSpec(provider_id=provider.id),
            ],
        )
        await test_session.commit()

        stored = sorted(row.services, key=lambda service: service.ordinal)
        assert [service.ordinal for service in stored] == [0, 1, 2]
        assert stored[0].service_name == "zz-named-engine"
        assert stored[0].provider_id is None, "a named candidate must not keep a provider row"
        assert stored[1].provider_id == provider.id
        assert stored[1].model == "zz-explicit"
        # `mandatory` is the vocabulary's awkward member — a second list typed out by hand would
        # have dropped it, so accepting it is what proves the write reads THINKING_LEVELS.
        assert stored[1].thinking == "mandatory"
        assert stored[2].model is None, "an omitted model stays omitted on the row"

        resolved = await resolve(test_session, row.key)
        assert resolved.reason == REASON_CAPABILITY
        assert resolved.primary is not None and resolved.primary.service_name == "zz-named-engine"
        assert [c.ordinal for c in resolved.candidates] == [0, 1, 2]
        assert resolved.backups[0].model == "zz-explicit", "the row's own model WINS"
        assert resolved.backups[1].model == "zz-provider-model", (
            "with no model stated, the provider row's default_model answers"
        )
    finally:
        await test_session.delete(row)
        await test_session.delete(provider)
        await test_session.commit()


@pytest.mark.anyio
async def test_a_class_candidate_expands_to_that_class_only(test_session: AsyncSession) -> None:
    """`prefer local` is configuration, not a hardcoded list — and it names no row of its own."""
    row = await _capability(test_session)
    local = await _provider(test_session, base_url="http://127.0.0.1:9/v1")
    cloud = await _provider(test_session, base_url="https://zz-cloud.invalid/v1")
    await test_session.commit()
    try:
        await replace_chain(test_session, row.key, [CandidateSpec(require_location="local")])
        await test_session.commit()

        stored = sorted(row.services, key=lambda service: service.ordinal)
        assert [service.ordinal for service in stored] == [0]
        assert stored[0].require_location == "local"
        assert stored[0].provider_id is None

        resolved = await resolve(test_session, row.key)
        names = [c.provider for c in resolved.candidates]
        assert local.name in names, (
            "the local provider this test created is not in the expanded class — the class "
            "lookup is not reading the live rows"
        )
        assert cloud.name not in names, "a 'local' candidate expanded to a cloud row"
        assert all(c.location == "local" for c in resolved.candidates)
        assert all(c.source == "class" for c in resolved.candidates)
        assert all(c.require_location == "local" for c in resolved.candidates), (
            "the class must survive resolution — a read-out that cannot say WHICH class a candidate "
            "came from cannot be sent back as a write"
        )
    finally:
        await test_session.delete(row)
        await test_session.delete(local)
        await test_session.delete(cloud)
        await test_session.commit()


@pytest.mark.anyio
async def test_a_refused_candidate_leaves_the_stored_chain_untouched(
    test_session: AsyncSession,
) -> None:
    """The whole chain is validated BEFORE anything is written — no half-applied replace."""
    row = await _capability(test_session)
    provider = await _provider(test_session)
    await test_session.commit()
    try:
        await replace_chain(test_session, row.key, [CandidateSpec(service_name="zz-kept")])
        await test_session.commit()

        with pytest.raises(ValueError, match="exactly ONE"):
            await replace_chain(
                test_session,
                row.key,
                [
                    CandidateSpec(service_name="zz-replacement"),
                    # Two forms on one candidate: refused, and it must take the FIRST one with it.
                    CandidateSpec(provider_id=provider.id, service_name="zz-greedy"),
                ],
            )

        await test_session.rollback()
        await test_session.refresh(row, ["services"])
        assert [service.service_name for service in row.services] == ["zz-kept"], (
            "a refused write changed the stored chain"
        )
    finally:
        await test_session.delete(row)
        await test_session.delete(provider)
        await test_session.commit()


@pytest.mark.anyio
async def test_off_is_not_the_same_state_as_configures_nothing(test_session: AsyncSession) -> None:
    """The distinction the availability ruling depends on, pinned in both directions.

    An EMPTY chain means "this capability configures nothing of its own", so the ladder continues to
    the global default row — which is what the seeded `chat` capability relies on. `enabled=False`
    means OFF: nothing resolves at all, and it must never quietly become the default row.
    """
    row = await _capability(test_session)
    default_row = await _provider(test_session, is_default=True)
    await test_session.commit()
    try:
        await replace_chain(test_session, row.key, [])
        await test_session.commit()

        empty = await resolve(test_session, row.key)
        assert empty.reason == REASON_GLOBAL_DEFAULT, (
            "an empty chain is not 'off' — it hands the question to the ladder's next rung"
        )
        assert empty.primary is not None

        await replace_chain(test_session, row.key, [], enabled=False)
        await test_session.commit()

        off = await resolve(test_session, row.key)
        assert off.reason == REASON_DISABLED
        assert off.candidates == ()
        assert off.primary is None
        assert off.reason != REASON_GLOBAL_DEFAULT, (
            "a disabled capability must NOT fall through to the default row — 'off' that still "
            "answers is the second answer this arc removes"
        )

        # ...and an explicit override does not re-arm it: "off" is about the capability, not about
        # which service a caller would prefer.
        overridden = await resolve(test_session, row.key, override="zz-anywhere/zz-model")
        assert overridden.reason == REASON_DISABLED
        assert overridden.candidates == ()
    finally:
        await test_session.delete(row)
        await test_session.delete(default_row)
        await test_session.commit()


@pytest.mark.anyio
async def test_an_unknown_capability_is_refused_as_a_value_error(
    test_session: AsyncSession,
) -> None:
    """Capabilities are seeded vocabulary — a write never invents one.

    `UnknownCapabilityError` is a `ValueError` SUBCLASS on purpose (the speech shim's callers catch
    `ValueError`), and the API route uses the distinction for 404-versus-400.
    """
    with pytest.raises(UnknownCapabilityError) as caught:
        await replace_chain(test_session, "zz-no-such-capability", [])

    assert isinstance(caught.value, ValueError)


@pytest.mark.anyio
async def test_the_named_form_is_checked_against_the_registry_that_owns_those_names(
    test_session: AsyncSession,
) -> None:
    """An engine nothing can build is refused; one the registry serves is written and resolves.

    Both halves matter: a check that refused EVERY name would satisfy the refusal test alone, and
    the point of the check is that a valid engine still goes in. Aimed at `tts` because that is the
    key whose named values have a registry (the check is keyed on the capability), with the row
    provisioned if the session is past its first test and its chain restored afterwards.
    """
    row, snapshot = await _speech_capability(test_session, "tts")
    await test_session.commit()
    try:
        with pytest.raises(ValueError, match="Unknown TTS provider"):
            await replace_chain(test_session, "tts", [CandidateSpec(service_name="zz-not-an-engine")])

        await replace_chain(test_session, "tts", [CandidateSpec(service_name="edge")])
        await test_session.commit()

        name, reason = await resolve_named_service(test_session, "tts")
        assert (name, reason) == ("edge", REASON_CAPABILITY)
    finally:
        await _restore_speech(test_session, row, snapshot)


@pytest.mark.anyio
async def test_a_candidate_the_resolver_could_not_attempt_is_refused_with_its_reason(
    test_session: AsyncSession,
) -> None:
    """Each refused shape names the candidate's position and what was wrong with it."""
    row = await _capability(test_session)
    await test_session.commit()
    try:
        with pytest.raises(ValueError, match="candidate 1: unknown location class 'mars'"):
            await replace_chain(
                test_session,
                row.key,
                [
                    CandidateSpec(service_name="zz-fine"),
                    CandidateSpec(require_location="mars"),
                ],
            )

        with pytest.raises(ValueError, match="candidate 0: unknown thinking 'deepish'"):
            await replace_chain(
                test_session, row.key, [CandidateSpec(service_name="zz-x", thinking="deepish")]
            )

        with pytest.raises(ValueError, match="candidate 0: no provider with id 999999"):
            await replace_chain(test_session, row.key, [CandidateSpec(provider_id=999999)])

        with pytest.raises(ValueError, match="name exactly ONE"):
            await replace_chain(test_session, row.key, [CandidateSpec()])

        await test_session.refresh(row, ["services"])
        assert row.services == [], "a refused write stored a candidate"
    finally:
        await test_session.delete(row)
        await test_session.commit()
