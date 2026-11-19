"""Regression tests for the litellm route — the one mapping, and the root its handler needs.

LiteLLM treats the ``ollama`` provider as function-UNSUPPORTED (it forces ``format=json`` and injects
tools as prompt text), so capable models emit tool calls as JSON content and the tool loop never runs;
``ollama_chat`` is the tool-capable handler. Choosing the handler also decides which ROOT it must be
given: ``ollama_chat`` composes ``{api_base}/api/chat`` itself and strips only a trailing
``/api/chat``, while the ``openai`` prefix posts to ``{api_base}/chat/completions``. A row's endpoint
is the app's COMPAT root for a hybrid type, so handing it straight to the ollama family lands one
directory outside the API — measured: ``https://ollama.com/v1/api/chat`` answers 404 where
``/api/chat`` answers 200.

THE ONE MAPPING (2026-10-12): the handler is decided by the row's TYPE (its dialect), the row's NAME
being the fallback for a caller with no type in hand. Before it the decision was written in four
places, and the two cognitive-pipeline modules hand-rolled ``{provider}/{model}`` — producing
``ollama_cloud/<m>`` and ``llama/<m>``, strings litellm REJECTS. Those modules route through here
now, which is what the last class pins.
"""

from types import SimpleNamespace

import pytest

from app.domain.providers.litellm_route import (
    HANDLER_BY_TYPE,
    api_base_for,
    handler_for,
    litellm_model_string,
)


class TestTheHandlerTheProviderSpeaks:
    def test_the_ollama_family_rides_the_tool_capable_handler(self):
        assert litellm_model_string("ollama", "qwen3:latest", "ollama") == "ollama_chat/qwen3:latest"
        assert litellm_model_string(
            "ollama_cloud", "nemotron-3-super", "ollama_cloud"
        ) == "ollama_chat/nemotron-3-super"

    def test_the_type_decides_not_the_name(self):
        """The name says nothing about the dialect; the TYPE does. `my-ollama` is the case a
        name-keyed map could not answer — it would have emitted `my-ollama/<m>`, which litellm
        REJECTS."""
        assert litellm_model_string("my-ollama", "qwen3:latest", "ollama") == "ollama_chat/qwen3:latest"
        assert litellm_model_string("my-llama-box", "Bonsai-27B.gguf", "llama") == "openai/Bonsai-27B.gguf"

    def test_the_local_llama_row_rides_the_openai_adapter(self):
        """The install's `llama` row is provider_type `openai` — litellm has no native `llama`
        prefix (the Bonsai fix, 2026-09-01)."""
        assert litellm_model_string("llama", "Bonsai-27B-Q1_0.gguf", "openai") == (
            "openai/Bonsai-27B-Q1_0.gguf"
        )

    def test_a_type_litellm_knows_is_its_own_prefix(self):
        assert litellm_model_string("deepseek", "deepseek-v4-flash", "deepseek") == (
            "deepseek/deepseek-v4-flash"
        )
        assert litellm_model_string("groq", "llama-3.3-70b", "groq") == "groq/llama-3.3-70b"
        assert litellm_model_string("mistral", "mistral-large", "mistral") == "mistral/mistral-large"

    def test_the_name_is_the_fallback_when_no_type_is_handed(self):
        """The chat path builds its string before it reads the row; for the names in the map the two
        answers coincide, which is why the fallback is safe."""
        assert litellm_model_string("ollama_cloud", "nemotron-3-super") == "ollama_chat/nemotron-3-super"
        assert litellm_model_string("llama", "Bonsai-27B-Q1_0.gguf") == "openai/Bonsai-27B-Q1_0.gguf"
        assert litellm_model_string("deepseek", "deepseek-v4-flash") == "deepseek/deepseek-v4-flash"

    def test_already_prefixed_models_are_idempotent(self):
        assert litellm_model_string("ollama", "ollama_chat/qwen3:latest", "ollama") == (
            "ollama_chat/qwen3:latest"
        )
        assert litellm_model_string("ollama", "ollama/qwen3:latest", "ollama") == (
            "ollama_chat/qwen3:latest"
        )
        # THE DOUBLING THAT USED TO HAPPEN: the predecessor returned `openai/llama/<model>` here.
        assert litellm_model_string("llama", "llama/Bonsai-27B.gguf", "openai") == (
            "openai/Bonsai-27B.gguf"
        )
        assert litellm_model_string("deepseek", "deepseek/deepseek-v4-flash", "deepseek") == (
            "deepseek/deepseek-v4-flash"
        )

    def test_a_model_name_that_contains_a_slash_is_not_read_as_a_handler(self):
        """`local/x.gguf` and `library/llama3` are real model ids — the slash is part of the NAME,
        so they are prefixed like any other model (the predecessor did the same)."""
        assert litellm_model_string("zz-title-local", "local/zz-model.gguf", "openai") == (
            "openai/local/zz-model.gguf"
        )
        assert litellm_model_string("mine", "library/llama3", "ollama") == (
            "ollama_chat/library/llama3"
        )

    def test_nothing_is_invented_for_a_provider_with_no_type_and_no_name(self):
        assert litellm_model_string("", "some-model") == "some-model"
        assert handler_for(None, "") == ""


class TestTheRootTheHandlerNeeds:
    """One function decides the handler; this one only READS that decision."""

    def test_the_ollama_family_gets_the_native_root(self):
        assert api_base_for(
            litellm_model_string("ollama", "qwen3:latest", "ollama"), "http://localhost:11434"
        ) == "http://localhost:11434"
        assert api_base_for(
            litellm_model_string("ollama_cloud", "nemotron-3-super", "ollama_cloud"),
            "https://ollama.com/v1",
        ) == "https://ollama.com"

    def test_a_row_that_already_carries_the_native_root_is_unchanged(self):
        assert api_base_for(
            litellm_model_string("ollama_cloud", "nemotron-3-super", "ollama_cloud"),
            "https://ollama.com",
        ) == "https://ollama.com"

    def test_the_compat_prefix_gets_the_endpoint_as_it_stands(self):
        assert api_base_for(
            litellm_model_string("deepseek", "deepseek-v4-flash", "deepseek"),
            "https://api.deepseek.com",
        ) == "https://api.deepseek.com"
        assert api_base_for(
            litellm_model_string("llama", "Bonsai-27B-Q1_0.gguf", "openai"),
            "http://127.0.0.1:8080/v1",
        ) == "http://127.0.0.1:8080/v1"

    def test_no_endpoint_is_never_invented(self):
        assert api_base_for("ollama_chat/x", None) is None
        assert api_base_for("ollama_chat/x", "") == ""


class TestTheBackupRebuild:
    """`_backup_request` — the failover's request, whose api_base is the CANDIDATE's endpoint."""

    def _candidate(self, provider, model, provider_type=None, endpoint=None):
        return SimpleNamespace(
            provider=provider, model=model, provider_type=provider_type, endpoint=endpoint
        )

    def test_a_cloud_backup_is_handed_the_native_root(self):
        """The candidate's endpoint is the COMPAT root while the model string is the ollama_chat
        handler: before this, every `ollama_cloud` backup dialled `https://ollama.com/v1/api/chat` —
        a 404."""
        from app.api.v1.chat.router import _backup_request

        kwargs = _backup_request(
            {"model": "x", "messages": [{"role": "user", "content": "hi"}], "api_base": "https://prev/v1", "api_key": "old"},
            self._candidate("ollama_cloud", "nemotron-3-super", "ollama_cloud", "https://ollama.com/v1"),
        )

        assert kwargs["model"] == "ollama_chat/nemotron-3-super"
        assert kwargs["api_base"] == "https://ollama.com"
        assert kwargs["api_key"] == "local-llama"

    def test_a_local_backup_keeps_its_root(self):
        """The `llama` row's endpoint is a compat root and its handler is the openai adapter."""
        from app.api.v1.chat.router import _backup_request

        kwargs = _backup_request(
            {"model": "x", "messages": []},
            self._candidate("llama", "Bonsai-27B-Q1_0.gguf", "openai", "http://127.0.0.1:8080/v1"),
        )

        assert kwargs["model"] == "openai/Bonsai-27B-Q1_0.gguf"
        assert kwargs["api_base"] == "http://127.0.0.1:8080/v1"

    def test_a_candidate_with_no_endpoint_gets_none_invented(self):
        """A row with no address of its own and no canonical endpoint yields NO api_base — nothing
        may dial a guess (the function's own NAMED GAP: a cloud backup rides litellm's env lookup)."""
        from app.api.v1.chat.router import _backup_request

        kwargs = _backup_request(
            {"model": "x", "api_base": "https://prev/v1", "api_key": "old", "extra_headers": {"H": "1"}},
            self._candidate("deepseek", "deepseek-v4-flash", "deepseek", None),
        )

        assert "api_base" not in kwargs
        assert "api_key" not in kwargs
        assert "extra_headers" not in kwargs


class TestThePipelineModulesNoLongerHandRollTheString:
    """THE LATENT FAILURE, pinned. Both modules built `{provider}/{model}` themselves: for either
    aliased provider that is a string litellm REJECTS (`LLM Provider NOT provided`, measured), and
    nothing failed only because the memory and summary capabilities both resolve to `deepseek` on
    this install. These two tests are the ones that would have caught it."""

    def _candidate(self, provider, provider_type, model, endpoint=None):
        from app.domain.providers.capabilities import ServiceCandidate

        return ServiceCandidate(
            ordinal=0, provider=provider, provider_type=provider_type, model=model, endpoint=endpoint
        )

    @pytest.mark.asyncio
    async def test_the_memory_pass_asks_a_dialable_model(self, monkeypatch):
        import litellm

        from app.services.cognitive_pipeline import memory_manager

        seen: dict = {}

        async def fake_acompletion(**kwargs):
            seen.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="ok"))]
            )

        monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
        await memory_manager._ask_service(
            self._candidate("ollama_cloud", "ollama_cloud", "nemotron-3-super", "https://ollama.com/v1"),
            [{"role": "user", "content": "hi"}],
            64,
        )

        assert seen["model"] == "ollama_chat/nemotron-3-super"
        assert seen["api_base"] == "https://ollama.com"
        assert seen["api_key"] == "local-llama"

    @pytest.mark.asyncio
    async def test_the_summary_pass_asks_a_dialable_model(self, monkeypatch):
        import litellm

        from app.services.cognitive_pipeline import conversation_compactor

        seen: dict = {}

        async def fake_acompletion(**kwargs):
            seen.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="summed"))]
            )

        monkeypatch.setattr(litellm, "acompletion", fake_acompletion)
        result = await conversation_compactor._summarize_with(
            self._candidate("llama", "openai", "Bonsai-27B-Q1_0.gguf", "http://127.0.0.1:8080/v1"),
            "summarize this",
        )

        assert result == "summed"
        assert seen["model"] == "openai/Bonsai-27B-Q1_0.gguf"
        assert seen["api_base"] == "http://127.0.0.1:8080/v1"

    def test_an_ordinary_provider_is_unchanged(self):
        """The install's own capabilities (deepseek here) must come out exactly as before."""
        assert litellm_model_string("deepseek", "deepseek-v4-flash", "deepseek") == (
            "deepseek/deepseek-v4-flash"
        )
        assert "deepseek" not in HANDLER_BY_TYPE
