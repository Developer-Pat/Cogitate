"""Stdout is captured while files, imports and network are blocked, and a timeout is enforced.

THE USER'S CALL: build it, see it in action, THEN decide the
liberty. This is the CONSERVATIVE baseline: safe preloads, the
restricted builtins, no file/network/import, a timeout, an output
cap.
"""

import pytest

from app.domain.tools.builtin.run_python_handler import RunPythonTool


@pytest.mark.asyncio
async def test_math_works():
    tool = RunPythonTool()
    r = await tool.execute({}, code="result = math.sqrt(144) + 6")
    assert r["success"] is True
    assert "18" in r["result"]


@pytest.mark.asyncio
async def test_statistics_and_text():
    tool = RunPythonTool()
    r = await tool.execute(
        {},
        code=(
            "data = [1, 2, 3, 4, 5]\n"
            "result = {'mean': statistics.mean(data), "
            "'reversed': ''.join(reversed('abc'))}"
        ),
    )
    assert r["success"] is True
    assert "'mean': 3" in r["result"]
    assert "'reversed': 'cba'" in r["result"]


@pytest.mark.asyncio
async def test_stdout_captured():
    tool = RunPythonTool()
    r = await tool.execute({}, code="print('hello from the sandbox')")
    assert r["success"] is True
    assert "hello from the sandbox" in r.get("stdout", "")


@pytest.mark.asyncio
async def test_no_file_access():
    tool = RunPythonTool()
    r = await tool.execute({}, code="result = open('/etc/hosts').read()")
    assert r["success"] is False
    assert "error_type" in r


@pytest.mark.asyncio
async def test_no_import_machinery():
    tool = RunPythonTool()
    r = await tool.execute({}, code="import os\nresult = os.getcwd()")
    assert r["success"] is False
    assert "error_type" in r


@pytest.mark.asyncio
async def test_no_network_modules():
    tool = RunPythonTool()
    r = await tool.execute({}, code="import requests\nresult = 1")
    assert r["success"] is False


@pytest.mark.asyncio
async def test_timeout():
    tool = RunPythonTool()
    r = await tool.execute({}, code="while True: pass")
    assert r["success"] is False
    assert r["error_type"] == "TimeoutError"


@pytest.mark.asyncio
async def test_script_error_reported():
    tool = RunPythonTool()
    r = await tool.execute({}, code="result = 1 / 0")
    assert r["success"] is False
    assert r["error_type"] == "ScriptError"
    assert "ZeroDivisionError" in r.get("error", "")


# ── the workspace-scoped read grant ──────────────────────────────


@pytest.mark.asyncio
async def test_grant_reads_workspace_files(tmp_path):
    (tmp_path / "data.txt").write_text("hello workspace")
    tool = RunPythonTool()
    r = await tool.execute(
        {"base_path": str(tmp_path)},
        code="result = read_file('data.txt')",
    )
    assert r["success"] is True
    assert "hello workspace" in r["result"]


@pytest.mark.asyncio
async def test_grant_lists_the_workspace(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    tool = RunPythonTool()
    r = await tool.execute(
        {"base_path": str(tmp_path)},
        code="result = list_dir()",
    )
    assert r["success"] is True
    assert "a.txt" in r["result"] and "b.txt" in r["result"]


@pytest.mark.asyncio
async def test_grant_blocks_path_traversal(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    work = tmp_path / "work"
    work.mkdir()
    tool = RunPythonTool()
    r = await tool.execute(
        {"base_path": str(work)},
        code="result = read_file('../outside.txt')",
    )
    assert r["success"] is False
    assert "PermissionError" in r.get("error", "")


@pytest.mark.asyncio
async def test_no_base_path_stays_closed(tmp_path):
    (tmp_path / "data.txt").write_text("x")
    tool = RunPythonTool()
    r = await tool.execute(
        {},  # no base_path — the sandbox stays fully closed
        code="result = read_file('data.txt')",
    )
    assert r["success"] is False
