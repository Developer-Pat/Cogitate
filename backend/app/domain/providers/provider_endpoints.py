"""THE PROVIDER-TYPE ENDPOINT REGISTRY — where a provider TYPE's own endpoint is defined.

**THE RULING THIS IMPLEMENTS** (2026-10-10, the user, the service-literals arc). The arc's rule
is *the app should never write down the name of a model, an endpoint or a service*, and what
settles a borderline case is whether the literal is a **decision** or a **definition**:

- A **DECISION** is the app choosing, on the user's behalf, which service does the work. A
  provider row carries that answer, and code must not keep a copy of it — *not even as a
  backup*: a backup is how a configuration gap passes for a deliberate address.
- A **DEFINITION** is a utility describing the one service it exists to talk to — the vendor's
  catalog, its prices, its published endpoint. That is legitimate, and it belongs in ONE named
  constant rather than inline at the point of use.

A provider **type's** endpoint is the definition half, and this module is where the definitions
live: one entry per type, naming the address that type's vendor publishes. It is **not** a
second source of truth about which service is used.

    **A row's ``base_url`` ALWAYS wins. This table answers only when the row declares none —
    and ``llm_factory.get_llm_from_config`` REPORTS that omission** (``logger.warning``, naming
    the provider and the address it fell back to), so a silent configuration gap cannot pass
    for an address somebody chose. That report is the whole reason this indirection is worth
    having: five adapters used to carry their own copy of these values inline, and one of them
    had already drifted from the row it was meant to agree with.

**Deliberately ABSENT — ``openai`` and ``anthropic``.** Those type names are overloaded: they
mean the hosted vendor, *and* any self-hosted OpenAI-compatible server on the loopback (the
live ``llama`` row is ``provider_type="openai"`` at ``127.0.0.1:8080/v1`` — see
``provider_classes.provider_location``, which resolves a cloud-typed loopback row as LOCAL for
exactly this reason). There is no single canonical address to answer with, so no entry exists
and the adapter's own default applies; a row of those types is expected to declare its endpoint.

**What is a legitimate home, and what is not.** An endpoint may be written down where the code
talks to ONE known service to read that service's own information (``deepseek_client``,
``groq_client``, ``openrouter_client`` — model discovery only; the ``*_browser`` modules' model
lists). It must not be written down where the app decides who does the work — which is why the
dispatch path reads this table instead of carrying literals of its own.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# The vendors' own published endpoints, keyed by provider TYPE (the value `get_llm_from_config`
# dispatches on) — not by row name, which is a label the user chooses.
PROVIDER_ENDPOINTS: dict[str, str] = {
    "ollama": "http://localhost:11434",
    "ollama_cloud": "https://ollama.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    # THE BARE HOST (2026-10-12, the address ruling). This entry carried `/v1`, which no source in
    # this install could point at: DeepSeek's own current docs print
    # `base_url (OpenAI) = https://api.deepseek.com` and never mention /v1, the live row here
    # carries the bare host, and this install runs its agents AND Exa on it. An address needs a
    # source — see wiki/issues/resolved/embedded-service-literals/provider-addresses-registry-copies.md.
    "deepseek": "https://api.deepseek.com",
    "groq": "https://api.groq.com/openai/v1",
}


def canonical_endpoint(provider_type: str) -> str | None:
    """The type's own endpoint, or ``None`` when the type has no single canonical one.

    ``None`` is an answer, not a failure: it says "the row has to declare this" (``openai``,
    ``anthropic``), so a caller must not treat it as a lookup that went wrong.
    """
    return PROVIDER_ENDPOINTS.get(provider_type)


# ── THE ADDRESS FOR ANOTHER PROCESS (the 2026-10-12 ruling, option A) ────────────────────────────
#
# **The acceptance rule on the external-agent model save.** The page is
# `wiki/issues/resolved/embedded-service-literals/exa-model-save-undialable-provider.md`: the save used to decide an address for ANOTHER
# process out of a three-entry literal map, so a provider the map did not know kept the PREVIOUS
# provider's address, and a name nothing could dial was written and reported as a success.
#
# Order, and why:
#   1. an EXPLICIT ``base_url`` wins — the caller is the authority about its own process;
#   2. the TYPE's canonical endpoint — for a compat client this is the root that vendor publishes for
#      it, which is why it beats the row for a HYBRID type (`ollama_cloud`'s row carries the native
#      host, and handing that to a compat client is the measured 404 in the arc's ruling);
#   3. the ROW's own ``base_url`` — the install's decision about which server answers, for a type the
#      registry declines by design (`openai`, i.e. a self-hosted OpenAI-compatible server);
#   4. nothing derivable but the client KNOWS the provider → write nothing and CLEAR any existing
#      address, so the client's own default applies and no stale value survives;
#   5. otherwise **REFUSE** — nothing can dial it, so a save cannot produce a working config.


@dataclass(frozen=True)
class ClientAddress:
    """What to write for another process, or why the save must be refused."""

    base_url: str | None = None
    clear: bool = False
    refusal: str | None = None
    note: str | None = None


def address_for_client(
    provider: str,
    *,
    row_type: str | None = None,
    row_base_url: str | None = None,
    explicit: str | None = None,
    client_knows: bool = False,
) -> ClientAddress:
    """The address to write for ``provider`` into another process's config.

    Pure: the caller supplies the row facts and whether the client knows the provider, so the rule is
    testable without a database or a client.
    """
    if explicit:
        return ClientAddress(base_url=explicit)

    canonical = canonical_endpoint(row_type or "") or canonical_endpoint(provider)
    if canonical:
        note = None
        if row_base_url and row_base_url != canonical:
            note = (
                f"'{provider}' resolved to the '{row_type or provider}' type's canonical endpoint "
                f"{canonical}; the row says {row_base_url} — pass base_url to use the row's address"
            )
        return ClientAddress(base_url=canonical, note=note)

    if row_base_url:
        return ClientAddress(base_url=row_base_url)

    if client_knows:
        return ClientAddress(
            clear=True,
            note=(
                f"'{provider}' has no row and no canonical endpoint; the client knows it, so its own "
                f"default applies — the address field is cleared rather than left stale"
            ),
        )

    return ClientAddress(
        refusal=(
            f"'{provider}' cannot be dialled: no provider row of that name, no canonical endpoint for "
            f"its type, and the client does not know it"
        )
    )


def client_can_dial(provider: str) -> bool:
    """Whether a litellm client can dial this provider with NO address from us.

    Exa's Hermes process builds its requests through litellm, which carries its own per-provider
    defaults (measured 2026-10-12: ``deepseek`` → ``https://api.deepseek.com/beta``; ``groq`` and
    ``mistral`` → their own roots; ``openai``/``anthropic``/``openrouter`` resolved internally). A name
    litellm does not know raises, which is the answer: nothing can dial it, so an address written for
    it would be a guess.
    """
    try:
        import litellm

        litellm.get_llm_provider(f"{provider}/probe")
        return True
    except Exception:
        return False


# ── The NATIVE root of a resolved endpoint ───────────────────────────────────────────────────────
#
# **THE `ollama_cloud` RULING (2026-10-11, the user — `wiki/issues/resolved/embedded-service-literals/ollama-cloud-two-api-roots.md`).**
# A row's ``base_url`` names **the API root the app DIALS**. For a type dialled through an
# OpenAI-compatible client that root is the compat one — ``https://ollama.com/v1`` — and the same
# service's NATIVE API does not live beneath it: measured on ``ollama.com``, ``/api/tags`` answers
# 200 while ``/v1/api/tags`` answers **404**. So a consumer that speaks the native protocol asks for
# the native root HERE, instead of pasting its path onto a compat root and dialling outside the
# service. One rule, one place — the same shape as `resolve_endpoint`.
#
# Only a trailing ``/v1`` is removed: that is the one suffix the app's own convention puts there
# (`join_probe_url` declares a managed base_url to carry the litellm-style root). A bare host comes
# back as it stands — which is what the LOCAL ``ollama`` row is, and must stay: every consumer of
# that row is native (`ChatOllama`, litellm's ``ollama_chat`` handler), so its root already IS the
# native one and nothing derives from it.


def native_root(base_url: str) -> str:
    """The native root of a resolved endpoint — a trailing ``/v1`` (the compat root) removed.

    Not a second answer to "where does this provider live": the endpoint still comes from the row
    (`resolve_endpoint`). This only says which of the one service's two roots a NATIVE path belongs
    to, in the one place that knows it.
    """
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base[: -len("/v1")]
    return base


# ── The types the app dials over BOTH protocols ──────────────────────────────────────────────────
#
# Most types speak ONE protocol, so a row's endpoint IS the root the app dials and nothing about it
# can be ambiguous. `ollama_cloud` is the exception: the app dials its **OpenAI-compatible** API to do
# work (`llm_factory._create_ollama_cloud_client`) and its **native** API to list models and check the
# key (`discovery_service.discover_ollama_cloud_models`, `availability`). The two roots are different
# directories on one host — measured on `ollama.com`: `/v1/chat/completions` answers 401 (it exists),
# `/chat/completions` answers **404**, `/api/tags` answers 200 and `/v1/api/tags` answers **404**.
#
# This table exists for exactly those types. It is what lets the report below tell a row carrying the
# NATIVE root from one carrying the COMPAT root: `native_root` alone cannot, because a host with no
# native API has nothing to be right or wrong about — and a row on a different host is not this
# app's business at all.
NATIVE_API_ROOTS: dict[str, str] = {
    "ollama_cloud": "https://ollama.com",
}


def compat_root_offer(provider_type: str, base_url: str | None) -> str | None:
    """The endpoint to SET, when a row carries a hybrid type's NATIVE root where the app dials the compat one.

    **THE REPORT HALF OF THE RULING** (2026-10-11, the user — *"report, then offer"*,
    `wiki/issues/resolved/embedded-service-literals/ollama-cloud-two-api-roots.md`): a row's ``base_url`` names the API root the app
    DIALS, so a hybrid type's row carries its COMPAT root. A row carrying the type's native root
    instead makes every OpenAI-compatible call land one directory outside the API — measured, a
    completion is posted to ``https://ollama.com/chat/completions``, which answers 404.

    Returns the value to set — **the OFFER, never applied**. The app reports; the row stays the user's.

    Deliberately silent when the row names a DIFFERENT host (a proxy, a mirror, a shim): the app cannot
    know which root such a host serves, and guessing there would be a second answer to a decided
    question. It speaks only about the one thing it knows: the type's own two roots, from this module.
    """
    if not base_url:
        return None
    native = NATIVE_API_ROOTS.get(provider_type)
    canonical = canonical_endpoint(provider_type)
    if not native or not canonical:
        return None
    if native_root(base_url) != native:
        return None  # some other service entirely — not this helper's business
    if base_url.rstrip("/") == canonical:
        return None  # the row already carries the compat root
    return canonical


def resolve_endpoint(provider_type: str, base_url: str | None, subject: str) -> str | None:
    """**THE HOUSE RULE for "where does this provider live": the ROW's endpoint, else the TYPE's.**

    ``base_url`` is the row's own field — its decision about which server answers, and the one place
    the user edits it. When a row declares none, the provider TYPE's canonical endpoint answers from
    the registry above; the omission is LOGGED either way, because silence in the config must never
    pass for an address somebody chose.

    ``None`` means the row declares nothing **and** the type has no canonical endpoint (``openai`` and
    ``anthropic``, which each name a hosted vendor and any self-hosted OpenAI-compatible server). A
    caller that gets ``None`` **REPORTS** it — nothing may dial a guessed address.

    ``subject`` names what is being resolved (usually the row's name) so the report is actionable.
    Every endpoint decision in the app goes through here, so there is ONE place that knows the rule.
    """
    if base_url:
        return base_url
    canonical = canonical_endpoint(provider_type)
    if canonical:
        logger.warning(
            "Provider row '%s' (%s) declares no base_url — using the '%s' type's canonical endpoint "
            "(%s). Set one on the row to make the address explicit.",
            subject,
            provider_type,
            provider_type,
            canonical,
        )
        return canonical
    logger.warning(
        "Provider row '%s' (%s) declares no base_url, and the '%s' type has no canonical endpoint.",
        subject,
        provider_type,
        provider_type,
    )
    return None
