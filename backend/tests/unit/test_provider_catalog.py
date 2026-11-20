"""The `GET /providers` catalog READS its addresses; it does not keep a second copy.

The 2026-10-12 address ruling (option A, staged): the registry is the one home for "where does this
provider type live", and the catalog — which Exa's own skills read for orientation — derives from it,
keeping a declared display value only for the two types the registry declines by design.
Page: `wiki/issues/resolved/embedded-service-literals/provider-addresses-registry-copies.md`.
"""

from app.domain.providers.provider_endpoints import canonical_endpoint


def test_every_address_the_registry_answers_for_comes_from_the_registry():
    from app.api.v1.providers.router import PROVIDERS

    derived = 0
    for slug, entry in PROVIDERS.items():
        canonical = canonical_endpoint(slug)
        if canonical:
            assert entry["base_url"] == canonical, slug
            derived += 1
    assert derived >= 3, "most of the catalog should be reading the registry, not declaring"


def test_the_two_types_the_registry_declines_keep_a_declared_display_value():
    """`openai` and `anthropic` name a hosted vendor AND any self-hosted compatible server."""
    from app.api.v1.providers.router import PROVIDERS

    assert canonical_endpoint("openai") is None and canonical_endpoint("anthropic") is None
    assert PROVIDERS["openai"]["base_url"] == "https://api.openai.com/v1"
    assert PROVIDERS["anthropic"]["base_url"] == "https://api.anthropic.com"


def test_the_catalog_keeps_the_shape_its_readers_observe():
    """Exa's surface map reads `{id, name, type, base_url, configured}` — the shape is a contract.

    The MEMBERSHIP is a contract too, but it is the REGISTRY's to state: the catalog covers every
    type the registry answers for, plus the two it declines by design (`openai`, `anthropic` —
    each names a hosted vendor AND any self-hosted compatible server). Written out as a copy of
    the names, this assertion went red the day `groq` and `ollama_cloud` were added — a
    chore for whoever adds a provider, not a broken contract.
    """
    from app.api.v1.providers.router import PROVIDERS
    from app.domain.providers.provider_endpoints import PROVIDER_ENDPOINTS

    declined_by_design = {"openai", "anthropic"}
    assert set(PROVIDERS) == set(PROVIDER_ENDPOINTS) | declined_by_design
    for slug, entry in PROVIDERS.items():
        assert set(entry) == {"name", "base_url", "type"}, slug
        assert entry["type"] in ("local", "cloud"), slug
        assert entry["base_url"].startswith("http"), slug
