"""The model's context window — READ, never chosen (the token-limit arc, Phase E.1).

The window is the one number in the limit model that is **physics rather than
policy** (`local/token-limits/roadmap.md` §2): we do not pick it, we cannot raise
it, and the only thing it is allowed to do to a budget we DID pick is lower it.
Everything else in the arc is a number someone chose; this is a fact about the
driver, so the arc's rules about it are different in three ways:

1. **It is read, not configured.** Two places record it, in this order:
   - `curated_models.context_length` — the CURATED claim (the row a person or a
     package points at). In the live database every one of these rows is NULL
     (`verified = 0`), so this source is usually silent.
   - `provider_model_cache.context_length` — the provider's OWN claim, captured by
     the discovery fetch. It is populated (445 of 464 rows at the time of
     writing) and it is keyed by `(provider, model_id)` — the same pair an agent
     row carries.
2. **Unknown does not clamp.** A model nobody has recorded (`context_length` NULL
   in both places — e.g. a local `codellama:latest`) returns no window at all, the
   assembly keeps its constant ceiling, and the log says `window unknown` once per
   model. **Never a silent guess** (§2.4: the catalogue's own labels are not
   trustworthy — a live model is catalogued `thinking: none` while streaming
   `reasoning_content`).
3. **A stale claim is used and DATED.** The cache row has a TTL (`cached_at` /
   `expires_at`, 168 h). A window changes rarely and NULL is strictly worse than a
   dated number, so an expired row still answers — and the log line carries its
   age, which is what makes the staleness honest rather than hidden.

**What a caller does with it:** `token_budget.input_budget_for(window, reserved_output)`
turns it into the assembly ceiling (a CEILING, never a new basis — E.1's F2 ruling),
and `output_budget.resolve_output_budget(..., window=...)` is where E.2 clamps an
output budget that cannot fit. Neither of those lives here: this module answers one
question — *how big is this driver's window, and where did that number come from?*
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cognitive_pipeline.reasoning_support import (
    REASONING_MAX_TOKENS_FLOOR,
    SOURCE_CURATED,
    SOURCE_PROVIDER_CLAIM,
    ThinkingSignal,
    level_from_claim,
    signal_from_level,
)
from app.infrastructure.database.models import (
    CuratedModel,
    Provider,
    ProviderModelCache,
)

logger = logging.getLogger(__name__)

# Where the number came from — the `source=` on the log line, and the honest
# answer to "should I trust this?".
SOURCE_CURATED = "curated"    # a curated row states it
SOURCE_CACHE = "cache"        # the provider's own discovery said so
SOURCE_NONE = "none"          # nobody has recorded it: unknown


@dataclass(frozen=True)
class ModelWindow:
    """A driver's context window, or the honest statement that it is unknown."""

    value: Optional[int] = None
    source: str = SOURCE_NONE
    provider: str = ""
    model: str = ""
    age_hours: Optional[float] = None
    stale: bool = False

    @property
    def known(self) -> bool:
        """Whether a window was found at all (`False` = do not clamp)."""
        return self.value is not None

    def describe(self) -> str:
        """The greppable one-liner: what the window is and where it came from."""
        if not self.known:
            return (
                f"🪟 MODEL WINDOW model={self.model} provider={self.provider} "
                f"window=unknown source={self.source} — the driver is unrecorded; "
                f"no clamp, the assembly keeps its ceiling"
            )
        stale = ""
        if self.stale:
            age = "" if self.age_hours is None else f" age={self.age_hours:.0f}h"
            stale = f" stale=true{age}"
        return (
            f"🪟 MODEL WINDOW model={self.model} provider={self.provider} "
            f"window={self.value} source={self.source}{stale}"
        )


def pick_model_window(
    curated: Optional[int] = None,
    cache: Optional[int] = None,
) -> tuple[Optional[int], str]:
    """The window from the two recorded claims — the pure precedence rule.

    Curated first (a person or a package stated it deliberately), then the
    provider's own discovery, then nothing. A non-positive number is treated as
    no number at all: a window of 0 is a data error, not a window.
    """
    for value, source in ((curated, SOURCE_CURATED), (cache, SOURCE_CACHE)):
        if value is None:
            continue
        try:
            as_int = int(value)
        except (TypeError, ValueError):
            continue
        if as_int > 0:
            return as_int, source
    return None, SOURCE_NONE


def cache_age_hours(cached_at: Optional[datetime]) -> Optional[float]:
    """How long ago the cache row was captured, in hours (None when unknown)."""
    if cached_at is None:
        return None
    moment = cached_at
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - moment
    return max(0.0, delta.total_seconds() / 3600.0)


def cache_is_stale(expires_at: Optional[datetime]) -> bool:
    """Whether the cached claim has outlived its TTL."""
    if expires_at is None:
        return False
    moment = expires_at
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment < datetime.now(timezone.utc)


# One line per (model, fact) per process: a window that is unknown or stale is a
# standing condition, and repeating it on every turn is the log churn the arc
# warns about. The first turn says it; the shape of the data is the same after.
_LOGGED: set[tuple[str, str, str]] = set()


def _log_once(provider: str, model: str, fact: str, window: ModelWindow) -> None:
    key = (provider, model, fact)
    if key in _LOGGED:
        return
    _LOGGED.add(key)
    if fact == "unknown":
        logger.warning(
            "🪟 MODEL WINDOW model=%s provider=%s window=unknown "
            "(window_unknown) — no window is recorded for this driver, so "
            "nothing is clamped and the assembly keeps its ceiling. Phase E.4 "
            "is what fills the row.",
            model, provider,
        )
    else:
        logger.warning(
            "🪟 MODEL WINDOW model=%s provider=%s window=%s source=%s "
            "stale=true age=%sh — the provider's last claim is older than the "
            "cache TTL; it is used (NULL would be worse) and dated here.",
            model, provider, window.value, window.source,
            "?" if window.age_hours is None else f"{window.age_hours:.0f}",
        )


def forget_logged_windows() -> None:
    """Clear the once-per-model log registry (tests, and a fresh process)."""
    _LOGGED.clear()


def needed_window_tokens(
    prompt_floor: Any = None,
    output_budget: Any = None,
) -> Optional[int]:
    """The window an agent NEEDS: its prompt floor plus its declared output budget.

    ``None`` when neither is declared — nothing declared is not a requirement, and
    a requirement nobody stated cannot be missed. Both numbers are policy (the
    package's ``min_context``, the agent's declared ``max_tokens``/``llm_spec``
    ``max_output``), which is why the sum is a NEED and the window is the fact it
    is measured against.
    """
    total = 0
    seen = False
    for value in (prompt_floor, output_budget):
        if value is None:
            continue
        try:
            total += int(value)
        except (TypeError, ValueError):
            continue
        seen = True
    return total if seen else None


def pairing_advice(
    declared: Optional[int],
    thinking: Optional[str],
    cap: Optional[int] = None,
    *,
    who: str = "This agent",
) -> List[str]:
    """What will really happen when this driver meets this contract — the sentences.

    G4 and G5's residue, said where the PAIRING is decided instead of being discovered
    later as a cut-off answer or a surprise on the profile page. Three numbers are
    involved, and this is the one place they are compared:

    - **the declaration** — what the agent's contract states (`llm_spec.max_output`);
    - **the floor** — a driver that reasons is floored at ``REASONING_MAX_TOKENS_FLOOR``
      whatever was declared, so the declared number is not the number that goes out;
      ``mandatory`` is stronger still: there is no effort to lower, only a driver to
      replace;
    - **the provider's grant** — `top_provider.max_completion_tokens`, what the provider
      will actually give. A request above it is cut there, and the cut is the provider's
      rather than the declaration's.

    REPORTED, never a filter and never enforced: the provider applies its own cap, and
    the floor is the resolver's business. An empty list is the honest answer when there
    is nothing to say — a driver that does not think, a declaration the floor does not
    touch, a grant that covers what will be asked for. An unknown need is not a finding
    (the rule `window_fit_warning` follows).
    """
    level = str(thinking or "none").strip().lower()
    thinks = level in ("low", "medium", "high", "mandatory")

    sentences: List[str] = []
    # The number that will actually be asked for, which is what a grant has to cover.
    asked = int(declared) if declared else None
    if thinks and (asked is None or asked < REASONING_MAX_TOKENS_FLOOR):
        asked = REASONING_MAX_TOKENS_FLOOR

    # The floor sentence fires only when the floor CHANGES the number. A declaration at
    # or above it is the number that goes out, so there is nothing to warn about — the
    # rule the window-fit warning follows, and the bug this test caught.
    below_floor = thinks and (declared is None or int(declared) < REASONING_MAX_TOKENS_FLOOR)
    if below_floor and level == "mandatory":
        sentences.append(
            f"{who}: the driver cannot be told not to think — every call's budget is "
            f"floored at {REASONING_MAX_TOKENS_FLOOR}, so the turn runs longer than the "
            f"declaration, and the only lever is another driver"
        )
    elif below_floor:
        sentences.append(
            f"{who}: the driver reasons, so the budget is floored at "
            f"{REASONING_MAX_TOKENS_FLOOR} — the declared number is not the number that "
            f"goes out"
        )

    if cap and asked and asked > int(cap):
        sentences.append(
            f"{who}: the provider grants at most {int(cap)} answer tokens and {asked} "
            f"will be asked for — the answer is cut there (finish_reason=length)"
        )
    return sentences


def window_fit_warning(
    window: Optional[int],
    needed_tokens: Optional[int] = None,
    *,
    who: str = "This agent",
) -> Optional[str]:
    """One sentence for a driver that cannot hold what an agent needs — or ``None``.

    D9's ruling in words: a window too small for the type's budget is **allowed**
    (never a refusal), it warns where the mismatch is knowable (match / provision /
    adopt time), and the runtime **clamps** with a reason (`window_clamp`). Two
    states produce a sentence:

    * **the window is UNKNOWN** — nobody recorded it, so nothing is clamped and
      nobody can claim it fits. (The matcher's floor check no longer has to cover this
      case: a stated `min_context` does not offer such a row at all. The sentence still
      matters for a match with NO floor, where they are offered and this is the only
      thing that says so.);
    * **the window is known and smaller than `needed_tokens`** — a driver to
      replace, said out loud instead of discovered as a cut-off answer.

    A known window big enough, or no `needed_tokens` to compare against, says
    nothing at all: an unknown need is not a finding.
    """
    if window is None:
        return (
            f"{who}: the driver's context window is not recorded (window unknown) — "
            f"nothing is clamped until it is, and a turn on it says the same"
        )
    if not needed_tokens:
        return None
    if int(window) >= int(needed_tokens):
        return None
    return (
        f"{who}: the driver holds {int(window)} tokens and this needs "
        f"{int(needed_tokens)} (the prompt floor plus the declared output budget) — "
        f"allowed, and the runtime will clamp the budget to fit (reason=window_clamp)"
    )


def log_window_fit(
    provider: Optional[str],
    model: Optional[str],
    window: Optional[int],
    needed_tokens: Optional[int] = None,
    *,
    who: str = "This agent",
) -> Optional[str]:
    """Log the fit sentence once per (driver, fact) and return it — the instrument.

    A window that cannot hold an agent's need is a standing condition, not a
    per-call event: the first time says it, and a REPEAT says it again only when
    the numbers move.
    """
    sentence = window_fit_warning(window, needed_tokens, who=who)
    if sentence is None:
        return None
    fact = "unknown" if window is None else f"too-small:{int(window)}:{int(needed_tokens or 0)}"
    key = (str(provider or ""), str(model or ""), fact)
    if key not in _LOGGED:
        _LOGGED.add(key)
        logger.warning("⚠️ WINDOW FIT model=%s provider=%s — %s", model, provider, sentence)
    return sentence


async def resolve_model_window(
    db: AsyncSession,
    provider_name: Optional[str],
    model_id: Optional[str],
) -> ModelWindow:
    """Read the window for one driver: curated row, else cache row, else unknown.

    Read-only and cheap (two indexed lookups). Never raises for missing data: a
    provider or model the database does not know is simply an unknown window.
    """
    provider = str(provider_name or "")
    model = str(model_id or "")
    if not provider or not model:
        return ModelWindow(value=None, source=SOURCE_NONE, provider=provider, model=model)

    provider_row = (
        await db.execute(
            select(Provider.id).where(Provider.name == provider).limit(1)
        )
    ).scalar_one_or_none()
    if provider_row is None:
        window = ModelWindow(value=None, source=SOURCE_NONE, provider=provider, model=model)
        _log_once(provider, model, "unknown", window)
        return window

    curated = (
        await db.execute(
            select(CuratedModel.context_length)
            .where(
                CuratedModel.provider_id == provider_row,
                CuratedModel.model_id == model,
                CuratedModel.is_active.is_(True),
                CuratedModel.context_length.isnot(None),
            )
            .order_by(CuratedModel.id)
            .limit(1)
        )
    ).scalar_one_or_none()

    cached_length: Optional[int] = None
    cached_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    cache_row = (
        await db.execute(
            select(ProviderModelCache)
            .where(
                ProviderModelCache.provider_id == provider_row,
                ProviderModelCache.model_id == model,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if cache_row is not None:
        cached_length = cache_row.context_length
        cached_at = cache_row.cached_at
        expires_at = cache_row.expires_at

    value, source = pick_model_window(curated=curated, cache=cached_length)
    window = ModelWindow(
        value=value,
        source=source,
        provider=provider,
        model=model,
        age_hours=cache_age_hours(cached_at) if source == SOURCE_CACHE else None,
        stale=cache_is_stale(expires_at) if source == SOURCE_CACHE else False,
    )

    if not window.known:
        _log_once(provider, model, "unknown", window)
    elif window.stale:
        _log_once(provider, model, f"stale:{window.value}", window)
    else:
        # A KNOWN window prints once per (driver, value) — a number that changes
        # prints again, and a steady one does not fill the log every turn.
        key = (provider, model, f"window={window.value}")
        if key not in _LOGGED:
            _LOGGED.add(key)
            logger.info("%s", window.describe())
    return window


def log_thinking_signal(provider: str, model: str, signal: ThinkingSignal) -> None:
    """Say the driver's thinking fact once per (driver, source) — the instrument (F.3).

    A driver that thinks is a standing condition, and the SOURCE is the part that
    matters: it is the whole difference between "we hand-labelled this" and "the
    provider says so". Logged once per (driver, source), like the window.
    """
    fact = f"thinking:{signal.source}:{signal.thinking}:{signal.mandatory}"
    key = (str(provider or ""), str(model or ""), fact)
    if key in _LOGGED:
        return
    _LOGGED.add(key)
    if not signal.thinking:
        logger.info(
            "🧠 MODEL THINKING model=%s provider=%s thinking=false source=%s — no "
            "thinking is recorded for this driver; the name pattern is the remaining "
            "fallback (F.3).",
            model, provider, signal.source,
        )
        return
    logger.info(
        "🧠 MODEL THINKING model=%s provider=%s thinking=true mandatory=%s source=%s — "
        "the reasoning floor applies from here (F.3).",
        model, provider, str(signal.mandatory).lower(), signal.source,
    )


def provider_reasoning_claim(raw_data: Any) -> tuple[bool, bool, Optional[str]]:
    """What the provider's own model payload says about thinking (F.3).

    Returns ``(thinks_by_default, mandatory, default_effort)``. The same field
    `curated_models_service.provider_claim_from_raw` reports in the provider's words on
    the verification line; here it is PARSED, because F.3 makes it load-bearing — a
    claim of `mandatory: true` cannot be turned off, whatever our own row says, and our
    row is the thing that rotted (a live driver catalogued `thinking: none` while the
    provider publishes `default_enabled: true`).
    """
    if not isinstance(raw_data, dict):
        return False, False, None
    payload = raw_data.get("_raw")
    if not isinstance(payload, dict):
        payload = raw_data
    reasoning = payload.get("reasoning")
    if not isinstance(reasoning, dict):
        return False, False, None
    mandatory = reasoning.get("mandatory") is True
    by_default = reasoning.get("default_enabled") is True or mandatory
    effort = reasoning.get("default_effort")
    return by_default, mandatory, str(effort) if effort is not None else None


async def resolve_model_thinking(
    db: AsyncSession,
    provider_name: Optional[str],
    model_id: Optional[str],
) -> ThinkingSignal:
    """Read one driver's thinking signal: the provider's CLAIM, else our row.

    The claim comes first, and that order is the finding (F.3): a curated row is OUR
    label — set through `POST`/`PUT /curated-models`, or adopted from the claim by
    `verify-window` — while the claim is the provider's own statement about the driver
    it serves. When the two disagree the claim
    wins, which is what turns "catalogued `thinking: none` while streaming reasoning"
    from a surprise into a floor.

    Read-only like the window reader, with the same honest unknown: a driver nobody has
    recorded returns an empty signal, and the resolver's declaration + name-pattern
    fallbacks speak instead.
    """
    provider = str(provider_name or "")
    model = str(model_id or "")
    if not provider or not model:
        return ThinkingSignal()

    provider_row = (
        await db.execute(select(Provider.id).where(Provider.name == provider).limit(1))
    ).scalar_one_or_none()
    if provider_row is None:
        return ThinkingSignal()

    claim_raw = (
        await db.execute(
            select(ProviderModelCache.raw_data)
            .where(
                ProviderModelCache.provider_id == provider_row,
                ProviderModelCache.model_id == model,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    by_default, mandatory, effort = provider_reasoning_claim(claim_raw)
    claimed = signal_from_level(
        level_from_claim(by_default, mandatory, effort), SOURCE_PROVIDER_CLAIM,
    )
    if claimed is not None:
        log_thinking_signal(provider, model, claimed)
        return claimed

    curated = (
        await db.execute(
            select(CuratedModel.thinking)
            .where(
                CuratedModel.provider_id == provider_row,
                CuratedModel.model_id == model,
                CuratedModel.is_active.is_(True),
            )
            .order_by(CuratedModel.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    signal = signal_from_level(curated, SOURCE_CURATED) or ThinkingSignal()
    log_thinking_signal(provider, model, signal)
    return signal
