"""API-tier fixtures.

**The availability probe is neutered for this whole tier.** The capability read-out
(`GET /providers/capabilities`) reads availability on every call — that is the point of phase 6's
group 5 — so without this every API test that touches the read-out would make real network calls to
whatever `base_url`s the copied installation carries, and its result would depend on the machine's
network rather than on the code. Nothing here answers, so the read-out is deterministic and offline.

A test that IS about availability opts back in by patching `availability.probe_json` itself (see
`test_the_read_out_stamps_what_is_up_on_the_resolved_candidates`); its own patch lands after this
fixture and wins.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _offline_availability(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.domain.providers import availability

    async def nothing(base_url: str, path: str, headers=None):
        return None

    monkeypatch.setattr(availability, "probe_json", nothing)
    monkeypatch.setattr(availability, "env_key", lambda provider_type: None)
    availability.clear_cache()
