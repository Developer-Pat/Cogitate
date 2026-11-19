"""The session-override merge — per field, agent first.

A runtime config row overrides the sampling fields it actually SETS. The shape this
replaces was all-or-nothing (`if runtime_config: … elif agent.parameters:`), so a row
that existed for a model override alone dropped the agent's own sampling and one of
the four sites wrote an unguarded NULL as a value. These tests pin the reading, the
per-field precedence, and the guard that keeps a fifth site from hand-rolling it.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.config import Paths
from app.domain.runtime_config.sampling import (
    OVERRIDABLE_SAMPLING_FIELDS,
    merge_sampling,
)

REPO = Path(str(Paths.root))

# The modules that send sampling settings. Each must call `merge_sampling`; none may
# grow its own merge again (the `elif agent.parameters` shape was the defect).
SAMPLING_SITES = {
    "api/v1/chat/context.py": REPO / "backend/app/api/v1/chat/context.py",
    "domain/chat/services.py": REPO / "backend/app/domain/chat/services.py",
}


def _config(**fields):
    """A row-shaped stand-in: only the fields passed are 'set'."""
    base = {"temperature": None, "top_p": None, "max_tokens": None,
            "model_override": None, "system_prompt_override": None}
    base.update(fields)
    return SimpleNamespace(**base)


class TestTheAgentValuesAreTheBase:
    def test_a_config_that_sets_nothing_leaves_the_agent_alone(self):
        """The case that motivated the fix: a row for a MODEL override only."""
        merged = merge_sampling(
            {"temperature": 0.3, "top_p": 0.8},
            _config(model_override="llama3.2:latest"),
        )
        assert merged == {"temperature": 0.3, "top_p": 0.8}

    def test_no_config_at_all_is_the_agent(self):
        assert merge_sampling({"temperature": 0.3}, None) == {"temperature": 0.3}

    def test_an_agent_declaring_nothing_stays_empty(self):
        """Absent means absent: the provider's own default, not an invented number."""
        assert merge_sampling(None, _config()) == {}
        assert merge_sampling({}, None) == {}

    def test_a_null_never_leaks_as_a_value(self):
        merged = merge_sampling({"temperature": 0.3}, _config(temperature=None))
        assert None not in merged.values()


class TestTheOverrideWinsPerField:
    def test_only_the_field_it_sets(self):
        merged = merge_sampling(
            {"temperature": 0.3, "top_p": 0.8}, _config(temperature=0.9)
        )
        assert merged["temperature"] == 0.9, "the override did not win"
        assert merged["top_p"] == 0.8, "the agent's other field was dropped"

    def test_both_fields_overridden(self):
        merged = merge_sampling(
            {"temperature": 0.3, "top_p": 0.8}, _config(temperature=0.0, top_p=1.0)
        )
        assert merged == {"temperature": 0.0, "top_p": 1.0}, (
            "0.0 and 1.0 are VALUES, not absences — a falsy check would drop them"
        )

    def test_the_agent_values_are_not_mutated(self):
        agent_parameters = {"temperature": 0.3}
        merge_sampling(agent_parameters, _config(temperature=0.9))
        assert agent_parameters == {"temperature": 0.3}, (
            "the merge wrote through to the agent's row"
        )

    def test_only_the_two_known_fields_can_be_overridden(self):
        assert OVERRIDABLE_SAMPLING_FIELDS == ("temperature", "top_p")
        merged = merge_sampling(
            {"temperature": 0.3}, SimpleNamespace(temperature=None, top_p=None,
                                                  max_tokens=99, frequency_penalty=1)
        )
        assert "max_tokens" not in merged, "the budget is the resolver's, not a sampling field"
        assert "frequency_penalty" not in merged


class TestTheMergeHasOneHome:
    @pytest.mark.parametrize("name", sorted(SAMPLING_SITES))
    def test_the_site_calls_the_shared_merge(self, name: str):
        assert SAMPLING_SITES[name].is_file(), f"{name} moved — update this guard"
        assert "merge_sampling(" in SAMPLING_SITES[name].read_text(), (
            f"{name} sends sampling settings without `merge_sampling`"
        )

    @pytest.mark.parametrize("name", sorted(SAMPLING_SITES))
    def test_the_site_did_not_grow_its_own_merge_again(self, name: str):
        """The all-or-nothing shape: a config's PRESENCE standing in for a choice.

        Matched as source text because that is what it was — two lines that read as a
        merge and behaved as a switch. Comment lines are excluded (a comment that NAMES
        the old shape is how the removal stays greppable — the same convention the
        one-writer guard uses).
        """
        code = "\n".join(
            line for line in SAMPLING_SITES[name].read_text().splitlines()
            if not line.strip().startswith("#")
        )
        assert not re.search(r"elif\s+agent\.parameters\s*:", code), (
            f"{name} merges by hand again — a runtime config row exists is not a choice"
        )
        assert not re.search(
            r"\[[\"'](temperature|top_p)[\"']\]\s*=\s*runtime_config\.", code
        ), f"{name} assigns a possibly-NULL override straight into the request"
