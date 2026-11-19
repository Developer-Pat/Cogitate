"""The provider-manager's curated-model operations — the intake ritual as a tool call.

Every assertion here is about the REQUEST this tool puts on the wire: the endpoint,
the method, the body. The handler drives the app's own HTTP API (the same one a
person would use), so the request IS the contract — a wrong URL is a tool that
reports success while the row is unchanged, which is the class of failure this
whole arc exists to remove.

The vocabularies are pinned against their ONE home (`THINKING_LEVELS`,
`MODEL_LOCATIONS`, `CURATED_CATEGORIES`): the point is not that the schema has an
enum, it is that the schema cannot drift from what the API validates against.
"""

from typing import Any, List, Optional, Tuple

import httpx
import pytest

from app.domain.providers.curated_models_service import (
    CURATED_CATEGORIES,
    MODEL_LOCATIONS,
)
from app.domain.tools.builtin.provider_manager_handler import ProviderManagerTool
from app.services.cognitive_pipeline.reasoning_support import THINKING_LEVELS


class _FakeResponse:
    def __init__(self, payload: Any, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self) -> Any:
        return self._payload


class _FakeClient:
    """Records every call and answers with one canned response."""

    calls: List[Tuple[str, str, Optional[dict], Any]] = []
    response = _FakeResponse({"ok": True})

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    async def get(self, url: str, params: Optional[dict] = None, timeout: Any = None) -> _FakeResponse:
        type(self).calls.append(("GET", url, params, None))
        return type(self).response

    async def post(self, url: str, json: Any = None, timeout: Any = None) -> _FakeResponse:
        type(self).calls.append(("POST", url, json, None))
        return type(self).response


@pytest.fixture
def wire(monkeypatch):
    """Point the handler's httpx at the recorder, and hand the recorder back."""
    _FakeClient.calls = []
    _FakeClient.response = _FakeResponse({"ok": True})
    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    return _FakeClient


@pytest.mark.asyncio
async def test_schema_declares_the_curated_operations_and_one_vocabulary(wire) -> None:
    """The operations are offered, and the enums ARE the shared vocabularies.

    Retyping them here would pass a looser test and drift the moment the API's
    vocabulary moves — so the assertion is equality against the one home.
    """
    props = ProviderManagerTool.arguments_schema["properties"]

    assert set(props["operation"]["enum"]) >= {
        "curated-list", "curated-add", "curated-verify",
    }
    assert props["thinking"]["enum"] == list(THINKING_LEVELS)
    assert props["location"]["enum"] == list(MODEL_LOCATIONS)
    assert set(props["category"]["enum"]) == CURATED_CATEGORIES


@pytest.mark.asyncio
async def test_curated_list_reads_the_list_endpoint(wire) -> None:
    """No provider filter reads everything; a provider becomes the query param."""
    tool = ProviderManagerTool()

    result = await tool.execute("curated-list")
    assert result["success"] is True
    assert wire.calls == [
        ("GET", "http://localhost:8000/api/v1/curated-models", None, None),
    ]

    await tool.execute("curated-list", provider="openrouter")
    assert wire.calls[-1] == (
        "GET",
        "http://localhost:8000/api/v1/curated-models",
        {"provider": "openrouter"},
        None,
    )


@pytest.mark.asyncio
async def test_curated_add_posts_the_decided_facts(wire) -> None:
    """A 201 is success, and the body carries exactly what the intake decided."""
    wire.response = _FakeResponse({"id": 13, "model_id": "stealth/space-bunny-alpha"}, 201)
    tool = ProviderManagerTool()

    result = await tool.execute(
        "curated-add",
        provider="openrouter",
        model_id="stealth/space-bunny-alpha",
        model_name="Space Bunny Alpha",
        category="reasoning",
        thinking="mandatory",
        location="cloud",
        context_length=1000000,
    )

    assert result["success"] is True
    method, url, body, _ = wire.calls[-1]
    assert (method, url) == ("POST", "http://localhost:8000/api/v1/curated-models")
    assert body == {
        "provider": "openrouter",
        "model_id": "stealth/space-bunny-alpha",
        "model_name": "Space Bunny Alpha",
        "category": "reasoning",
        "context_length": 1000000,
        "thinking": "mandatory",
        "location": "cloud",
    }


@pytest.mark.asyncio
async def test_curated_add_omits_what_the_caller_did_not_state(wire) -> None:
    """Unstated fields are not invented — the row takes the app's own shape."""
    wire.response = _FakeResponse({"id": 14}, 201)
    tool = ProviderManagerTool()

    await tool.execute(
        "curated-add", provider="ollama", model_id="llama3.3", model_name="Llama 3.3",
    )

    body = wire.calls[-1][2]
    assert body == {
        "provider": "ollama",
        "model_id": "llama3.3",
        "model_name": "Llama 3.3",
    }


@pytest.mark.asyncio
async def test_curated_add_refuses_an_incomplete_call_before_the_wire(wire) -> None:
    """The three identity fields are required, and the refusal names the missing one."""
    tool = ProviderManagerTool()

    result = await tool.execute("curated-add", provider="openrouter")

    assert result["success"] is False
    assert "model_id" in result["error"] and "model_name" in result["error"]
    assert wire.calls == []


@pytest.mark.asyncio
async def test_curated_add_surfaces_the_apis_own_refusal(wire) -> None:
    """A 422 becomes the vocabulary sentence, not a wall of response text.

    The model is the reader here: "Unknown thinking level: 'high3'. Valid: …" tells
    it what to send instead, where a status code and a body dump do not.
    """
    wire.response = _FakeResponse(
        {"detail": [{"msg": "Value error, Unknown thinking level: 'high3'. Valid: none, low"}]},
        422,
    )
    tool = ProviderManagerTool()

    result = await tool.execute(
        "curated-add", provider="openrouter", model_id="x/y", model_name="X", thinking="high3",
    )

    assert result["success"] is False
    assert result["status"] == 422
    assert "Unknown thinking level" in result["error"]


@pytest.mark.asyncio
async def test_curated_verify_asks_our_record_by_default(wire) -> None:
    """`refresh` defaults off: our own record is the cheap read, and the answer dates it."""
    tool = ProviderManagerTool()

    await tool.execute("curated-verify", curated_id=12)
    assert wire.calls[-1] == (
        "POST",
        "http://localhost:8000/api/v1/curated-models/12/verify-window",
        {"refresh": False},
        None,
    )

    await tool.execute("curated-verify", curated_id=12, refresh=True)
    assert wire.calls[-1][2] == {"refresh": True}


@pytest.mark.asyncio
async def test_curated_verify_requires_a_row_id(wire) -> None:
    """No id, no call — and the refusal says which argument is missing."""
    tool = ProviderManagerTool()

    result = await tool.execute("curated-verify")

    assert result["success"] is False
    assert "curated_id" in result["error"]
    assert wire.calls == []


@pytest.mark.asyncio
async def test_an_unknown_operation_is_loud(wire) -> None:
    """The fall-through stays a named failure rather than a silent empty success."""
    tool = ProviderManagerTool()

    result = await tool.execute("curated-delete-everything")

    assert result == {
        "success": False,
        "error": "Unknown operation: curated-delete-everything",
    }
    assert wire.calls == []
