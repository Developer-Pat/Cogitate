"""D.5 (trimmed) — the cost limit is INACTIVE, and BOTH paths say so.

D8's ruling is why there is no enforcement half here: cost limits stay inactive
until pricing is verified, because a limit judged against a $0 measurement is a
guard that does nothing while claiming to. D.5 as trimmed has to make the
INACTIVE state LEGIBLE on both sides of the same fact:

* `limits.TURN_LIMITS_INACTIVE` declares `cost_usd` inactive in the census the log
  prints beside the armed set — so a reader can tell "nothing is near a line" from
  "nothing is watching";
* `ProviderService.calculate_cost` says `cost limit inactive` at the moment it
  falls back to $0 for an unpriced model — i.e. where the number the limit WOULD
  judge is produced.

The second half is what was missing: the log said "no pricing … treating as $0",
which names the gap but not its consequence, so a reader had to remember that the
cost limit is not watching. The two halves agree by test rather than by habit.
"""

import logging

from app.domain.providers.services import ProviderService
from app.services.cognitive_pipeline.limits import TURN_LIMITS_INACTIVE

# A model PRICING does not carry — so this exercises `calculate_cost` with NO resolved price,
# the fallback path. The live caller resolves one from the provider's catalog first
# (`_log_usage` -> `ProviderModelCacheService.pricing_for_model`; `test_cost_from_catalog.py`),
# and this model IS priced there. What is pinned here is the call that passes nothing.
UNPRICED = "openrouter/inclusionai/ling-3.0-flash"
PRICED = "deepseek/deepseek-v4-flash"


def _lines(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records]


class TestTheCostLimitSaysItIsInactive:
    def test_the_turn_census_declares_cost_inactive(self):
        """The armed-set census names the limit it is not watching."""
        assert "cost_usd" in TURN_LIMITS_INACTIVE
        assert "pricing" in TURN_LIMITS_INACTIVE["cost_usd"].lower()

    def test_an_unpriced_model_says_the_cost_limit_is_inactive(self, caplog):
        with caplog.at_level(logging.WARNING):
            cost = ProviderService().calculate_cost("openrouter", UNPRICED, 1000, 1000)

        assert cost == 0.0
        line = next(l for l in _lines(caplog) if "no pricing" in l)
        assert "cost limit inactive" in line, line
        # and it names the model it is about, so the gap is attributable
        assert "inclusionai/ling-3.0-flash" in line, line

    def test_a_priced_model_computes_the_number_and_does_not_claim_inactive(self, caplog):
        """The other half of the same fact: a priced model produces a real number.

        Enforcement is deliberately NOT tested here — it waits for real pricing
        (D8). What must hold today is that the priced path computes a cost and
        does not carry the inactive sentence.
        """
        with caplog.at_level(logging.WARNING):
            cost = ProviderService().calculate_cost("deepseek", PRICED, 1000, 1000)

        assert cost > 0
        assert not any("cost limit inactive" in l for l in _lines(caplog)), _lines(caplog)
