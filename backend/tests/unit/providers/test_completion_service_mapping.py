"""Unit tests for CompletionRequest.to_litellm_kwargs provider mapping."""

from app.domain.providers.completion_service import CompletionRequest


class TestLitellmProviderMapping:
    """`CompletionRequest` rides the app's ONE mapping (`litellm_route`) now.

    `ollama_cloud` used to send the `openai/` prefix HERE while the chat path sent `ollama_chat/` —
    two homes disagreeing about the protocol for one provider. It rides the tool-capable handler
    everywhere now, and the ADDRESS is the caller's: a value object cannot look a row up and must not
    carry a copy of it, so the request is handed its endpoint (2026-10-12, stage 2).
    """

    def test_ollama_cloud_rides_the_tool_capable_handler(self) -> None:
        req = CompletionRequest(
            messages=[{"role": "user", "content": "hi"}],
            model="gemma4:31b",
            provider="ollama_cloud",
            endpoint="https://ollama.com/v1",
        )
        kwargs = req.to_litellm_kwargs()
        assert kwargs["model"] == "ollama_chat/gemma4:31b"
        # the NATIVE root: `ollama_chat` composes `{api_base}/api/chat` itself, so handing it the
        # compat root would land one directory outside the API (measured 404)
        assert kwargs["api_base"] == "https://ollama.com"

    def test_no_endpoint_means_no_api_base(self) -> None:
        """Nothing is invented for a request that was handed no address — the caller knows; a value
        object must not guess one."""
        req = CompletionRequest(
            messages=[{"role": "user", "content": "hi"}],
            model="gemma4:31b",
            provider="ollama_cloud",
        )
        kwargs = req.to_litellm_kwargs()
        assert "api_base" not in kwargs

    def test_ollama_cloud_includes_api_key_from_settings(self, monkeypatch) -> None:
        from app.core.config import get_settings
        monkeypatch.setattr(get_settings(), "ollama_cloud_api_key", "test-cloud-key")

        req = CompletionRequest(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-oss:20b",
            provider="ollama_cloud",
            endpoint="https://ollama.com/v1",
        )
        kwargs = req.to_litellm_kwargs()
        assert kwargs["api_key"] == "test-cloud-key"

    def test_regular_providers_keep_own_prefix(self) -> None:
        req = CompletionRequest(
            messages=[{"role": "user", "content": "hi"}],
            model="deepseek-v4-flash",
            provider="deepseek",
        )
        kwargs = req.to_litellm_kwargs()
        assert kwargs["model"] == "deepseek/deepseek-v4-flash"
        assert "api_base" not in kwargs
