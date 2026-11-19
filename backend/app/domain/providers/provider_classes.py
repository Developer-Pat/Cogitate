"""The provider class seam (2026-09-08, the A1 provider-split).

The one place that decides whether a provider_type is CLOUD or
LOCAL. Extracted from llm_factory's inline key-requirement list;
everything outside the cloud set is treated as local/self-hosted
(ollama, llama.cpp, any LAN daemon).

The vocabulary matches curated_models.location ("cloud"/"local")
so the whole system speaks one class language.
"""

# The remote API-class providers (SaaS / hosted). Anything not in
# this set is local by construction (a daemon the user runs).
PROVIDER_CLOUD_TYPES = frozenset(
    {"openai", "anthropic", "openrouter", "deepseek", "groq", "ollama_cloud"}
)


def _is_loopback(base_url: str | None) -> bool:
    """A self-hosted endpoint (localhost / 127.0.0.1). A cloud-type
    provider pointed at the loopback (e.g. llama.cpp registered as
    an 'openai' type) is LOCAL — the user runs it."""
    if not base_url:
        return False
    host = base_url.split("://")[-1].split("/")[0].split(":")[0].lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def provider_location(provider_type: str, base_url: str | None = None) -> str:
    """The class for a provider: 'cloud' or 'local'.

    Type-first (the cloud whitelist), then the loopback tiebreaker:
    a cloud-typed provider on the loopback is a self-hosted server
    the user runs (llama.cpp registers as 'openai' + 127.0.0.1).
    """
    if provider_type not in PROVIDER_CLOUD_TYPES:
        return "local"
    return "local" if _is_loopback(base_url) else "cloud"
