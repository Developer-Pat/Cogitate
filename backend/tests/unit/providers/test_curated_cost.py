"""The cost fact's derivation, and the rule the backfill applied.

`cost_from_raw` is where a curated row's `is_free` comes from: the provider's own cached pricing,
read at intake. It has THREE answers — free, priced, and the honest unknown — and the third is the
reason the phase exists, so each case is pinned here.

The last class is a DRIFT GUARD, not a duplicate: the backfill that made the column nullable carried
its own frozen copy of the rule (a migration is a record of what IT did), and this asserts the two
still say the same thing. The copy lives HERE as a literal now — the migration that carried it was
retired with the chain, and the assertion is still worth keeping. If the live rule changes on
purpose, that test fails and the change becomes a decision instead of a silent divergence.
"""

from typing import Any, Optional

import pytest

from app.domain.providers.curated_models_service import cost_from_raw


def _as_amount(value: Any) -> Optional[float]:
    """One price component as a number, or ``None`` when the entry is not an amount."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _frozen_backfill_rule(raw_data: Any, location: str) -> Optional[bool]:
    """THE RULE AS THE BACKFILL APPLIED IT — a frozen copy of ``cost_from_raw``.

    The rule: the prices live at ``_raw.pricing``, and a model is free when the payload prices it and
    EVERY priced component is zero. A payload that prices nothing is the unknown — except a LOCAL
    model, which is free to call (the hardware was paid for once, not per token).
    """
    pricing: Any = None
    if isinstance(raw_data, dict):
        payload = raw_data.get("_raw")
        if not isinstance(payload, dict):
            payload = raw_data
        pricing = payload.get("pricing")

    if not isinstance(pricing, dict) or not pricing:
        return True if location == "local" else None

    amounts = [
        amount
        for amount in (_as_amount(value) for value in pricing.values())
        if amount is not None
    ]
    if not amounts:
        return None
    return all(amount == 0 for amount in amounts)


def _payload(pricing: Any) -> dict:
    """A cached payload shaped like the discovery fetch writes it."""
    return {"id": "some/model", "name": "Some Model", "_raw": {"pricing": pricing}}


class TestTheThreeAnswers:
    """Free, priced, and unknown — the whole vocabulary of this fact."""

    def test_a_model_the_provider_prices_is_paid(self) -> None:
        assert cost_from_raw(_payload({"prompt": "0.000000021", "completion": "0.00000032"})) is False

    def test_a_model_priced_at_zero_everywhere_is_free(self) -> None:
        assert cost_from_raw(_payload({"prompt": "0", "completion": "0"})) is True

    def test_zero_tokens_but_a_charged_extra_is_NOT_free(self) -> None:
        """The case the live catalog cannot produce today, and the one that decides the rule.

        No cached row charges for anything while prompt and completion both read zero, so "free =
        prompt+completion are 0" would pass every live check — and be wrong the first time a model
        gives its tokens away but bills per request, per image or per cache write. Every priced
        component counts.
        """
        assert cost_from_raw(_payload({"prompt": "0", "completion": "0", "request": "0.001"})) is False
        assert cost_from_raw(_payload({"prompt": "0", "completion": "0", "image": "0.04"})) is False

    def test_a_payload_that_prices_nothing_is_unknown(self) -> None:
        """Two configured providers publish no price at all, so this is a live case, not a shape."""
        assert cost_from_raw({"id": "deepseek/x", "_raw": {"context_window": 128000}}) is None
        assert cost_from_raw(_payload({})) is None
        assert cost_from_raw(None) is None
        assert cost_from_raw("not a payload") is None

    def test_a_pricing_dict_with_no_amounts_is_unknown(self) -> None:
        assert cost_from_raw(_payload({"overrides": [{"a": 1}], "note": "n/a"})) is None

    def test_a_local_model_with_no_price_is_free(self) -> None:
        """Calling a local model costs nothing — the hardware was paid for once, not per token."""
        assert cost_from_raw({"id": "llama3.2:latest"}, location="local") is True
        assert cost_from_raw({"id": "llama3.2:latest"}, location="cloud") is None


class TestWhereThePriceIsRead:
    """`_raw.pricing` — NOT `pricing`, which no cached row carries."""

    def test_the_raw_wrapper_is_unwrapped(self) -> None:
        assert cost_from_raw(_payload({"prompt": "0"})) is True

    def test_a_payload_with_no_underscore_raw_reads_at_the_top_level(self) -> None:
        assert cost_from_raw({"pricing": {"prompt": "0"}}) is True

    def test_prices_may_arrive_as_numbers(self) -> None:
        assert cost_from_raw({"pricing": {"prompt": 0, "completion": 0}}) is True
        assert cost_from_raw({"pricing": {"prompt": 0.5}}) is False

    def test_a_boolean_entry_is_not_an_amount(self) -> None:
        """`True` is an `int` in Python, and `float(True) == 1.0` would make a flag a price."""
        assert cost_from_raw({"pricing": {"free": True}}) is None


class TestTheBackfillAgreesWithTheLiveRule:
    """The frozen copy of the backfill's rule says what the live rule says (drift guard)."""

    @pytest.mark.parametrize(
        "raw_data,location",
        [
            (_payload({"prompt": "0", "completion": "0"}), "cloud"),
            (_payload({"prompt": "0.000000021"}), "cloud"),
            (_payload({"prompt": "0", "completion": "0", "web_search": "0.01"}), "cloud"),
            (_payload({}), "cloud"),
            ({"id": "deepseek/x", "_raw": {"api_capabilities": ["chat"]}}, "cloud"),
            (None, "cloud"),
            ({"id": "llama3.2:latest"}, "local"),
            ({"pricing": {"prompt": 0}}, "cloud"),
        ],
    )
    def test_the_frozen_rule_matches(self, raw_data: Optional[dict], location: str) -> None:
        frozen = _frozen_backfill_rule
        assert frozen(raw_data, location) == cost_from_raw(raw_data, location)
