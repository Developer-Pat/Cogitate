"""Tests for the Workspace Search tool (the findable-by-name front door).

Built 2026-09-10 with the search capability. It exists because search
shipped as an OPERATION on File Info first, and an agent asked to search
its workspace listed its tools, saw nothing named search, and correctly
reported the capability missing. The capability was there and could not
be found.

These tests pin the two things that make the second door safe: it
resolves the SAME sandbox as File Info (so it cannot be a way around the
containment), and it delegates rather than reimplements (so the two
surfaces cannot drift).
"""

from __future__ import annotations

import os

import pytest

from app.domain.tools.builtin.workspace_search_handler import WorkspaceSearchTool


@pytest.fixture
def workspace(tmp_path):
    """A tiny stand-in for an agent's workspace."""
    (tmp_path / "notes.md").write_text(
        "line one\n"
        "the BEAT sheet says hello\n"
        "line three\n",
        encoding="utf-8",
    )
    (tmp_path / "state.json").write_text('{"location": null}\n', encoding="utf-8")
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01NEEDLE\xff" * 16)
    return tmp_path


async def test_finds_matches_with_file_line_and_text(workspace):
    tool = WorkspaceSearchTool()
    r = await tool.execute({"base_path": str(workspace)}, pattern="hello")

    assert r["success"] is True
    assert r["count"] == 1
    assert r["truncated"] is False
    match = r["matches"][0]
    assert os.path.basename(match["file"]) == "notes.md"
    assert match["line"] == 2
    assert "hello" in match["text"]


async def test_ignore_case(workspace):
    tool = WorkspaceSearchTool()
    lower = await tool.execute({"base_path": str(workspace)}, pattern="beat")
    upper = await tool.execute(
        {"base_path": str(workspace)}, pattern="beat", ignore_case=True
    )

    assert lower["count"] == 0, "the workspace text is upper-case BEAT"
    assert upper["count"] == 1


async def test_glob_filter(workspace):
    tool = WorkspaceSearchTool()
    only_json = await tool.execute(
        {"base_path": str(workspace)}, pattern="location", glob="*.json"
    )
    only_md = await tool.execute(
        {"base_path": str(workspace)}, pattern="location", glob="*.md"
    )

    assert only_json["count"] == 1
    assert only_md["count"] == 0


async def test_sandbox_refuses_absolute_path_outside(workspace):
    tool = WorkspaceSearchTool()
    r = await tool.execute({"base_path": str(workspace)}, pattern="root", path="/etc")

    assert r["success"] is False
    assert "outside the sandbox" in r["error"]


async def test_sandbox_refuses_traversal(workspace):
    tool = WorkspaceSearchTool()
    r = await tool.execute(
        {"base_path": str(workspace)}, pattern="x", path="../../../../etc"
    )

    assert r["success"] is False
    assert "outside the sandbox" in r["error"]


async def test_sandbox_refuses_symlink_escape(workspace):
    """A symlink inside the workspace pointing out of it must not be a door."""
    tool = WorkspaceSearchTool()
    link = workspace / "_escape"
    try:
        os.symlink("/etc", link)
    except OSError:
        pytest.skip("symlinks not available")

    r = await tool.execute({"base_path": str(workspace)}, pattern="root", path="_escape")

    assert r["success"] is False
    assert "outside the sandbox" in r["error"]


async def test_binary_file_does_not_break_the_search(workspace):
    tool = WorkspaceSearchTool()
    r = await tool.execute({"base_path": str(workspace)}, pattern=".")

    assert r["success"] is True
    assert r["count"] >= 1


async def test_cap_sets_truncated(workspace):
    tool = WorkspaceSearchTool()
    r = await tool.execute({"base_path": str(workspace)}, pattern=".", max_results=1)

    assert r["count"] == 1
    assert r["truncated"] is True


async def test_invalid_regex_is_a_clean_error(workspace):
    tool = WorkspaceSearchTool()
    r = await tool.execute({"base_path": str(workspace)}, pattern="[unclosed")

    assert r["success"] is False
    assert "Invalid regex" in r["error"]


async def test_missing_pattern_is_a_clean_error(workspace):
    tool = WorkspaceSearchTool()
    r = await tool.execute({"base_path": str(workspace)})

    assert r["success"] is False
    assert "pattern" in r["error"]


def test_shape_matches_what_the_registry_needs():
    """The registry + LLM surface contract, pinned."""
    tool = WorkspaceSearchTool()

    assert tool.slug == "search"
    assert tool.needs_workspace is True, "no workspace injection -> no sandbox"
    assert tool.capability == "file-read", "file-read is GRAS: default-on for agents"
    assert tool.arguments_schema["properties"], "a schema with no properties is useless"
    assert "required" in tool.arguments_schema
    # every documented parameter must be declared, or the model guesses
    for param in ("pattern", "path", "glob", "ignore_case", "max_results"):
        assert param in tool.arguments_schema["properties"]
