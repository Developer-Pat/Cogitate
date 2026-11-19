"""The jina_reader SIGNAL tests — the reader's own warnings, surfaced.

The service already tells a caller enough to detect a cached or partially
rendered page: a declared length in the response headers, and a `Warning:` line
in the markdown preamble. The handler used to keep only `content`, so a
truncated fetch came back as an unqualified SUCCESS (Bob's weather.com report,
2026-09-16).

The vendor shapes asserted here were captured live on 2026-09-26 against
r.jina.ai: `x-decompressed-content-length: 79388` beside a 79,388-byte body,
`x-usage-tokens: 21966`, and `Warning: This is a cached snapshot of the original
page, consider retry with caching opt-out.` as an inline body line.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.tools.builtin import jina_reader_handler as mod
from app.domain.tools.builtin.jina_reader_handler import (
    JinaReaderTool,
    _declared_length,
    _preamble_warning,
)

BODY = (
    "Title: Fog\n\nURL Source: https://example.com/fog\n\n"
    "Warning: This is a cached snapshot of the original page, consider retry with caching opt-out.\n\n"
    "Markdown Content:\n" + ("fog over cold water " * 12)
)


class _Resp:
    def __init__(self, text: str, headers: dict[str, str]) -> None:
        self.text, self.headers = text, headers

    def raise_for_status(self) -> None:
        return None


def _client(monkeypatch: pytest.MonkeyPatch, text: str, headers: dict[str, str]) -> None:
    class _AsyncClient:
        def __init__(self, *a: Any, **k: Any) -> None: ...

        async def __aenter__(self) -> "_AsyncClient":
            return self

        async def __aexit__(self, *a: Any) -> bool:
            return False

        async def get(self, *a: Any, **k: Any) -> _Resp:
            return _Resp(text, headers)

    monkeypatch.setattr(mod.httpx, "AsyncClient", _AsyncClient)


@pytest.mark.asyncio
async def test_surfaces_the_declared_length_usage_and_the_service_warning(monkeypatch):
    _client(
        monkeypatch,
        BODY,
        {"x-decompressed-content-length": str(len(BODY.encode())), "x-usage-tokens": "21966"},
    )
    r = await JinaReaderTool().execute({}, url="https://example.com/fog")
    assert r["success"] is True
    assert r["content_length"] == len(BODY)
    assert r["declared_length"] == len(BODY.encode())
    assert r["usage_tokens"] == 21966
    assert "cached snapshot" in r["warning"]
    assert "length_mismatch" not in r
    assert "PARTIALLY" in JinaReaderTool.description, "the description must warn the model"


@pytest.mark.asyncio
async def test_a_short_body_is_recorded_as_a_mismatch_not_a_silent_success(monkeypatch):
    """The whole point: a partial fetch used to look like a clean SUCCESS."""
    _client(monkeypatch, BODY, {"x-decompressed-content-length": str(len(BODY.encode()) + 5000)})
    r = await JinaReaderTool().execute({}, url="https://example.com/fog")
    assert r["success"] is True  # it IS a success ...
    assert r["length_mismatch"] == -5000  # ... but the disagreement is visible


@pytest.mark.asyncio
async def test_says_nothing_extra_when_the_service_says_nothing(monkeypatch):
    plain = "Title: x\n\nMarkdown Content:\n" + ("ordinary page text " * 8)
    _client(monkeypatch, plain, {})
    r = await JinaReaderTool().execute({}, url="https://example.com/plain")
    assert set(r) == {"success", "url", "content", "content_length"}


def test_a_warning_after_the_content_marker_is_page_text_not_a_warning():
    assert _preamble_warning("Title: x\n\nMarkdown Content:\nWarning: quoted page text") is None
    assert (
        _preamble_warning("Title: x\n\nWarning: cached snapshot\n\nMarkdown Content:\nbody")
        == "cached snapshot"
    )


def test_declared_length_prefers_the_decompressed_figure():
    class R:
        headers = {"content-length": "22500", "x-decompressed-content-length": "79388"}

    assert _declared_length(R()) == 79388
    assert _declared_length(type("R2", (), {"headers": {"content-length": "367"}})()) == 367
    assert _declared_length(type("R3", (), {"headers": {}})()) is None
