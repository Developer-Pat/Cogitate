"""A NEW agent's service: what the caller states, else the default provider row.

The provision request used to name both halves itself — ``provider="openrouter"`` and
``model="deepseek/deepseek-v4-flash"`` — so the operator's configured default provider row
was never consulted for a newly provisioned agent (and the two defaults disagreed with the
row they named: the live default row is ``deepseek`` / ``deepseek-v4-flash``). They now
resolve through the rows like every other service choice in the app.

TWO layers are asserted, because they are two halves of one contract:

* the SCHEMA must not fill the fields in — a request model carrying its own default writes
  a service into every row before the resolver ever runs, which is the defect this replaced;
* the RESOLVER must answer from the default row, and must leave a stated service alone.

Removing either half would not fail the other's assertion, which is why both are here.
"""

from sqlalchemy import select

from app.api.v1.agents.provisioning_router import (
    AgentProvisionRequest,
    _resolve_service,
)
from app.infrastructure.database.models import Provider

SCRATCH_NAME = "scratch-default-service"
SCRATCH_MODEL = "scratch-model:latest"


async def _scratch_default_row(session) -> None:
    """Put ONE is_default provider row in this session, whatever the seed did.

    Created rather than assumed: the row's presence is the seed's business, and a test that
    depended on it would be measuring the fixture instead of the resolver. The session
    fixture rolls the scratch row back, so nothing is left behind.
    """
    for row in (await session.execute(select(Provider).where(Provider.is_default))).scalars().all():
        row.is_default = False

    session.add(
        Provider(
            name=SCRATCH_NAME,
            provider_type="ollama",
            is_active=True,
            is_default=True,
            priority=99,
            config={"default_model": SCRATCH_MODEL},
        )
    )
    await session.flush()


def test_an_omitted_service_is_not_filled_in_by_the_schema():
    """The request model supplies no provider and no model of its own."""
    req = AgentProvisionRequest(name="x")
    assert req.provider is None, "a schema default here makes the resolver unreachable"
    assert req.model is None, "a schema default here makes the resolver unreachable"


async def test_an_unstated_service_resolves_from_the_default_provider_row(test_session):
    """With nothing stated, the answer is the row marked is_default."""
    await _scratch_default_row(test_session)

    provider, model = await _resolve_service(test_session, None)

    assert provider == SCRATCH_NAME
    assert model == SCRATCH_MODEL


async def test_a_stated_service_is_taken_at_its_word(test_session):
    """A caller that supplies both halves is never overridden — no row is consulted."""
    provider, model = await _resolve_service(
        test_session,
        AgentProvisionRequest(name="x", provider="groq", model="llama3-8b-8192"),
    )
    assert (provider, model) == ("groq", "llama3-8b-8192")


async def test_a_partially_stated_service_keeps_what_was_stated(test_session):
    """A stated provider survives; only the missing half is resolved."""
    await _scratch_default_row(test_session)

    provider, model = await _resolve_service(
        test_session, AgentProvisionRequest(name="x", provider="groq")
    )

    assert provider == "groq"
    assert model == SCRATCH_MODEL
