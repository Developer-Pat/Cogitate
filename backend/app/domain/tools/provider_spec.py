"""Provider spec classifier (Phase F — the ARM substrate).

Derives the operational axis of the ARM resource card from the
provider/model strings: local vs cloud, and a size tier. Derived,
never user-entered — an agent's spec is a fact about how it runs.

Rules (plain, data-grounded):
- local providers: ollama (localhost), any base_url on localhost
- cloud: everything else (openrouter, deepseek, openai, anthropic)
- size: models with small/lite/nano/flash/7b/8b/3b/13b or :free →
  small; 70b/120b/400b/large → big; else medium
"""

from __future__ import annotations

from typing import Optional, Tuple

# providers that run locally
LOCAL_PROVIDERS = {"ollama", "local", "lm-studio", "llamacpp", "llama.cpp"}

# model-name markers → size tier
SMALL_MARKERS = ("small", "lite", "nano", "flash", "mini", "7b", "8b",
                 "3b", "13b", "1b", "2b", ":free")
BIG_MARKERS = ("70b", "120b", "400b", "large", "big", "xl", "72b")

LOCAL = "local"
CLOUD = "cloud"
SMALL = "small"
MEDIUM = "medium"
BIG = "big"


def spec_for(provider: Optional[str], model: Optional[str],
             base_url: Optional[str] = None) -> Tuple[str, str]:
    """Derive (location, size) for a provider+model.

    Returns (local|cloud, small|medium|big). Unknown provider →
    cloud (safe default: assume remote), unknown size → medium.
    """
    provider = (provider or "").strip().lower()
    model = (model or "").strip().lower()
    base_url = (base_url or "").strip().lower()

    if provider in LOCAL_PROVIDERS or "localhost" in base_url or "127.0.0.1" in base_url:
        location = LOCAL
    else:
        location = CLOUD

    if any(m in model for m in BIG_MARKERS):
        size = BIG
    elif any(m in model for m in SMALL_MARKERS):
        size = SMALL
    else:
        size = MEDIUM

    return location, size


def location_for(provider: Optional[str], base_url: Optional[str] = None) -> str:
    return spec_for(provider, None, base_url)[0]
