"""The named pseudo-agents — the specs the workflows reference (2026-09-10).

Each spec is data: a prompt, an ordered provider chain, the sampling
params. The chain order is the fallback order, chosen for speed-then-cost:
the free route first, the always-up local model second, the paid brain
last.

The tag-survey fan-out (the Ox Boss pipeline) is the first consumer. Its
worker extraction and its boss consolidation are the two ends of the
chain described in `wiki/atlas/workflows/tag-survey-fanout.md`.
"""

from __future__ import annotations

from app.domain.pseudo_agents.spec import (
    LOCAL_PLACEHOLDER_KEY,
    ChainStep,
    PseudoAgentError,
    PseudoAgentResult,
    PseudoAgentSpec,
    invoke,
)

# THE STEPS NAME PROVIDER ROWS, NOT SERVICES (2026-10-09). `provider_row` is a
# `providers.name`: its provider_type, base_url and configured model are read when the CALL
# is made, so a chain states the ROLE it wants ("the free route", "the paid brain") instead
# of re-stating an endpoint and a model id the row already holds. A model the step names
# anyway is a deliberate pin and wins over the row — as the free route's does, because the
# row's own default is the paid model this step exists to avoid.
#
# The row's values are read at call time, never import time: a chain is a module-level
# constant, so anything read into it would be frozen, and a settings or row change could
# never take effect.

# The local llama.cpp server (the Bonsai) now NAMES ITS PROVIDER ROW too. It used to keep
# its own endpoint here because the `llama` row's configured model is the SHORT name
# (`Bonsai-27B-Q1_0.gguf`) while the server was launched with the full path — but that
# field no longer decides anything: a local server mounts one model and reports it on
# `/v1/models`, so `llm_factory.single_served_model` takes what the server says and logs the
# disagreement. The row supplies the endpoint and the adapter type; the server supplies the
# model. The key is a placeholder the server ignores.

TAG_WORKER_SYSTEM = (
    "You extract YAML frontmatter tags from wiki pages. "
    "Return ONLY a JSON array of objects: [{\"page\": <path>, \"tags\": [<tags>]}]. "
    "Do not add prose. If a page has no tags, return an empty tags array."
)

TAG_BOSS_SYSTEM = (
    "You are the tag-consolidation reviewer for a wiki. Given tag counts, "
    "messy variants, untagged pages and non-namespaced junk, propose a "
    "consolidation. Return ONLY JSON: "
    "{\"renames\": [{\"from\": ..., \"to\": ...}], \"adds\": [...], "
    "\"drops\": [...], \"summary\": ...}. Do not add prose outside the JSON. "
    "The canonical namespaces: type/*, domain/*, feature/*, status/*."
)

# ─────────────────────────────────────────────────────────────────────
# tag-worker — the extraction brain (one call per batch)
# ─────────────────────────────────────────────────────────────────────
TAG_WORKER = PseudoAgentSpec(
    name="tag-worker",
    system_prompt=TAG_WORKER_SYSTEM,
    chain=(
        # 1. the free route — fast when it is up (an availability lottery).
        # THE MODEL IS PINNED BY THE STEP: the openrouter ROW's default is the paid
        # deepseek model, and the whole point of this step is to try the free one first.
        # THE MODEL SWAP (2026-09-10): the old free slug
        # (nvidia/nemotron-3-nano-30b-a3b:free) went paid-only — the
        # probe returned 404 "unavailable for free". Ling is the atlas's
        # original worker candidate and was verified live on 2026-09-10.
        ChainStep(provider_row="openrouter", model="inclusionai/ling-3.0-flash-sante:free",
                  has_api_key=True, api_key_setting="openrouter_api_key"),
        # 2. the local Bonsai — always up, slow, a Q1 quant (quality watch)
        ChainStep(provider_row="llama", has_api_key=False,
                  literal_api_key=LOCAL_PLACEHOLDER_KEY),
        # 3. the boss's brain — the deepseek ROW's own model, so the step names nothing
        ChainStep(provider_row="deepseek", has_api_key=True,
                  api_key_setting="deepseek_api_key"),
    ),
    temperature=0.0,
    max_tokens=4000,
)

# ─────────────────────────────────────────────────────────────────────
# tag-boss — the consolidation reviewer (one call, the whole manifest)
# ─────────────────────────────────────────────────────────────────────
TAG_BOSS = PseudoAgentSpec(
    name="tag-boss",
    system_prompt=TAG_BOSS_SYSTEM,
    chain=(
        # 1. the free route first here too — the prompt is one shot, so a
        #    retry on the next step costs only a wait.
        #    (the dead nemotron free slug swapped for Ling, 2026-09-10)
        ChainStep(provider_row="openrouter", model="inclusionai/ling-3.0-flash-sante:free",
                  has_api_key=True, api_key_setting="openrouter_api_key"),
        # 2. the local Bonsai — the offline path
        ChainStep(provider_row="llama", has_api_key=False,
                  literal_api_key=LOCAL_PLACEHOLDER_KEY),
        # 3. the proven brain — the deepseek row's own model
        ChainStep(provider_row="deepseek", has_api_key=True,
                  api_key_setting="deepseek_api_key"),
    ),
    temperature=0.0,
    max_tokens=4000,
)

CATALOG: dict[str, PseudoAgentSpec] = {
    TAG_WORKER.name: TAG_WORKER,
    TAG_BOSS.name: TAG_BOSS,
}


def get_spec(name: str) -> PseudoAgentSpec:
    """Look up a named spec. Raises KeyError with the available names."""
    try:
        return CATALOG[name]
    except KeyError:
        raise KeyError(
            f"pseudo-agent '{name}' not in the catalog: {sorted(CATALOG)}"
        ) from None


__all__ = [
    "CATALOG", "ChainStep", "LOCAL_PLACEHOLDER_KEY", "PseudoAgentError",
    "PseudoAgentResult", "PseudoAgentSpec", "TAG_BOSS", "TAG_BOSS_SYSTEM",
    "TAG_WORKER", "TAG_WORKER_SYSTEM", "get_spec", "invoke",
]
