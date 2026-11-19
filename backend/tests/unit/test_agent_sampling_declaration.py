"""The agent-init arc — an agent's sampling: declared, or nothing at all.

Two properties, both measured against the REAL schemas rather than against a restatement
of them.

**Nothing declared stores nothing.** An omitted `parameters` field used to arrive at the
row as `{"temperature": 0.7, "top_p": 0.9}`, filled in by three separate homes: the
request schema's `default_factory`, the template schema's, and the ORM column's own
`default`. They composed — removing one alone changed nothing on the row, because the
column's default backfilled whatever the schema stopped writing — so all three had to go
together. An agent that declares no sampling now stores NULL; `merge_sampling` leaves the
field absent, the completion request carries no `temperature`, and the provider's own
default applies.

**A declared value is inside its bound.** The bounds are `AgentParameters`' own
(`temperature` 0-2, `top_p` 0-1) — the same treatment the session override already had on
its own model. They are refused BY NAME, through one door, so a request schema and an
internal copy path cannot carry different halves of the same rule.
"""
from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from app.domain.agents.schemas import (
    AgentCreate,
    AgentParameters,
    AgentTemplateCreate,
    AgentUpdate,
    checked_parameters,
)

BOB_MODEL = "inclusionai/ling-3.0-flash"


def _bounds(field_name: str) -> tuple[list[object], list[object]]:
    """The `ge`/`le` the model itself carries for a field — never a literal here."""
    metadata = AgentParameters.model_fields[field_name].metadata
    return (
        [m.ge for m in metadata if hasattr(m, "ge")],
        [m.le for m in metadata if hasattr(m, "le")],
    )


class TestNothingDeclaredStoresNothing:
    """The write path: an omitted field leaves nothing behind for a turn to send."""

    def test_a_create_that_omits_parameters_declares_none(self):
        """The API's create path is how an external agent arrives — it omits the field."""
        created = AgentCreate(name="undeclared", provider="ollama", model="llama3.2")
        assert created.parameters is None
        assert created.model_dump()["parameters"] is None

    def test_a_template_that_omits_parameters_declares_none(self):
        template = AgentTemplateCreate(
            name="t", description="d", provider="ollama", model="m", system_prompt="p"
        )
        assert template.parameters is None

    def test_an_update_omitted_and_an_update_cleared_are_different_things(self):
        """`exclude_unset` is what lets an edit CLEAR a declaration, not repeat it.

        Omitted leaves the row's sampling alone; an explicit `null` clears it. Both are
        deliberate, and neither writes a value nobody chose.
        """
        assert AgentUpdate().model_dump(exclude_unset=True) == {}
        assert AgentUpdate(parameters=None).model_dump(exclude_unset=True) == {
            "parameters": None
        }

    def test_the_copy_path_carries_nothing_as_none_not_as_an_empty_dict(self):
        """One stored shape for "declares nothing" — `{}` and NULL read the same."""
        assert checked_parameters({}) is None
        assert checked_parameters(None) is None
        assert checked_parameters({"temperature": 0.3}) == {"temperature": 0.3}


class TestAValueOutsideItsBoundIsRefusedByName:
    """A sampling value is inside its range, or it does not reach the row."""

    def test_the_bounds_live_on_the_model_and_nowhere_else(self):
        assert _bounds("temperature") == ([0], [2])
        assert _bounds("top_p") == ([0], [1])

    def test_the_edges_are_inside_the_bound(self):
        """A bound that refuses its own edge is a bound that lies about its range."""
        for payload in (
            {"temperature": 0},
            {"temperature": 2},
            {"top_p": 0},
            {"top_p": 1},
            {"temperature": 0.7, "top_p": 0.9},
        ):
            assert AgentCreate(
                name="edge probe", provider="ollama", model=BOB_MODEL, parameters=payload
            ).parameters == payload

    @pytest.mark.parametrize(
        "payload",
        [
            {"temperature": 3.0},
            {"temperature": -1.0},
            {"top_p": 1.5},
            {"top_p": -0.5},
            {"temperature": 0.7, "top_p": 1.5},
        ],
    )
    def test_the_request_schemas_refuse_it_and_name_it(self, payload, caplog):
        offending = [k for k, v in payload.items() if (k == "temperature" and not 0 <= v <= 2)
                     or (k == "top_p" and not 0 <= v <= 1)]
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValidationError, match="out of range"):
                AgentCreate(
                    name="range probe", provider="ollama", model=BOB_MODEL, parameters=payload
                )
            with pytest.raises(ValidationError, match="out of range"):
                AgentUpdate(parameters=payload)
            with pytest.raises(ValidationError, match="out of range"):
                AgentTemplateCreate(
                    name="t", description="d", provider="ollama", model=BOB_MODEL,
                    system_prompt="p", parameters=payload,
                )
        refusals = [
            r.getMessage() for r in caplog.records
            if "REFUSED model parameters" in r.getMessage()
        ]
        assert len(refusals) == 3, f"the refusal was not logged: {refusals}"
        for line in refusals:
            for key in offending:
                assert key in line, f"the log line does not name {key}: {line}"

    def test_the_copy_path_refuses_a_legacy_row_instead_of_copying_it(self, caplog):
        """An out-of-range row is the same class as an unknown key: fix it, don't spread it."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError, match="out of range"):
                checked_parameters({"temperature": 0.7, "top_p": 3.0})
        assert any(
            "REFUSED model parameters" in r.getMessage() and r.levelno == logging.ERROR
            for r in caplog.records
        ), "an out-of-range row was refused at the copy without a logged error naming it"
