"""The window verification — the provider's own number, adopted and dated (E.4).

A curated row's `context_length` is OUR statement; `provider_model_cache` holds the
PROVIDER's claim, captured by the app's discovery fetch. E.4's rule, and what these
tests pin:

* the provider's number is the FACT — the row adopts it, and a disagreement is
  reported (`mismatch`) rather than quietly overwritten;
* `verified` means the row agrees with a claim we can STAND BEHIND, so a stale claim
  can fill a row that had no number while `verified` stays False;
* a verification that could not ask the provider SAYS so instead of presenting a
  dated claim as a fresh one;
* the provider's thinking signal is reported in the provider's own words — mapping it
  to none/low/medium/high is F.3's ruling, because that level keys the reasoning floor.

Measured against the live payload (2026-09-23): the working driver's own entry carries
`context_length: 262144`, `reasoning: {mandatory: false, default_enabled: true}` and
`top_provider.max_completion_tokens: 32768` — the row says `thinking: none`, which is
the mislabelling this phase can now SEE.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.providers.curated_models_service import (
    curated_model_service,
    provider_claim_from_raw,
    resolve_verification,
)
from app.infrastructure.database.models import (
    CuratedModel,
    Provider,
    ProviderModelCache,
)

RAW = {
    "_raw": {
        "id": "inclusionai/ling-3.0-flash",
        "context_length": 262144,
        "reasoning": {"mandatory": False, "default_enabled": True},
        "top_provider": {"context_length": 262144, "max_completion_tokens": 32768},
    }
}


# ── the provider's own claims, read from its payload ──────────────────────────

def test_the_reasoning_signal_is_reported_in_the_providers_own_words():
    signal, cap = provider_claim_from_raw(RAW)

    assert signal == "reasoning: default_enabled=True, mandatory=False"
    assert cap == 32768


def test_a_payload_with_no_reasoning_says_nothing():
    signal, cap = provider_claim_from_raw({"_raw": {"id": "m"}})

    assert signal is None and cap is None


def test_junk_payloads_do_not_crash_the_read():
    assert provider_claim_from_raw(None) == (None, None)
    assert provider_claim_from_raw("nonsense") == (None, None)
    assert provider_claim_from_raw({"_raw": {"reasoning": "yes"}})[0] == "reasoning: yes"
    assert provider_claim_from_raw({"_raw": {"top_provider": {"max_completion_tokens": 0}}})[1] is None


# ── the decision ──────────────────────────────────────────────────────────────

def test_a_row_with_no_number_adopts_the_providers():
    window, verified, mismatch, note = resolve_verification(None, 262144, fresh=True)

    assert (window, verified, mismatch) == (262144, True, False)
    assert "adopted" in note


def test_agreement_is_confirmed():
    window, verified, mismatch, _ = resolve_verification(262144, 262144, fresh=True)

    assert (window, verified, mismatch) == (262144, True, False)


def test_a_disagreement_adopts_the_provider_and_reports_it():
    window, verified, mismatch, note = resolve_verification(8192, 262144, fresh=True)

    assert (window, verified, mismatch) == (262144, True, True)
    assert "8192" in note and "262144" in note


def test_a_stale_claim_fills_a_row_but_verifies_NOTHING():
    """The difference between "we recorded a number" and "we checked it"."""
    window, verified, mismatch, note = resolve_verification(None, 262144, fresh=False)

    assert (window, verified) == (262144, False)     # recorded, not verified
    assert mismatch is False
    assert "adopted" in note


def test_no_claim_leaves_the_row_alone_and_says_why():
    window, verified, mismatch, note = resolve_verification(8192, None, fresh=False)

    assert (window, verified, mismatch) == (8192, False, False)
    assert "nothing to verify against" in note


# ── the verification against the database ─────────────────────────────────────

async def _provider(db, name: str, provider_type: str = "weird") -> Provider:
    provider = Provider(name=name, display_name=name, provider_type=provider_type)
    db.add(provider)
    await db.flush()
    return provider


async def _curated(db, provider: Provider, model_id: str, window, thinking="none"):
    row = CuratedModel(
        provider_id=provider.id, model_id=model_id, model_name=model_id,
        context_length=window, thinking=thinking, verified=False, is_active=True,
    )
    db.add(row)
    await db.flush()
    return row


async def _claim(db, provider: Provider, model_id: str, window, *, expires_in_hours=24, raw=RAW):
    row = ProviderModelCache(
        provider_id=provider.id, model_id=model_id, name=model_id,
        context_length=window, raw_data=raw,
        cached_at=datetime.now(timezone.utc) - timedelta(hours=1),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
    )
    db.add(row)
    await db.flush()
    return row


async def test_the_working_drivers_row_is_verified_and_written(test_session):
    """The phase's own acceptance: 262144, verified, written to the row."""
    provider = await _provider(test_session, "verify-a")
    row = await _curated(test_session, provider, "inclusionai/ling-3.0-flash", None)
    await _claim(test_session, provider, "inclusionai/ling-3.0-flash", 262144)

    result = await curated_model_service.verify_window(test_session, row.id)

    assert result is not None
    assert (result.window, result.verified, result.mismatch) == (262144, True, False)
    assert result.curated is None                       # what the row said before
    assert result.thinking_curated == "none"
    assert result.thinking_provider == "reasoning: default_enabled=True, mandatory=False"
    assert result.max_completion == 32768
    # and the ROW carries it now
    await test_session.refresh(row)
    assert (row.context_length, bool(row.verified)) == (262144, True)


async def test_a_disagreeing_row_is_overwritten_with_the_providers_number(test_session):
    provider = await _provider(test_session, "verify-b")
    row = await _curated(test_session, provider, "m-small", 8192)
    await _claim(test_session, provider, "m-small", 262144)

    result = await curated_model_service.verify_window(test_session, row.id)

    assert result is not None
    assert (result.curated, result.window, result.mismatch) == (8192, 262144, True)
    await test_session.refresh(row)
    assert row.context_length == 262144


async def test_a_stale_claim_is_used_and_left_UNVERIFIED(test_session):
    provider = await _provider(test_session, "verify-c")
    row = await _curated(test_session, provider, "m-stale", None)
    await _claim(test_session, provider, "m-stale", 8192, expires_in_hours=-24)

    result = await curated_model_service.verify_window(test_session, row.id)

    assert result is not None
    assert (result.window, result.verified, result.stale) == (8192, False, True)
    assert result.age_hours is not None
    await test_session.refresh(row)
    assert row.context_length == 8192          # recorded …
    assert bool(row.verified) is False         # … and honest about it


async def test_a_model_the_provider_does_not_list_is_left_alone(test_session):
    provider = await _provider(test_session, "verify-d")
    row = await _curated(test_session, provider, "m-unlisted", 4096)

    result = await curated_model_service.verify_window(test_session, row.id)

    assert result is not None
    assert (result.window, result.verified) == (4096, False)
    assert "nothing to verify against" in result.note


async def test_a_refresh_that_cannot_run_is_a_NOTE_not_a_claim(test_session, caplog):
    """No refresh path for this provider type → the claim is the cached one, said out loud."""
    import logging

    provider = await _provider(test_session, "verify-e", provider_type="weird")
    row = await _curated(test_session, provider, "m-norefresh", 8192)
    await _claim(test_session, provider, "m-norefresh", 262144)

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.curated_models_service"):
        result = await curated_model_service.verify_window(test_session, row.id, refresh=True)

    assert result is not None
    assert result.refreshed is False
    assert "the refresh could not run" in result.note
    assert "no refresh path" in result.note
    assert "WINDOW VERIFY could not refresh" in caplog.text


async def test_an_unknown_row_is_None(test_session):
    assert await curated_model_service.verify_window(test_session, 999999) is None


async def test_the_mislabelled_thinking_is_ADOPTED_not_merely_reported(test_session, caplog):
    """F.3 reversed this test's premise on purpose: the mismatch is CORRECTED now.

    E.4 reported the disagreement (`THINKING MISMATCH`) and left the label alone, because
    mapping the provider's claim onto our levels was F.3's ruling. That ruling landed:
    the verification is the one place that holds the claim, so the label stops being a
    hand-set value no API can correct.
    """
    import logging

    provider = await _provider(test_session, "verify-f")
    row = await _curated(test_session, provider, "m-thinking", 262144, thinking="none")
    await _claim(test_session, provider, "m-thinking", 262144)

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.curated_models_service"):
        await curated_model_service.verify_window(test_session, row.id)

    assert "THINKING ADOPTED" in caplog.text
    assert "curated=none" in caplog.text
    await test_session.refresh(row)
    assert row.thinking == "high"


async def test_a_row_that_already_claims_thinking_is_not_flagged(test_session, caplog):
    import logging

    provider = await _provider(test_session, "verify-g")
    row = await _curated(test_session, provider, "m-thinks", 262144, thinking="high")
    await _claim(test_session, provider, "m-thinks", 262144)

    with caplog.at_level(logging.WARNING, logger="app.domain.providers.curated_models_service"):
        await curated_model_service.verify_window(test_session, row.id)

    assert "THINKING MISMATCH" not in caplog.text


# ── the endpoint ──────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_the_endpoint_verifies_and_returns_what_it_did(client, test_session):
    provider = await _provider(test_session, "verify-api")
    row = await _curated(test_session, provider, "m-api", None)
    await _claim(test_session, provider, "m-api", 128000, raw={"_raw": {"id": "m-api"}})
    await test_session.commit()

    response = await client.post(f"/api/v1/curated-models/{row.id}/verify-window", json={})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["window"] == 128000
    assert body["verified"] is True
    assert body["mismatch"] is False
    assert body["model_id"] == "m-api"
    assert body["thinking_provider"] is None          # this payload exposes none


@pytest.mark.anyio
async def test_the_endpoint_404s_for_an_unknown_row(client):
    response = await client.post("/api/v1/curated-models/999999/verify-window", json={})
    assert response.status_code == 404


# ── F.3: the label is ADOPTED, not just reported ──────────────────────────────

async def test_a_hand_set_label_is_adopted_from_the_providers_claim(test_session):
    """The write path F.3 adds: the row stops being a value no API can correct."""
    provider = await _provider(test_session, "verify-adopt")
    row = await _curated(test_session, provider, "adopt-me", 262144, thinking="none")
    await _claim(test_session, provider, "adopt-me", 262144)

    result = await curated_model_service.verify_window(test_session, row.id)

    assert result is not None
    assert result.thinking_curated == "none"      # what it said before
    assert result.thinking_adopted == "high"      # the claim's projection
    await test_session.refresh(row)
    assert row.thinking == "high"


async def test_a_mandatory_claim_is_recorded_as_mandatory(test_session):
    raw = {
        "_raw": {
            "id": "mand-m",
            "context_length": 1000,
            "reasoning": {"mandatory": True, "default_effort": "max"},
        }
    }
    provider = await _provider(test_session, "verify-mand")
    row = await _curated(test_session, provider, "mand-m", 1000, thinking="none")
    await _claim(test_session, provider, "mand-m", 1000, raw=raw)

    result = await curated_model_service.verify_window(test_session, row.id)

    assert result is not None
    assert result.thinking_adopted == "mandatory"
    await test_session.refresh(row)
    assert row.thinking == "mandatory"


async def test_a_label_the_claim_agrees_with_is_left_alone(test_session):
    provider = await _provider(test_session, "verify-agree")
    row = await _curated(test_session, provider, "agree-m", 262144, thinking="high")
    await _claim(test_session, provider, "agree-m", 262144)

    result = await curated_model_service.verify_window(test_session, row.id)

    assert result is not None
    assert result.thinking_adopted is None
    assert result.thinking_curated == "high"
    await test_session.refresh(row)
    assert row.thinking == "high"
