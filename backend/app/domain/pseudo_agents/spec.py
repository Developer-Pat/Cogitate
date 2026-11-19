"""Pseudo-agents — the bare-LLM call specs (2026-09-10).

A pseudo-agent is a NAMED, STATELESS, TOOL-LESS LLM call: a system
prompt + an ordered provider chain + the sampling params.

It is deliberately NOT an agent. There is no row in the agents table, no
workspace, no persona file, no skills, no tools, no memory, no chat
session. It exists for deterministic fan-out work, where the LLM lives at
the edges (the house doctrine: deep jobs = deterministic fan-out, workers
= bare LLM). Real agents are the *characters* — personas, skills, kits,
memory; pseudo-agents are the beasts of burden. Keeping the line sharp is
the point.

THE CHAIN is the fallback order. Each step is tried in turn; the first
success wins; every attempt is logged. If every step fails the call
RAISES — the caller owns its own degraded path (the tag-survey nodes have
a mechanical fallback), and nothing degrades silently.

AN EMPTY COMPLETION IS A FAILURE (2026-09-14). A provider that answers with
nothing — the shape a reasoning model produces when its thinking eats a
small max_tokens budget — used to be returned as SUCCESS: the chain reported
a served step while writing nothing, and a fan-out of 173 calls would have
produced blank output throughout, all of it reporting success. Empty text is
now a failed attempt. The chain falls through to the next step, and if every
step answers empty the call RAISES like any other total failure. The escape
hatch is `allow_empty` on the spec, for a prompt where "" is a legitimate
answer — no spec in the catalog needs it today.

PROVENANCE IS RETURNED, not just logged. A run that mixes providers (the
free route for one batch, the local model for the next) must be
auditable afterwards: `served_by` names the step that answered, and
`attempts` carries the full story.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutureTimeout
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# The placeholder key for keyless local servers (the llama at :8080). The
# OpenAI client requires a non-empty string; the server ignores it.
LOCAL_PLACEHOLDER_KEY = "sk-local"


class PseudoAgentError(RuntimeError):
    """Every step of the chain failed. The caller decides what happens next."""


@dataclass(frozen=True)
class ChainStep:
    """One provider attempt in a pseudo-agent's fallback chain.

    THE STEP NAMES A PROVIDER ROW (2026-10-09). `provider_row` is a `providers.name`: the
    row's own `provider_type`, `base_url` and configured model are read when the CALL is
    made, so a chain carries the ROLE it wants ("the paid brain", "the local Bonsai")
    instead of re-stating an endpoint and a model id the row already holds. Anything the
    step states itself wins over the row, so a step may still pin a model or an endpoint
    deliberately.

    Everything is read at CALL time, never at import — the same reason this module resolves
    rather than stores: a chain is a module-level constant, so a value read into it is
    frozen at import and a settings or row change could never take effect.
    """

    # The factory's provider_type (openrouter | deepseek | groq | openai | ...).
    # Empty = take the named row's.
    provider: str = ""
    # The model id. Empty = take the named row's configured default.
    model: str = ""
    base_url: str | None = None
    has_api_key: bool = True
    # The settings attribute to pull the key from (.env), e.g.
    # 'openrouter_api_key'. None for keyless-local steps.
    api_key_setting: str | None = None
    # A literal key to pass (the keyless-local placeholder). Takes
    # precedence over api_key_setting.
    literal_api_key: str | None = None
    # `providers.name` — the row this step means. None = a step that names no row, which
    # must then state the provider_type (and whatever else it needs) itself.
    provider_row: str | None = None


@dataclass(frozen=True)
class PseudoAgentSpec:
    """A named, stateless LLM call: prompt + ordered chain + params."""

    name: str
    system_prompt: str
    chain: tuple[ChainStep, ...]
    temperature: float = 0.0
    max_tokens: int = 4000
    timeout_per_attempt: float = 120.0
    # An empty (or whitespace-only) completion is treated as a FAILED
    # attempt and falls through the chain. Set True only where the empty
    # string is a legitimate answer to the prompt ("return an empty
    # array"): the promise is then "empty is what we asked for", not "we
    # could not tell the difference" — an empty answer is silently
    # indistinguishable from a truncated one.
    allow_empty: bool = False

    def describe(self) -> str:
        """One line for the logs: the chain in order, as the STEPS declare it."""
        return f"{self.name}: " + " → ".join(
            f"{s.provider_row or s.provider}/{s.model or '(row default)'}" for s in self.chain
        )


@dataclass
class PseudoAgentResult:
    """The output plus its provenance."""

    text: str
    served_by: str  # 'provider/model' of the step that answered
    attempts: list[dict[str, Any]] = field(default_factory=list)
    elapsed: float = 0.0
    # the provider's own token counts for the served call — the actual
    # a cost estimate is checked against (the estimator prototype lives
    # at backend/scripts/estimate_workflow_cost.py)
    usage: dict[str, Any] = field(default_factory=dict)

    @property
    def degraded(self) -> bool:
        """True when a fallback (not the first step) answered."""
        return bool(self.attempts) and self.attempts[0].get("ok") is False


def _resolve_api_key(step: ChainStep) -> str | None:
    """The key for a step: literal → the settings attr → None (keyless)."""
    if step.literal_api_key:
        return step.literal_api_key
    if step.api_key_setting:
        from app.core.config import get_settings

        return getattr(get_settings(), step.api_key_setting, None) or None
    return None


def _provider_rows() -> dict[str, dict[str, Any]]:
    """Every ACTIVE provider row by name, read NOW — one connection per chain invocation.

    A chain is a module-level constant, so anything read into it is frozen at import. This
    module holds no ORM session (it runs inside a worker thread), so the read is a plain
    sqlite3 SELECT. A failure returns `{}` rather than raising: a chain that cannot read the
    rows still has whatever its own steps state.
    """
    import json
    import sqlite3

    from app.core.config import Paths, get_settings

    db = Paths.from_settings(get_settings()).shared_db
    try:
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    try:
        conn.row_factory = sqlite3.Row
        fetched = conn.execute(
            "SELECT name, provider_type, base_url, config FROM providers WHERE is_active = 1"
        ).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        conn.close()

    rows: dict[str, dict[str, Any]] = {}
    for r in fetched:
        try:
            cfg = json.loads(r["config"]) if r["config"] else {}
        except (TypeError, ValueError):
            cfg = {}
        rows[r["name"]] = {
            "provider_type": r["provider_type"] or "",
            "base_url": r["base_url"],
            "default_model": (cfg or {}).get("default_model") or "",
        }
    return rows


def _step_service(
    step: ChainStep, rows: dict[str, dict[str, Any]]
) -> tuple[str, str | None, str]:
    """(provider_type, base_url, model) for one step: the row it names, then the step's own.

    THE STEP NAMES A ROW, not a service: anything the step states itself wins, and
    everything else comes from the row — so a chain stops re-stating an endpoint and a model
    id the row already holds.

    A step that names NO row keeps an empty model meaning "the local server's own knob"
    (`llama_model_path`) — the rowless form, which is what a step states when the row's
    configured model is not the one the server actually serves.
    """
    row = (rows.get(step.provider_row) if step.provider_row else None) or {}
    model = step.model or row.get("default_model", "")
    if not model and not step.provider_row:
        from app.core.config import get_settings

        model = getattr(get_settings(), "llama_model_path", "") or ""
    return (
        step.provider or row.get("provider_type", ""),
        step.base_url or row.get("base_url"),
        model,
    )


def _invoke_once(
    spec: PseudoAgentSpec,
    step: ChainStep,
    service: tuple[str, str | None, str],
    prompt: str,
    max_tokens: int | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build the client for one step and make the single call.

    `service` is the RESOLVED (provider_type, base_url, model) for this step — resolved once
    per invocation by the caller, so a fan-out is not re-reading the rows per attempt.

    `max_tokens` overrides the spec's budget for THIS call — the floor retry
    (see `invoke`) is the only caller that passes it.

    Returns (text, usage). The usage is the provider's own token count — the
    only honest basis for a cost estimate, and the actual we check an
    estimate against.
    """
    from app.domain.providers.config_service import ProviderConfig
    from app.domain.providers.llm_factory import get_llm_from_config

    provider_type, base_url, model = service
    cfg = ProviderConfig(
        provider_type=provider_type,
        base_url=base_url,
        name=step.provider_row or provider_type,
        config={"default_model": model},
        has_api_key=step.has_api_key,
    )
    llm = get_llm_from_config(
        cfg,
        temperature=spec.temperature,
        max_tokens=max_tokens if max_tokens is not None else spec.max_tokens,
        api_key=_resolve_api_key(step),
    )
    resp = llm.invoke(prompt)
    text = resp.content if hasattr(resp, "content") else str(resp)

    # THE USAGE CAPTURE (2026-09-10): the provider reports its own token
    # counts; without them a cost estimate can never be checked against
    # reality. langchain normalizes them to usage_metadata.
    um = getattr(resp, "usage_metadata", None) or {}
    usage = {
        "input_tokens": um.get("input_tokens"),
        "output_tokens": um.get("output_tokens"),
        "total_tokens": um.get("total_tokens"),
    }
    return text, usage


def invoke(spec: PseudoAgentSpec, prompt: str) -> PseudoAgentResult:
    """Run the chain: the first step that answers wins.

    Each attempt is bounded by ``spec.timeout_per_attempt``. A timeout
    abandons the attempt (the worker thread is a daemon and is left to die
    on its own — Python cannot kill it) and moves to the next step.

    Raises:
        PseudoAgentError: when every step fails — an exception, a timeout, or
            an empty completion (``allow_empty`` on the spec opts out of the
            last one).
    """
    full_prompt = f"{spec.system_prompt}\n\n{prompt}" if spec.system_prompt else prompt
    attempts: list[dict[str, Any]] = []
    started = time.monotonic()

    # THE ROWS, READ ONCE PER INVOCATION — resolution is per CALL (a chain is a module-level
    # constant, so a value read into it would be frozen at import), but a forty-row fan-out
    # must not open forty connections per chain.
    rows = _provider_rows()

    for idx, step in enumerate(spec.chain, start=1):
        service = _step_service(step, rows)
        provider_type, _, step_model = service
        label = f"{provider_type}/{step_model or '(provider default)'}"
        t0 = time.monotonic()
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(_invoke_once, spec, step, service, full_prompt)
                text, usage = fut.result(timeout=spec.timeout_per_attempt)
            secs = time.monotonic() - t0
            if not spec.allow_empty and not (text or "").strip():
                # THE EMPTY-CONTENT GUARD (2026-09-14): a provider can answer
                # with nothing and still report a healthy call — a reasoning
                # model whose thinking consumed a small max_tokens budget does
                # exactly this. Returning that as SUCCESS is how a fan-out
                # writes 40 blank results and reports 40 successes, so it is
                # recorded as a FAILED attempt and the chain moves on.
                attempts.append({"step": idx, "provider": provider_type, "model": step_model,
                                 "ok": False, "seconds": round(secs, 2), "usage": usage,
                                 "error": "empty content"})
                logger.warning(
                    "[pseudo %s] step %d/%d %s returned EMPTY content (%.1fs, out_tokens=%s) "
                    "— next fallback (set allow_empty=True if an empty answer is legitimate)",
                    spec.name, idx, len(spec.chain), label, secs, usage.get("output_tokens"),
                )

                # THE FLOOR, APPLIED BEHAVIOURALLY (2026-09-26). A thinking
                # driver fed a small budget spends the whole budget thinking and
                # answers with nothing — and the NAME pattern cannot see it:
                # `is_reasoning_model()` matches r1 / -r / deepseek-v4, while
                # the model that actually failed the tag survey
                # (`inclusionai/ling-3.0-flash-sante:free`) matches none. So the
                # empty completion ITSELF is the signal: retry the SAME step ONCE
                # with the floor as its budget before the chain falls through.
                # No name list is needed, and the floor constant keeps its one
                # home in reasoning_support.
                from app.services.cognitive_pipeline.reasoning_support import (
                    REASONING_MAX_TOKENS_FLOOR,
                )

                # FIRE ONLY ON THE SHAPE THAT MEANS "THE BUDGET ATE THE
                # ANSWER" — the provider reports the output hit the ceiling, or
                # reports nothing about usage at all. An empty answer that did
                # NOT consume the budget (a refusal, a broken upstream) falls
                # through exactly as it always did: a fan-out over forty rows
                # must not pay for a second call on every one of them.
                out_tokens = usage.get("output_tokens")
                looks_truncated = out_tokens is None or out_tokens >= spec.max_tokens

                if spec.max_tokens < REASONING_MAX_TOKENS_FLOOR and looks_truncated:
                    t1 = time.monotonic()
                    try:
                        with ThreadPoolExecutor(max_workers=1) as pool:
                            fut = pool.submit(
                                _invoke_once, spec, step, service, full_prompt,
                                REASONING_MAX_TOKENS_FLOOR,
                            )
                            text, usage = fut.result(timeout=spec.timeout_per_attempt)
                        retry_secs = time.monotonic() - t1
                    except _FutureTimeout:
                        retry_secs = time.monotonic() - t1
                        attempts.append({"step": idx, "provider": provider_type, "model": step_model,
                                         "ok": False, "seconds": round(retry_secs, 2),
                                         "retried_with_floor": REASONING_MAX_TOKENS_FLOOR,
                                         "error": "empty, then the floor retry timed out"})
                        logger.warning(
                            "[pseudo %s] step %d/%d %s: the floor retry TIMED OUT (%.0fs) "
                            "— next fallback", spec.name, idx, len(spec.chain), label, retry_secs)
                    except Exception as exc:  # noqa: BLE001 — a failed retry still moves on
                        retry_secs = time.monotonic() - t1
                        attempts.append({"step": idx, "provider": provider_type, "model": step_model,
                                         "ok": False, "seconds": round(retry_secs, 2),
                                         "retried_with_floor": REASONING_MAX_TOKENS_FLOOR,
                                         "error": f"floor retry failed: {str(exc)[:200]}"})
                        logger.warning(
                            "[pseudo %s] step %d/%d %s: the floor retry FAILED (%.1fs): %s "
                            "— next fallback", spec.name, idx, len(spec.chain), label, retry_secs,
                            str(exc)[:200])
                    else:
                        if (text or "").strip():
                            attempts.append({"step": idx, "provider": provider_type,
                                             "model": step_model, "ok": True,
                                             "seconds": round(retry_secs, 2), "usage": usage,
                                             "retried_with_floor": REASONING_MAX_TOKENS_FLOOR})
                            logger.info(
                                "[pseudo %s] step %d/%d %s answered on the FLOOR retry "
                                "(budget %d, %.1fs, %d chars)", spec.name, idx, len(spec.chain),
                                label, REASONING_MAX_TOKENS_FLOOR, retry_secs, len(text))
                            return PseudoAgentResult(
                                text=text, served_by=label, attempts=attempts,
                                elapsed=round(time.monotonic() - started, 2),
                                usage=usage,
                            )
                        attempts.append({"step": idx, "provider": provider_type,
                                         "model": step_model, "ok": False,
                                         "seconds": round(retry_secs, 2), "usage": usage,
                                         "retried_with_floor": REASONING_MAX_TOKENS_FLOOR,
                                         "error": "empty on the floor retry too"})
                        logger.warning(
                            "[pseudo %s] step %d/%d %s is STILL empty at a %d budget "
                            "— next fallback", spec.name, idx, len(spec.chain), label,
                            REASONING_MAX_TOKENS_FLOOR)
                continue
            attempts.append({"step": idx, "provider": provider_type, "model": step_model,
                             "ok": True, "seconds": round(secs, 2), "usage": usage})
            logger.info(
                "[pseudo %s] step %d/%d %s OK (%.1fs, %d chars)",
                spec.name, idx, len(spec.chain), label, secs, len(text or ""),
            )
            return PseudoAgentResult(
                text=text, served_by=label, attempts=attempts,
                elapsed=round(time.monotonic() - started, 2),
                usage=usage,
            )
        except _FutureTimeout:
            secs = time.monotonic() - t0
            attempts.append({"step": idx, "provider": provider_type, "model": step_model,
                             "ok": False, "seconds": round(secs, 2),
                             "error": f"timeout after {spec.timeout_per_attempt}s"})
            logger.warning("[pseudo %s] step %d/%d %s TIMED OUT (%.0fs) — next fallback",
                           spec.name, idx, len(spec.chain), label, secs)
        except Exception as exc:  # noqa: BLE001 — any failure moves the chain on
            secs = time.monotonic() - t0
            attempts.append({"step": idx, "provider": provider_type, "model": step_model,
                             "ok": False, "seconds": round(secs, 2), "error": str(exc)[:300]})
            logger.warning("[pseudo %s] step %d/%d %s FAILED (%.1fs): %s",
                           spec.name, idx, len(spec.chain), label, secs, str(exc)[:200])

    tried = ", ".join(f"{a['provider']}/{a['model']}" for a in attempts)
    logger.error("[pseudo %s] ALL %d chain steps failed (%s)", spec.name, len(attempts), tried)
    raise PseudoAgentError(
        f"pseudo-agent '{spec.name}': all {len(attempts)} chain steps failed — {tried}"
    )
