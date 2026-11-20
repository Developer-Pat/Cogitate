"""Which key a call carries — the defect that blamed a valid credential.

Measured on a fresh install (2026-11-20): a chat turn to a provider row NAMED "Deepseek" (type
`deepseek`) sent the literal string `local-llama` to api.deepseek.com, and the vendor answered
401 — so the app reported "DeepSeek Flash is not functioning properly — authentication failed"
for a key that returned 200 when tested directly.

Two rules defend against that, and these tests are the fence round them:

1. the whole-row lookup tolerates the NAME (the table is keyed by TYPE);
2. the keyless placeholder is for a LOOPBACK endpoint and nothing else, so a cloud call with no
   key in reach fails as missing instead of authenticating with a dummy.
"""

from app.domain.providers.env_key_store import EnvKeyStore
from app.domain.providers.llm_factory import LOCAL_KEY_PLACEHOLDER, placeholder_key_for


class TestThePlaceholderIsOnlyForLoopback:
    def test_a_cloud_endpoint_gets_no_placeholder(self):
        assert placeholder_key_for("https://api.deepseek.com", "deepseek/deepseek-flash") is None
        assert placeholder_key_for("https://openrouter.ai/api/v1", "openrouter/x") is None

    def test_an_ollama_chat_handler_gets_one_even_on_a_cloud_host(self):
        """`ollama_chat/…` attaches no auth of its own, and the `ollama_cloud` root is
        `https://ollama.com` — its key is added by a separate branch. The handler decides."""
        assert placeholder_key_for("https://ollama.com", "ollama_chat/nemotron-3-super") == (
            LOCAL_KEY_PLACEHOLDER
        )

    def test_a_loopback_endpoint_gets_one(self):
        assert placeholder_key_for("http://localhost:11434") == LOCAL_KEY_PLACEHOLDER
        assert placeholder_key_for("http://127.0.0.1:8080/v1") == LOCAL_KEY_PLACEHOLDER

    def test_no_endpoint_at_all_gets_none(self):
        assert placeholder_key_for(None) is None
        assert placeholder_key_for("") is None


class TestARowNameFindsItsProvidersKey:
    def test_the_type_and_a_lowercased_name_agree(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("DEEPSEEK_API_KEY=sk-not-a-real-key\n", encoding="utf-8")
        store = EnvKeyStore(env_path=env)

        assert store.get_key("deepseek") == "sk-not-a-real-key"
        assert store.get_key("Deepseek") == "sk-not-a-real-key", (
            "the chat path hands this the provider row's NAME — a capital must not lose the key"
        )

    def test_an_unknown_name_still_answers_none(self, tmp_path):
        env = tmp_path / ".env"
        env.write_text("DEEPSEEK_API_KEY=sk-not-a-real-key\n", encoding="utf-8")
        assert EnvKeyStore(env_path=env).get_key("some local box") is None
