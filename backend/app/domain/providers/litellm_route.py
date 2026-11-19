"""The LITELLM ROUTE — the ONE home for which litellm handler a provider speaks, and what root it needs.

ONE DECISION, ONE HOME (2026-10-12, the litellm-mapping ruling —
``wiki/issues/litellm-provider-mapping-four-homes.md``). *Which litellm string does this provider get,
and which root does that handler need?* was written in four places: the chat path's handler map, a
two-entry alias table carrying a prefix AND an address, the endpoint registry, and the two
cognitive-pipeline modules that hand-rolled ``{provider}/{model}`` with neither — which produced
``ollama_cloud/<m>`` and ``llama/<m>``, strings litellm REJECTS (``LLM Provider NOT provided``,
measured). This module is the consolidation: everything else reads it.

**TWO FACTS LIVE HERE.**

1. **WHICH HANDLER — decided by the row's TYPE**, because the type is what a provider IS: the dialect
   its server speaks. Litellm knows most types by their own name; ``HANDLER_BY_TYPE`` holds the three
   it does not, and the handler that speaks each one's dialect. ``provider`` (the row NAME) is the
   fallback for a caller that has only the name — the chat path builds its string before it reads the
   row — and for the row names in the map the two answers coincide.

2. **WHICH ROOT — decided by the HANDLER, never by the field.** The ollama family routes to litellm's
   ``ollama_chat`` handler, which composes its OWN paths onto whatever it is given
   (``{api_base}/api/chat``), while the ``openai`` prefix posts to ``{api_base}/chat/completions``. A
   row's ``base_url`` is therefore the app's COMPAT root for a hybrid type, and handing it straight to
   ``ollama_chat`` lands one directory outside the API — measured: ``https://ollama.com/v1/api/chat``
   answers **404** where ``/api/chat`` answers 200 (2026-10-11, the ``ollama_cloud`` ruling,
   ``wiki/issues/resolved/embedded-service-literals/ollama-cloud-two-api-roots.md``). So the ollama
   family is handed the NATIVE root and every other handler gets the endpoint as it stands.

Both functions are IDEMPOTENT: ``api_base_for`` READS the string ``litellm_model_string`` produced
rather than re-deciding the handler, which is what keeps the two from disagreeing about the protocol.
"""

from __future__ import annotations

from typing import Optional

from app.domain.providers.provider_endpoints import native_root

# The types litellm has no prefix for, and the handler that speaks each one's dialect.
HANDLER_BY_TYPE: dict[str, str] = {
    # THE TOOL-CAPABLE OLLAMA HANDLER (2026-08-14, live): litellm's `ollama` provider is treated as
    # function-UNSUPPORTED — it forces `format=json` and injects tools as prompt text, so a capable
    # model emits tool calls as JSON *content* and the tool loop never runs. `ollama_chat` streams
    # real `delta.tool_calls`. The DB provider name stays `ollama`; only the prefix is remapped.
    "ollama": "ollama_chat",
    # THE OLLAMA CLOUD (2026-08-24, live): the provider NAME alone is not a litellm provider, and the
    # cloud row is the same Ollama dialect — so it rides the same tool-capable handler.
    "ollama_cloud": "ollama_chat",
    # THE LOCAL LLAMA.CPP SERVER (2026-09-01, the Bonsai fix): llama-server serves the OpenAI API.
    # Litellm has no native `llama` prefix — the raw string dies with `LLM Provider NOT provided`.
    "llama": "openai",
}


# The handler the ollama family rides — also the one a stored model string may already carry.
_OLLAMA_FAMILY_HANDLER = "ollama_chat"


def handler_for(provider_type: Optional[str], provider: str = "") -> str:
    """The litellm handler a provider speaks — its TYPE, unless litellm has no prefix for the type.

    ``provider`` (the row name) is the fallback for a caller that has no type in hand; it is NOT a
    second map — the same table answers both, so the two can never disagree.
    """
    key = (provider_type or provider or "").strip()
    return HANDLER_BY_TYPE.get(key, key)


def litellm_model_string(provider: str, model: str, provider_type: Optional[str] = None) -> str:
    """The litellm model string for a provider row: ``<handler>/<model>``.

    A model that already carries the row's OWN prefix is stripped first, and one carrying a handler
    this module remaps is remapped rather than doubled — the predecessor was not idempotent for a
    remapped provider whose model was already prefixed, and produced ``openai/llama/<model>``.

    Everything else after the first slash is part of the model NAME, not a handler: ``local/x.gguf``
    and ``library/llama3`` are real model ids, so they are prefixed like any other.
    """
    name = (model or "").strip()
    if "/" in name:
        head, _, rest = name.partition("/")
        if head == _OLLAMA_FAMILY_HANDLER:
            return name  # already the tool-capable handler (a stored model string)
        if head in HANDLER_BY_TYPE and head != provider:
            return f"{HANDLER_BY_TYPE[head]}/{rest}"
        if provider and head == provider:
            name = rest
    handler = handler_for(provider_type, provider)
    return f"{handler}/{name}" if handler else name


def api_base_for(model_string: str, endpoint: Optional[str]) -> Optional[str]:
    """The root the CHOSEN HANDLER needs: the endpoint, or its NATIVE root for the ollama family.

    Reads the string rather than re-deciding the handler, so the root can never disagree with it. An
    empty endpoint is returned as it stands — the caller reports the absence; nothing dials a guess.
    """
    if not endpoint:
        return endpoint
    if (model_string or "").startswith("ollama_chat/"):
        return native_root(endpoint)
    return endpoint
