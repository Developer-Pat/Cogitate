"""The File Info tool's `search` operation — sandboxed workspace grep.

Covers the doctrine-sensitive edges: a truncated result must say so, a
binary file must not abort the walk, and a path escaping the workspace
(including via symlink) must be refused rather than followed.
"""

import os

import pytest

from app.domain.tools.builtin.file_info_handler import FileInfoTool


@pytest.fixture
def tool():
    return FileInfoTool()


@pytest.fixture
def workspace(tmp_path):
    """A small fake agent workspace on disk."""
    (tmp_path / "notes.md").write_text(
        "Alpha line\nmarker here\nBeta line\n", encoding="utf-8"
    )
    (tmp_path / "data.json").write_text('{"key": "marker"}\n', encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "deep.txt").write_text("MARKER uppercase\nplain\n", encoding="utf-8")
    return tmp_path


def cfg(base):
    return {"base_path": str(base)}


@pytest.mark.asyncio
async def test_search_finds_match_with_file_line_text(tool, workspace):
    result = await tool.execute(cfg(workspace), operation="search", pattern="marker")

    assert result["success"] is True
    assert result["truncated"] is False
    assert result["count"] == 2
    text_matches = {(m["file"], m["line"], m["text"]) for m in result["matches"]}
    assert (str(workspace / "notes.md"), 2, "marker here") in text_matches
    assert (str(workspace / "data.json"), 1, '{"key": "marker"}') in text_matches


@pytest.mark.asyncio
async def test_search_ignore_case(tool, workspace):
    sensitive = await tool.execute(cfg(workspace), operation="search", pattern="marker")
    insensitive = await tool.execute(
        cfg(workspace), operation="search", pattern="marker", ignore_case=True
    )

    assert sensitive["count"] == 2
    # The uppercase MARKER in sub/deep.txt is only found case-insensitively.
    assert insensitive["count"] == 3
    assert any(m["file"].endswith("deep.txt") for m in insensitive["matches"])


@pytest.mark.asyncio
async def test_search_glob_filter(tool, workspace):
    result = await tool.execute(
        cfg(workspace), operation="search", pattern="marker", glob="*.md"
    )

    assert result["success"] is True
    assert result["count"] == 1
    assert result["matches"][0]["file"].endswith("notes.md")


@pytest.mark.asyncio
async def test_search_max_results_sets_truncated(tool, workspace):
    (workspace / "many.txt").write_text(
        "".join(f"hit {i}\n" for i in range(20)), encoding="utf-8"
    )

    result = await tool.execute(
        cfg(workspace), operation="search", pattern="hit", max_results=3
    )

    assert result["success"] is True
    assert result["count"] == 3
    assert result["truncated"] is True
    assert "note" in result
    assert "cap" in result["note"].lower()


@pytest.mark.asyncio
async def test_search_no_truncation_when_exactly_at_cap(tool, workspace):
    (workspace / "exact.txt").write_text("hit\nhit\n", encoding="utf-8")

    result = await tool.execute(
        cfg(workspace), operation="search", pattern="hit", max_results=2
    )

    assert result["count"] == 2
    assert result["truncated"] is False


@pytest.mark.asyncio
async def test_search_rejects_path_escaping_sandbox(tool, workspace, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    (outside / "secret.txt").write_text("marker\n", encoding="utf-8")

    result = await tool.execute(
        cfg(workspace), operation="search", pattern="marker", path=str(outside)
    )

    assert result["success"] is False
    assert "outside the sandbox" in result["error"]


@pytest.mark.asyncio
async def test_search_rejects_relative_traversal(tool, workspace):
    result = await tool.execute(
        cfg(workspace), operation="search", pattern="marker", path="../"
    )

    assert result["success"] is False
    assert "outside the sandbox" in result["error"]


@pytest.mark.asyncio
async def test_search_symlink_escape_is_not_followed(tool, workspace):
    outside = workspace.parent / "outside_ws"
    outside.mkdir(exist_ok=True)
    (outside / "leak.txt").write_text("marker-leak\n", encoding="utf-8")

    # A symlinked FILE inside the workspace pointing outside it...
    os.symlink(outside / "leak.txt", workspace / "linked.txt")
    # ...and a symlinked DIR inside the workspace pointing outside it.
    os.symlink(outside, workspace / "linked_dir")

    result = await tool.execute(
        cfg(workspace), operation="search", pattern="marker-leak"
    )

    assert result["success"] is True
    assert result["count"] == 0
    assert all("outside_ws" not in m["file"] for m in result["matches"])


@pytest.mark.asyncio
async def test_search_skips_binary_file_and_reports_it(tool, workspace):
    (workspace / "blob.bin").write_bytes(b"\x00\x01\x02zznib\x00\xff")
    (workspace / "text.txt").write_text("zznib\n", encoding="utf-8")

    result = await tool.execute(cfg(workspace), operation="search", pattern="zznib")

    assert result["success"] is True
    # The binary's "zznib" bytes are NOT matched; the text file still is.
    assert result["count"] == 1
    assert result["matches"][0]["file"].endswith("text.txt")
    assert result["skipped_binary"] == 1
    assert "Skipped files" in result["note"]


@pytest.mark.asyncio
async def test_search_invalid_regex_returns_clean_error(tool, workspace):
    result = await tool.execute(cfg(workspace), operation="search", pattern="(")

    assert result["success"] is False
    assert "Invalid regex" in result["error"]


@pytest.mark.asyncio
async def test_search_missing_pattern_returns_clean_error(tool, workspace):
    result = await tool.execute(cfg(workspace), operation="search")

    assert result["success"] is False
    assert "pattern" in result["error"]


@pytest.mark.asyncio
async def test_search_path_defaults_to_whole_workspace(tool, workspace):
    result = await tool.execute(cfg(workspace), operation="search", pattern="plain")

    assert result["success"] is True
    # `plain` lives only in sub/deep.txt — reachable without an explicit path.
    assert result["count"] == 1
    assert result["matches"][0]["file"].endswith("deep.txt")


@pytest.mark.asyncio
async def test_search_on_single_file(tool, workspace):
    result = await tool.execute(
        cfg(workspace),
        operation="search",
        pattern="marker",
        path=str(workspace / "notes.md"),
    )

    assert result["count"] == 1
    assert result["matches"][0]["file"].endswith("notes.md")


def test_search_schema_declares_every_parameter(tool):
    """The file-manager `write` bug guard: a param the model can pass must
    be declared in the schema, or the model invents a different key and
    silently passes nothing."""
    props = tool.arguments_schema["properties"]
    assert "search" in props["operation"]["enum"]
    for name in ("pattern", "glob", "ignore_case", "max_results", "path"):
        assert name in props, f"missing schema param: {name}"
