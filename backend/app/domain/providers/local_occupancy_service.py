"""The LOCAL occupancy service (A3, the read side — 2026-09-09).

The availability-class split made concrete: for each LOCAL daemon, probe it and classify the state:

  healthy           — the daemon answers (loaded = what it serves right now)
  down-by-occupancy — no answer AND another local daemon answers: the GPU is taken by ownership,
                      not an incident
  down              — no answer AND nothing else answers: the ownerless down (incident or
                      deliberate stop — the design's down-by-decision is a later flag)

The occupancy = the set of daemons that answer. The one-at-a-time GPU paradigm means a local "down"
is usually a swap-away — the local page must read it as a choice, not an alert.

**The probe primitives MOVED to `availability.py` (phase 6, group 5).** This module is the LOCAL
page's view — the cross-daemon set, the running list, the loaded models. The primitives themselves
(the short-timeout probe, the `/v1`-join fix, the per-class endpoints) are now the ONE availability
read, so this view and the capability read-out can never disagree about a daemon.
"""

import logging
from typing import Any, Dict, List

from app.domain.providers.availability import is_reachable, served_models

logger = logging.getLogger(__name__)


async def get_local_occupancy(providers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Classify every local provider + report the running set.

    Args:
        providers: the local provider configs (name, provider_type, base_url — the ProviderConfig
            dataclass as dicts).

    Returns:
        {
          "daemons": [{provider_id, name, provider_type, base_url, state, loaded_models[]}],
          "running": [names],   # the daemons that answer
          "generated_at": iso
        }
    """
    # 1. reachability pass
    reachable: Dict[str, bool] = {}
    loaded: Dict[str, List[str]] = {}
    for provider in providers:
        name = provider.get("name", "")
        reachable[name] = await is_reachable(provider)
        if reachable[name]:
            loaded[name] = await served_models(provider)
        else:
            loaded[name] = []

    any_running = any(reachable.values())

    daemons = []
    for provider in providers:
        name = provider.get("name", "")
        up = reachable[name]
        if up:
            state = "healthy"
        elif any_running:
            # Another local daemon answers — the GPU is owned.
            state = "down-by-occupancy"
        else:
            state = "down"
        daemons.append({
            "provider_id": provider.get("id"),
            "name": name,
            "display_name": provider.get("display_name") or name,
            "provider_type": provider.get("provider_type"),
            "base_url": provider.get("base_url"),
            "state": state,
            "loaded_models": loaded[name],
        })

    from datetime import datetime, timezone
    return {
        "daemons": daemons,
        "running": [d["name"] for d in daemons if d["state"] == "healthy"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
