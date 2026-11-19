"""The POST checks' provider read-outs — the row's OWN model, never a Settings literal.

Phase 4 of the service-capability arc, group C (C1). Two checks read the DEFAULT PROVIDER ROW and
then reported `Settings.default_llm_model` as that row's model — an env knob whose code default is
the literal `"llama3.2"`. So the evidence line could name a model the row does not serve and nobody
can reach (live: the default row serves `deepseek-v4-flash`).

These tests call the checks directly — they ARE the unit; `execute()` would also probe the API
server, the database and the RAG index — and read the model back out of the strings a user sees.
Each assertion is DISCRIMINATING: restoring the Settings read puts `llama3.2` back into the
evidence and fails the file.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import update

from app.domain.providers.config_service import ProviderConfig
from app.domain.tools.builtin.run_post import RunPostTool
from app.infrastructure.database.models import Provider


def test_the_config_object_reports_the_rows_own_model() -> None:
    """`ProviderConfig.default_model` reads `config["default_model"]`.

    A row that carries no model says `""` — it must not borrow one from Settings.
    """
    assert ProviderConfig(
        name="rows", provider_type="openai", config={"default_model": "zz-row-model"}
    ).default_model == "zz-row-model"
    assert ProviderConfig(name="bare", provider_type="openai").default_model == ""
    assert ProviderConfig(
        name="empty", provider_type="openai", config={"default_model": ""}
    ).default_model == ""


async def _make_default_row(test_session, config: dict) -> Provider:
    """A default row of our own.

    The copied test database already holds one (`deepseek`), and `get_default_provider` reads with
    `scalar_one_or_none` — two default rows raise `MultipleResultsFound`, so the others are cleared
    first.
    """
    await test_session.execute(update(Provider).values(is_default=False))
    row = Provider(
        name=f"zz-{uuid.uuid4().hex[:6]}",
        provider_type="openai",
        base_url="http://127.0.0.1:9/v1",
        is_active=True,
        is_default=True,
        config=config,
    )
    test_session.add(row)
    await test_session.commit()
    return row


@pytest.mark.anyio
async def test_check_1_names_the_model_of_the_row_it_read(test_session) -> None:
    """LLM Provider Connectivity (check 1) reports the row's model."""
    await _make_default_row(test_session, {"default_model": "zz-row-model"})

    result = await RunPostTool()._check_llm_connectivity()

    assert result["status"] == "pass"
    assert "zz-row-model" in result["detail"]
    assert "zz-row-model" in result["evidence"]
    assert "llama3.2" not in result["evidence"]      # the retired Settings literal


@pytest.mark.anyio
async def test_check_6_names_the_model_of_the_row_it_read(test_session) -> None:
    """Default Provider Config (check 6) reports the row's model."""
    await _make_default_row(test_session, {"default_model": "zz-row-model"})

    result = await RunPostTool()._check_system_config()

    assert result["status"] == "pass"
    assert "zz-row-model" in result["evidence"]
    assert "llama3.2" not in result["evidence"]


@pytest.mark.anyio
async def test_a_row_with_no_model_makes_check_1_warn_not_borrow_one(test_session) -> None:
    """The row declares no model, so the check reports THAT.

    The retired read made this branch unreachable: a Settings model always answered, so a row
    serving nothing reported `pass` under a name it does not serve.
    """
    await _make_default_row(test_session, {})

    result = await RunPostTool()._check_llm_connectivity()

    assert result["status"] == "warn"
    assert "no model set" in result["detail"]
