"""A listing is not a key check — the Test button has to be able to FAIL.

On ollama.com every listing is ungated: `/api/tags` answers 200 with no key at all, and the
OpenAI-compat `/v1/models` answers 200 to a deliberately fake one (both measured). The provider Test
therefore reported "connected, 18 models" through a dead key — a health check that cannot fail,
which is worse than no check.

The only gated operation is inference, so `probe_key_accepted` asks for the smallest completion there
is, and a refusal becomes CONFIGURATION (`unconfigured`) rather than an outage: a rejected key is
something to fix, not something to wait on. The check is `verify_key`-only, because it spends a real
request against the account — a badge refresh is not a reason to do that, and the last test here
pins exactly that.
"""

import pytest

from app.domain.providers import availability as av

PROVIDER = {
    "id": 5,
    "name": "ollama_cloud",
    "base_url": "https://ollama.com",
    "provider_type": "ollama_cloud",
}


async def _key_for(_provider):
    return "sk-live"


@pytest.fixture
def posted(monkeypatch):
    """Capture the request the key probe makes instead of standing up a provider."""
    seen: dict = {}

    class _Client:
        def __init__(self, timeout=None):
            seen["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, json=None):
            seen["url"] = url
            seen["headers"] = headers
            seen["json"] = json
            class _R:
                status_code = seen["status"]
            return _R()

    monkeypatch.setattr(av.httpx, "AsyncClient", _Client)
    return seen


@pytest.mark.anyio
async def test_a_rejected_key_is_a_verdict(posted):
    posted["status"] = 401
    assert await av.probe_key_accepted("https://ollama.com", "sk-dead", "gemma4:31b") is False


@pytest.mark.anyio
async def test_an_accepted_key_is_accepted(posted):
    posted["status"] = 200
    assert await av.probe_key_accepted("https://ollama.com", "sk-live", "gemma4:31b") is True


@pytest.mark.anyio
async def test_a_server_error_is_not_a_verdict(posted):
    """A 503 says nothing about the key — the honest answer is "unknown", not "rejected"."""
    posted["status"] = 503
    assert await av.probe_key_accepted("https://ollama.com", "sk", "m") is None


@pytest.mark.anyio
async def test_no_model_named_means_no_call(posted):
    assert await av.probe_key_accepted("https://ollama.com", "sk", "") is None
    assert "url" not in posted, "nothing should have been sent"


@pytest.mark.anyio
async def test_the_probe_uses_the_one_gated_path_and_caps_the_output(posted):
    posted["status"] = 200
    await av.probe_key_accepted("https://ollama.com", "sk-live", "gemma4:31b")

    assert posted["url"].endswith("/api/chat")
    assert posted["headers"]["Authorization"] == "Bearer sk-live"
    assert posted["json"]["options"]["num_predict"] == 1
    assert posted["json"]["stream"] is False


@pytest.mark.anyio
async def test_a_refusal_reads_as_configuration_not_an_outage(monkeypatch):
    """The state the badge and the pre-turn refusal read has to send the reader to the key."""

    async def _listing(base_url, path, headers=None):
        return {"data": [{"id": "gemma4:31b"}]}

    async def _refused(base_url, key, model):
        return False

    monkeypatch.setattr(av, "probe_json", _listing)
    monkeypatch.setattr(av, "probe_key_accepted", _refused)

    reading = await av._probe_cloud(PROVIDER, _key_for, verify_key=True)

    assert reading.state == av.STATE_UNCONFIGURED
    assert reading.key_accepted is False
    assert "REJECTED" in reading.reason
    assert av.test_card(reading, "Ollama Cloud")["status"] == "not_configured"


@pytest.mark.anyio
async def test_an_accepted_key_says_so_on_the_card(monkeypatch):
    async def _listing(base_url, path, headers=None):
        return {"data": [{"id": "gemma4:31b"}]}

    async def _accepted(base_url, key, model):
        return True

    monkeypatch.setattr(av, "probe_json", _listing)
    monkeypatch.setattr(av, "probe_key_accepted", _accepted)

    reading = await av._probe_cloud(PROVIDER, _key_for, verify_key=True)

    assert reading.state == av.STATE_AVAILABLE
    assert reading.key_accepted is True
    card = av.test_card(reading, "Ollama Cloud")
    assert card["status"] == "connected"
    assert "API key accepted" in card["message"]


@pytest.mark.anyio
async def test_a_page_read_never_spends_an_inference_request(monkeypatch):
    """`verify_key` is off by default, and that default is the whole point of the flag."""
    called: list = []

    async def _listing(base_url, path, headers=None):
        return {"data": [{"id": "gemma4:31b"}]}

    async def _key_probe(*args, **kwargs):
        called.append(args)
        return True

    monkeypatch.setattr(av, "probe_json", _listing)
    monkeypatch.setattr(av, "probe_key_accepted", _key_probe)

    reading = await av._probe_cloud(PROVIDER, _key_for)

    assert called == [], "an availability read must not run a completion"
    assert reading.key_accepted is None
    assert reading.state == av.STATE_AVAILABLE
