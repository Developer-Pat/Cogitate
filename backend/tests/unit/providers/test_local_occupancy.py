"""The local-occupancy service tests.

The classification: healthy / down-by-occupancy / down. The probes
are monkeypatched — no real daemons in the unit tests.
"""

import pytest

from app.domain.providers import availability
from app.domain.providers import local_occupancy_service as svc

# The fixture providers: ollama (local!) + llama.cpp (openai-typed,
# loopback = local per the class seam)
OLLAMA = {
    "id": 1, "name": "ollama", "display_name": "Ollama",
    "provider_type": "ollama", "base_url": "http://localhost:11434",
}
LLAMA = {
    "id": 6, "name": "llama", "display_name": "Llama Server",
    "provider_type": "openai", "base_url": "http://127.0.0.1:8080/v1",
}


class FakeClient:
    """A fake httpx.AsyncClient that answers per-provider."""

    def __init__(self, answers):
        # answers: {(base_url, path): dict or None}
        self._answers = answers

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url):
        # The service requests the DEDUPED probe URL — the answer
        # keys are full real URLs, so a regression to the doubled
        # /v1/v1 join leaves no answer and the test fails.
        for full_url, payload in self._answers.items():
            if url == full_url:
                if payload is None:
                    raise Exception("connection refused")
                return _FakeResponse(payload)
        raise Exception(f"no answer for {url}")

    async def __call__(self, *a, **k):
        return self


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_ollama_running_llama_swapped(monkeypatch):
    """ollama answers (phi4 loaded); llama.cpp silent -> occupancy."""
    answers = {
        "http://localhost:11434/api/tags": {"models": [{"name": "phi4-mini"}]},
        "http://localhost:11434/api/ps": {"models": [{"model": "phi4-mini:latest"}]},
    }
    monkeypatch.setattr(availability.httpx, "AsyncClient", lambda **kw: FakeClient(answers))
    result = await svc.get_local_occupancy([OLLAMA, LLAMA])
    states = {d["name"]: d["state"] for d in result["daemons"]}
    assert states["ollama"] == "healthy"
    assert states["llama"] == "down-by-occupancy"
    assert result["running"] == ["ollama"]
    loaded = next(d for d in result["daemons"] if d["name"] == "ollama")["loaded_models"]
    assert loaded == ["phi4-mini:latest"]


@pytest.mark.asyncio
async def test_nobody_running_all_down(monkeypatch):
    """No daemon answers -> the ownerless down for both."""
    answers = {
        "http://localhost:11434/api/tags": None,
        "http://127.0.0.1:8080/v1/models": None,
    }
    monkeypatch.setattr(availability.httpx, "AsyncClient", lambda **kw: FakeClient(answers))
    result = await svc.get_local_occupancy([OLLAMA, LLAMA])
    states = {d["name"]: d["state"] for d in result["daemons"]}
    assert states["ollama"] == "down"
    assert states["llama"] == "down"
    assert result["running"] == []


@pytest.mark.asyncio
async def test_llama_running_ollama_swapped(monkeypatch):
    """The reverse: llama.cpp serves the Bonsai GGUF, ollama is out."""
    answers = {
        "http://127.0.0.1:8080/v1/models": {"data": [{"id": "bonsai-8b"}]},
    }
    monkeypatch.setattr(availability.httpx, "AsyncClient", lambda **kw: FakeClient(answers))
    result = await svc.get_local_occupancy([OLLAMA, LLAMA])
    states = {d["name"]: d["state"] for d in result["daemons"]}
    assert states["llama"] == "healthy"
    assert states["ollama"] == "down-by-occupancy"
    assert result["running"] == ["llama"]
    loaded = next(d for d in result["daemons"] if d["name"] == "llama")["loaded_models"]
    assert loaded == ["bonsai-8b"]


def test_join_probe_url_v1_base_dedupes():
    """The litellm-style /v1 base + /v1 path -> ONE /v1 (the bug)."""
    assert availability.join_probe_url("http://127.0.0.1:8080/v1", "/v1/models") == \
        "http://127.0.0.1:8080/v1/models"
    assert availability.join_probe_url("http://127.0.0.1:8080/v1/", "/v1/models") == \
        "http://127.0.0.1:8080/v1/models"


def test_join_probe_url_plain_base_keeps_v1_path():
    """A base without the API root keeps the path's /v1."""
    assert availability.join_probe_url("http://host:8080", "/v1/models") == \
        "http://host:8080/v1/models"


def test_join_probe_url_ollama_paths_unaffected():
    """The /api/* paths never start with /v1 — untouched."""
    assert availability.join_probe_url("http://localhost:11434", "/api/tags") == \
        "http://localhost:11434/api/tags"
