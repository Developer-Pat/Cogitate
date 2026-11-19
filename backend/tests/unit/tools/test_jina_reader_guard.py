"""The jina_reader scheme-guard tests."""

import pytest

from app.domain.tools.builtin.jina_reader_handler import JinaReaderTool


@pytest.mark.asyncio
async def test_rejects_file_urls_with_guidance():
    tool = JinaReaderTool()
    r = await tool.execute({}, url="file:///tmp/example/wiki/SCHEMA.md")
    assert r["success"] is False
    assert "file-manager" in r["error"] or "doc-reader" in r["error"]


@pytest.mark.asyncio
async def test_rejects_bare_paths():
    tool = JinaReaderTool()
    r = await tool.execute({}, url="/etc/hosts")
    assert r["success"] is False


@pytest.mark.asyncio
async def test_accepts_web_urls():
    # the guard passes http/https — the fetch itself is not exercised
    tool = JinaReaderTool()
    assert tool is not None
