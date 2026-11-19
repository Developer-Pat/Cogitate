"""The model's window — read from where it is recorded, or honestly unknown (E.1).

The window is the arc's one non-policy number (roadmap §2). These tests pin the
three states a caller can be in — curated, cached (the provider's own discovery),
unknown — plus the precedence between them and the TTL that makes a cached claim
dated rather than timeless.

The live database is why the precedence is worth pinning: **every curated row is
NULL**, so in practice the answer comes from `provider_model_cache`, and the two
must not be confused when a curated row finally states a number.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.providers.model_window import (
    SOURCE_CACHE,
    SOURCE_CURATED,
    SOURCE_NONE,
    ModelWindow,
    forget_logged_windows,
    log_window_fit,
    needed_window_tokens,
    pick_model_window,
    provider_reasoning_claim,
    resolve_model_thinking,
    resolve_model_window,
    window_fit_warning,
)
from app.infrastructure.database.models import CuratedModel, ProviderModelCache
from app.infrastructure.database.models import (
    CuratedModel,
    Provider,
    ProviderModelCache,
)


@pytest.fixture(autouse=True)
def _clean_log_registry():
    """The once-per-model log registry is process state — isolate the tests."""
    forget_logged_windows()
    yield
    forget_logged_windows()


# ── the precedence (pure) ─────────────────────────────────────────────────────

def test_the_curated_claim_wins_over_the_discovered_one():
    assert pick_model_window(curated=262144, cache=8192) == (262144, SOURCE_CURATED)


def test_the_cached_claim_answers_when_the_curated_row_is_silent():
    assert pick_model_window(curated=None, cache=8192) == (8192, SOURCE_CACHE)


def test_nothing_recorded_is_unknown_not_zero():
    assert pick_model_window() == (None, SOURCE_NONE)
    assert pick_model_window(curated=None, cache=None) == (None, SOURCE_NONE)


def test_a_non_positive_number_is_no_number():
    """A window of 0 (or junk) is a data error, not a window to clamp against."""
    assert pick_model_window(curated=0, cache=8192) == (8192, SOURCE_CACHE)
    assert pick_model_window(curated=None, cache=0) == (None, SOURCE_NONE)
    # Wrong type on purpose: a column can hand back something that is not a number.
    assert pick_model_window(curated=None, cache="nonsense") == (None, SOURCE_NONE)  # type: ignore[arg-type]


def test_a_window_describes_itself_for_the_log():
    known = ModelWindow(value=262144, source=SOURCE_CACHE, provider="openrouter", model="m")
    unknown = ModelWindow(provider="openrouter", model="m")

    assert known.known and not unknown.known
    assert "window=262144" in known.describe() and "source=cache" in known.describe()
    assert "window=unknown" in unknown.describe()


# ── the resolver (the two lookups) ────────────────────────────────────────────

async def _provider(db, name: str) -> Provider:
    provider = Provider(name=name, display_name=name, provider_type=name, is_active=True)
    db.add(provider)
    await db.flush()
    return provider


async def _cache_row(db, provider_id: int, model_id: str, length, expires_at=None):
    row = ProviderModelCache(
        provider_id=provider_id,
        model_id=model_id,
        name=model_id,
        context_length=length,
        cached_at=datetime.now(timezone.utc) - timedelta(hours=1),
        expires_at=expires_at,
    )
    db.add(row)
    await db.flush()
    return row


async def test_the_providers_own_number_is_used_when_the_curated_row_is_null(test_session):
    """The live case: the curated row says nothing, the discovery knows."""
    provider = await _provider(test_session, "window-test-a")
    await _cache_row(test_session, provider.id, "inclusionai/ling-3.0-flash", 262144)
    test_session.add(
        CuratedModel(
            provider_id=provider.id,
            model_id="inclusionai/ling-3.0-flash",
            model_name="Ling 3.0 Flash",
            context_length=None,
            is_active=True,
        )
    )
    await test_session.flush()

    window = await resolve_model_window(
        test_session, "window-test-a", "inclusionai/ling-3.0-flash"
    )

    assert window.value == 262144
    assert window.source == SOURCE_CACHE
    assert window.known


async def test_a_curated_number_overrides_the_discovered_one(test_session):
    provider = await _provider(test_session, "window-test-b")
    await _cache_row(test_session, provider.id, "m", 8192)
    test_session.add(
        CuratedModel(
            provider_id=provider.id,
            model_id="m",
            model_name="M",
            context_length=32768,
            is_active=True,
        )
    )
    await test_session.flush()

    window = await resolve_model_window(test_session, "window-test-b", "m")

    assert window.value == 32768
    assert window.source == SOURCE_CURATED


async def test_an_unrecorded_driver_is_unknown(test_session):
    provider = await _provider(test_session, "window-test-c")
    await _cache_row(test_session, provider.id, "recorded", 8192)

    window = await resolve_model_window(test_session, "window-test-c", "codellama:latest")

    assert not window.known
    assert window.value is None
    assert window.source == SOURCE_NONE


async def test_an_unknown_provider_is_unknown(test_session):
    window = await resolve_model_window(test_session, "nowhere", "m")

    assert not window.known


async def test_a_missing_model_id_is_unknown(test_session):
    window = await resolve_model_window(test_session, "window-test-c", None)

    assert not window.known


async def test_an_expired_claim_is_used_and_dated(test_session):
    """A window changes rarely; NULL is worse than a dated number (E.1's F1)."""
    provider = await _provider(test_session, "window-test-d")
    await _cache_row(
        test_session,
        provider.id,
        "m",
        8192,
        expires_at=datetime.now(timezone.utc) - timedelta(days=8),
    )

    window = await resolve_model_window(test_session, "window-test-d", "m")

    assert window.value == 8192          # still answers
    assert window.stale is True          # and says it is stale
    assert window.age_hours is not None


async def test_a_fresh_claim_is_not_marked_stale(test_session):
    provider = await _provider(test_session, "window-test-e")
    await _cache_row(
        test_session,
        provider.id,
        "m",
        8192,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    window = await resolve_model_window(test_session, "window-test-e", "m")

    assert window.value == 8192
    assert window.stale is False


# ── the fit warning (E.3, D9) ─────────────────────────────────────────────────

def test_the_need_is_the_prompt_floor_plus_the_declared_budget():
    assert needed_window_tokens(prompt_floor=4096, output_budget=8192) == 12288
    assert needed_window_tokens(prompt_floor=4096) == 4096
    assert needed_window_tokens(output_budget=8192) == 8192


def test_no_declaration_is_no_requirement():
    """A requirement nobody stated cannot be missed."""
    assert needed_window_tokens() is None
    assert needed_window_tokens(prompt_floor=None, output_budget=None) is None


def test_a_junk_requirement_is_ignored_not_summed():
    assert needed_window_tokens(prompt_floor="nonsense", output_budget=8192) == 8192


def test_a_window_that_fits_says_nothing():
    """A driver big enough is not a finding — no note, no log line."""
    assert window_fit_warning(262144, 12288) is None
    assert window_fit_warning(12288, 12288) is None      # exactly enough fits


def test_a_window_too_small_says_so_and_names_both_numbers():
    sentence = window_fit_warning(8192, 12288, who="Agent 'Bob'")

    assert sentence is not None
    assert "Agent 'Bob'" in sentence
    assert "8192" in sentence and "12288" in sentence
    assert "window_clamp" in sentence       # what will happen at runtime
    assert "allowed" in sentence            # D9: never a refusal


def test_an_unknown_window_is_said_not_guessed():
    sentence = window_fit_warning(None, 12288)

    assert sentence is not None
    assert "window unknown" in sentence
    assert "nothing is clamped" in sentence


def test_an_unknown_need_is_not_a_finding():
    """A known window with nothing declared to compare it against says nothing."""
    assert window_fit_warning(8192, None) is None


def test_the_fit_line_is_logged_once_per_fact(caplog):
    """A standing condition, not a per-call event: the first time says it."""
    import logging

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.model_window"):
        first = log_window_fit("groq", "llama-3.1-8b-instant", 8192, 12288, who="Agent 'A'")
        log_window_fit("groq", "llama-3.1-8b-instant", 8192, 12288, who="Agent 'A'")

    assert first is not None
    assert caplog.text.count("WINDOW FIT") == 1


def test_the_fit_line_speaks_again_when_the_numbers_move(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.model_window"):
        log_window_fit("groq", "llama-3.1-8b-instant", 8192, 12288)
        log_window_fit("groq", "llama-3.1-8b-instant", 8192, 20000)

    assert caplog.text.count("WINDOW FIT") == 2


LING_RAW = {
    "_raw": {
        "id": "inclusionai/ling-3.0-flash",
        "reasoning": {"mandatory": False, "default_enabled": True},
    }
}
MANDATORY_RAW = {
    "_raw": {
        "id": "stealth/space-bunny-alpha",
        "reasoning": {
            "mandatory": True,
            "supported_efforts": ["max", "xhigh", "high", "medium", "low"],
            "default_effort": "max",
        },
    }
}


class TestTheThinkingClaim:
    """F.3 — the provider's own reasoning payload, parsed rather than trusted."""

    def test_a_default_enabled_claim_says_it_thinks(self):
        assert provider_reasoning_claim(LING_RAW) == (True, False, None)

    def test_a_mandatory_claim_carries_its_effort(self):
        assert provider_reasoning_claim(MANDATORY_RAW) == (True, True, "max")

    def test_a_payload_without_reasoning_says_nothing(self):
        assert provider_reasoning_claim({"_raw": {"id": "m"}}) == (False, False, None)
        assert provider_reasoning_claim(None) == (False, False, None)
        assert provider_reasoning_claim({"reasoning": "yes"}) == (False, False, None)


async def _thinking_claim(db, provider_id: int, model_id: str, raw):
    row = ProviderModelCache(
        provider_id=provider_id, model_id=model_id, name=model_id, raw_data=raw,
    )
    db.add(row)
    await db.flush()
    return row


async def test_the_providers_claim_beats_a_curated_row_that_says_none(test_session):
    """THE LIVE CASE: our row says `none`, the provider says it thinks (F.3)."""
    provider = await _provider(test_session, "thinking-a")
    test_session.add(
        CuratedModel(
            provider_id=provider.id, model_id="inclusionai/ling-3.0-flash",
            model_name="Ling", thinking="none", verified=True, is_active=True,
        )
    )
    await _thinking_claim(test_session, provider.id, "inclusionai/ling-3.0-flash", LING_RAW)

    signal = await resolve_model_thinking(
        test_session, "thinking-a", "inclusionai/ling-3.0-flash"
    )

    assert signal.thinking and not signal.mandatory
    assert signal.source == "provider_claim"


async def test_a_mandatory_claim_is_reported_as_mandatory(test_session):
    provider = await _provider(test_session, "thinking-b")
    await _thinking_claim(
        test_session, provider.id, "stealth/space-bunny-alpha", MANDATORY_RAW
    )

    signal = await resolve_model_thinking(
        test_session, "thinking-b", "stealth/space-bunny-alpha"
    )

    assert signal.thinking and signal.mandatory


async def test_our_label_answers_when_the_claim_is_silent(test_session):
    provider = await _provider(test_session, "thinking-c")
    test_session.add(
        CuratedModel(
            provider_id=provider.id, model_id="m-local", model_name="m",
            thinking="high", verified=True, is_active=True,
        )
    )
    await _thinking_claim(test_session, provider.id, "m-local", {"_raw": {"id": "m-local"}})

    signal = await resolve_model_thinking(test_session, "thinking-c", "m-local")

    assert signal.thinking and signal.source == "curated"


async def test_an_unrecorded_driver_is_an_empty_signal(test_session):
    signal = await resolve_model_thinking(test_session, "thinking-d", "nobody")
    assert not signal.thinking
    assert not signal.mandatory
