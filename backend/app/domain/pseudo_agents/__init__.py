"""Pseudo-agents — the bare-LLM call specs.

A pseudo-agent is a named, stateless, tool-less LLM call with an ordered
provider chain. It is not an agent: no table row, no workspace, no
persona, no skills, no tools, no memory. See `spec.py` for the doctrine.

    from app.domain.pseudo_agents import get_spec, invoke

    result = invoke(get_spec("tag-worker"), prompt)
    result.text          # the answer
    result.served_by     # 'deepseek/deepseek-v4-flash' — which step answered
    result.attempts      # the full chain story
"""

from app.domain.pseudo_agents.catalog import (
    CATALOG,
    TAG_BOSS,
    TAG_BOSS_SYSTEM,
    TAG_WORKER,
    TAG_WORKER_SYSTEM,
    get_spec,
)
from app.domain.pseudo_agents.spec import (
    LOCAL_PLACEHOLDER_KEY,
    ChainStep,
    PseudoAgentError,
    PseudoAgentResult,
    PseudoAgentSpec,
    invoke,
)

__all__ = [
    "CATALOG", "ChainStep", "LOCAL_PLACEHOLDER_KEY", "PseudoAgentError",
    "PseudoAgentResult", "PseudoAgentSpec", "TAG_BOSS", "TAG_BOSS_SYSTEM",
    "TAG_WORKER", "TAG_WORKER_SYSTEM", "get_spec", "invoke",
]
