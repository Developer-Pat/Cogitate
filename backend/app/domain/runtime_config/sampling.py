"""The sampling settings a turn sends — ONE merge, PER FIELD.

A session's runtime config (`runtime_configs`) overrides the AGENT's own sampling
settings for that session. It overrides the fields it actually SETS and nothing else,
because every column there is nullable and NULL means "no override for this field" —
not "override with nothing".

That reading is the whole point of this module. The shape it replaces was
all-or-nothing:

    params = {}
    if runtime_config:                        # ← the row EXISTS
        params["temperature"] = runtime_config.temperature   # ← possibly None
    elif agent.parameters:                    # ← never reached
        params = agent.parameters.copy()

so a config row that existed for a `model_override` or a `system_prompt_override`
alone silently dropped the agent's own sampling and the provider's default decided in
the dark — and one of the four sites wrote an unguarded `None` into the request. A
session override is supposed to be the narrow thing; a row's presence is not a choice.

The sites that send sampling settings call this function rather than merging by hand
(`tests/unit/test_sampling_merge.py` lists them and fails if one grows its own merge
again). The OUTPUT BUDGET is not here — that is the resolver's
(`services/cognitive_pipeline/output_budget.py`), which reads the same row's
`max_tokens` as writer #4 in its own precedence.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

# The fields a runtime config may override. This is the same pair the agent's own
# `AgentParameters` shape accepts (`domain/agents/schemas.py`, `extra="forbid"`).
OVERRIDABLE_SAMPLING_FIELDS = ("temperature", "top_p")


def merge_sampling(
    agent_parameters: Optional[Mapping[str, Any]],
    runtime_config: Any = None,
) -> Dict[str, Any]:
    """The sampling settings for one call: agent values first, overridden per field.

    Args:
        agent_parameters: the agent row's own `parameters` (sampling settings only).
        runtime_config: the session's `RuntimeConfig` row, or None. Read with
            `getattr` so a caller may pass anything row-shaped.

    Returns:
        A new dict. Fields the config does not set keep the agent's value; a field
        neither declares is simply absent, which leaves the provider's own default —
        the state the system has always had for an agent that declares nothing.
    """
    merged: Dict[str, Any] = dict(agent_parameters or {})

    if runtime_config is None:
        return merged

    for field in OVERRIDABLE_SAMPLING_FIELDS:
        value = getattr(runtime_config, field, None)
        if value is not None:
            merged[field] = value

    return merged
