"""
Context Indexer Workflow Nodes.

Nodes for building a searchable file index in SQLite:
1. indexer_scan_node — Scan folder, gather file metadata
2. indexer_summarize_node — Summarize all files in parallel
3. indexer_classify_node — Optional classification into categories
4. indexer_store_node — Write results to SQLite database

The indexer reuses the BossAgent parallelization pattern but outputs
a SQLite database instead of reorganizing files.
"""

import os
import json
import sqlite3
import logging
import asyncio
from datetime import datetime, UTC
from typing import cast

from ..state.workflow_state import WorkflowState, RunMetadata

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_cancellation(state: WorkflowState) -> bool:
    try:
        from ..utils.cancellation import is_workflow_cancelled
        return is_workflow_cancelled(state["workflow_id"])
    except Exception:
        return False


def _previous_step_failed(state: WorkflowState) -> bool:
    exec_result = state.get("execution_result")
    if exec_result and isinstance(exec_result, dict) and "error" in exec_result:
        return True
    return False


def _error_state(state: WorkflowState, error: str, step: str) -> dict:
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    meta = state.get("metadata")
    return {
        "execution_result": {"error": error, "failed_at_step": step},
        "current_step": None,
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=getattr(meta, "started_at", None),
            completed_at=now,
            status="error",
            error=error,
        ),
    }


def _merge_outputs(existing: dict | None, new: dict) -> dict:
    merged = dict(existing) if existing else {}
    merged.update(new)
    return merged


def _get_target_path(state: WorkflowState) -> str:
    inputs = state.get("inputs", {}) or {}
    return cast(str, inputs.get("folder_path", "/tmp/boss-agent-test"))


def _read_file_content(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return ""


def _get_file_stat(file_path: str) -> dict:
    """Get file metadata including creation and modification times."""
    try:
        st = os.stat(file_path)
        # Linux: ctime is metadata change time, birth time may not be available
        # Use st_birthtime on macOS, fall back to st_ctime on Linux
        created_at = getattr(st, 'st_birthtime', st.st_ctime)
        return {
            "file_size": st.st_size,
            "created_at": datetime.fromtimestamp(created_at).isoformat(),
            "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
        }
    except Exception:
        return {"file_size": 0, "created_at": None, "modified_at": None}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _init_db(db_path: str):
    """Create the context index database schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL UNIQUE,
            file_size INTEGER DEFAULT 0,
            created_at TEXT,
            modified_at TEXT,
            category TEXT,
            display_order INTEGER DEFAULT 999,
            tags TEXT,
            summary TEXT,
            checksum TEXT,
            indexed_at TEXT
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_category ON file_index(category)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_display_order ON file_index(display_order)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_file_name ON file_index(file_name)
    """)
    conn.commit()
    conn.close()


def _store_files(db_path: str, records: list[dict]):
    """Batch insert or update file index records."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    indexed_at = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    for rec in records:
        cursor.execute("""
            INSERT INTO file_index (
                file_name, file_path, file_size, created_at, modified_at,
                category, display_order, tags, summary, checksum, indexed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_name=excluded.file_name,
                file_size=excluded.file_size,
                modified_at=excluded.modified_at,
                category=excluded.category,
                display_order=excluded.display_order,
                tags=excluded.tags,
                summary=excluded.summary,
                checksum=excluded.checksum,
                indexed_at=excluded.indexed_at
        """, (
            rec["file_name"],
            rec["file_path"],
            rec.get("file_size", 0),
            rec.get("created_at"),
            rec.get("modified_at"),
            rec.get("category", "unclassified"),
            rec.get("display_order", 999),
            json.dumps(rec.get("tags", [])) if isinstance(rec.get("tags"), list) else rec.get("tags", "[]"),
            rec.get("summary", ""),
            rec.get("checksum", ""),
            indexed_at,
        ))

    conn.commit()
    count = cursor.execute("SELECT COUNT(*) FROM file_index").fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------------------
# Node 1: Scan Files
# ---------------------------------------------------------------------------

def indexer_scan_node(state: WorkflowState) -> dict:
    """
    Scan target folder for markdown files. Collects metadata for each file.
    """
    if _check_cancellation(state):
        return {"current_step": None, "execution_result": {"result": "Cancelled"}}

    target = _get_target_path(state)
    logger.info(f"📂 Scanning for files in: {target}")

    if not os.path.isdir(target):
        return _error_state(state, f"Target folder does not exist: {target}", "scan")

    file_list = []
    for root, _dirs, files in os.walk(target):
        for fname in sorted(files):
            if fname.lower().endswith(".md"):
                fpath = os.path.join(root, fname)
                # Skip files already in subfolders if we want flat scan
                rel_path = os.path.relpath(fpath, target)
                stats = _get_file_stat(fpath)
                file_list.append({
                    "name": fname,
                    "path": fpath,
                    "rel_path": rel_path,
                    **stats,
                })

    logger.info(f"📄 Found {len(file_list)} markdown files")

    outputs = _merge_outputs(state.get("outputs"), {
        "file_list": file_list,
        "target_path": target,
    })

    return {
        "outputs": outputs,
        "current_step": "indexer_summarize",
        "execution_result": {"step": "scan", "files_found": len(file_list)},
    }


# ---------------------------------------------------------------------------
# Node 2: Summarize All (Parallel)
# ---------------------------------------------------------------------------

async def _summarize_file(content: str, style: str = "brief") -> str:
    """Summarize file content using summarize-llm tool."""
    from .file_clerk_nodes import _execute_tool
    try:
        result = await _execute_tool(
            "summarize-llm",
            {"model": "ollama/llama3.2", "max_tokens": 1000, "temperature": 0.3},
            content=content,
            style=style,
        )
        if isinstance(result, dict):
            summary = result.get("summary") or result.get("result")
            return str(summary) if summary is not None else str(result)
        return str(result)
    except Exception as e:
        logger.warning(f"Summarization failed: {e}")
        return f"[Summarization failed: {e}]"


def indexer_summarize_node(state: WorkflowState) -> dict:
    """
    Summarize all files in parallel using asyncio.gather().
    """
    if _check_cancellation(state):
        return {"current_step": None, "execution_result": {"result": "Cancelled"}}

    if _previous_step_failed(state):
        return {"execution_result": state.get("execution_result"), "current_step": None}

    # Ensure tools are registered (needed when running outside the FastAPI app)
    from app.domain.tools.registry import init_default_registry
    init_default_registry()

    outputs = state.get("outputs", {}) or {}
    file_list = outputs.get("file_list", [])

    if not file_list:
        return _error_state(state, "No files found to summarize", "summarize")

    logger.info(f"📝 Summarizing {len(file_list)} files in batches of 10...")

    async def _summarize_one(file_info: dict) -> dict:
        content = _read_file_content(file_info["path"])
        if not content:
            return {**file_info, "summary": "[Empty or unreadable file]"}
        summary = await _summarize_file(content, style="brief")
        logger.info(f"  ✅ Summarized: {file_info['name']}")
        return {**file_info, "summary": summary}

    # Batched parallelism: process files in groups of BATCH_SIZE
    # Prevents overwhelming the LLM provider when indexing 100+ files
    BATCH_SIZE = 10
    results = []

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for i in range(0, len(file_list), BATCH_SIZE):
                batch = file_list[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                total_batches = (len(file_list) + BATCH_SIZE - 1) // BATCH_SIZE
                logger.info(f"  📦 Batch {batch_num}/{total_batches} ({len(batch)} files)")
                tasks = [_summarize_one(fi) for fi in batch]
                batch_results = loop.run_until_complete(asyncio.gather(*tasks))
                results.extend(batch_results)
        finally:
            loop.close()
    except Exception as e:
        return _error_state(state, f"Failed to summarize files: {e}", "summarize")

    summaries = {r["name"]: r.get("summary", "") for r in results}
    outputs = _merge_outputs(outputs, {"summaries": summaries, "file_records": results})
    logger.info(f"✅ Summarized {len(summaries)} files")

    return {
        "outputs": outputs,
        "current_step": "indexer_classify",
        "execution_result": {"step": "summarize", "files_summarized": len(summaries)},
    }


# ---------------------------------------------------------------------------
# Node 3: Classify (Reuses File Clerk logic)
# ---------------------------------------------------------------------------

def indexer_classify_node(state: WorkflowState) -> dict:
    """
    Classify files into categories. Reuses File Clerk classify_subjects_node.
    """
    if _check_cancellation(state):
        return {"current_step": None, "execution_result": {"result": "Cancelled"}}

    if _previous_step_failed(state):
        return {"execution_result": state.get("execution_result"), "current_step": None}

    outputs = state.get("outputs", {}) or {}
    summaries = outputs.get("summaries", {})
    file_records = outputs.get("file_records", [])

    if not summaries:
        return _error_state(state, "No summaries available for classification", "classify")

    # Build a mini-state for the File Clerk classify node
    classify_state = cast(WorkflowState, {
        "workflow_id": state["workflow_id"],
        "template_id": state["template_id"],
        "outputs": {"summaries": summaries},
        "current_step": "classify_subjects",
    })

    from .file_clerk_nodes import classify_subjects_node
    result = classify_subjects_node(classify_state)

    if result.get("execution_result") and "error" in result["execution_result"]:
        return _error_state(state, f"Classification failed: {result['execution_result'].get('error', 'unknown')}", "classify")

    classification = result.get("outputs", {}).get("classification", {})
    logger.info(f"📊 Classification: {len(classification)} categories")
    for cat, files in classification.items():
        logger.info(f"  📁 {cat}: {len(files)} files")

    # Assign categories to file records
    category_map = {}
    for cat, files in classification.items():
        for fname in files:
            category_map[fname] = cat

    for rec in file_records:
        rec["category"] = category_map.get(rec["name"], "unclassified")

    outputs = _merge_outputs(outputs, {
        "classification": classification,
        "file_records": file_records,
    })

    return {
        "outputs": outputs,
        "current_step": "indexer_store",
        "execution_result": {
            "step": "classify",
            "categories": len(classification),
        },
    }


# ---------------------------------------------------------------------------
# Node 4: Store in SQLite
# ---------------------------------------------------------------------------

def indexer_store_node(state: WorkflowState) -> dict:
    """
    Write file index records to SQLite database.
    Database is created in the target folder as 'context_index.db'.
    """
    if _check_cancellation(state):
        return {"current_step": None, "execution_result": {"result": "Cancelled"}}

    if _previous_step_failed(state):
        return {"execution_result": state.get("execution_result"), "current_step": None}

    outputs = state.get("outputs", {}) or {}
    file_records = outputs.get("file_records", [])
    target = outputs.get("target_path", _get_target_path(state))

    if not file_records:
        return _error_state(state, "No file records to store", "store")

    db_path = os.path.join(target, "context_index.db")

    # Remove existing DB to start fresh (like git reset for the index)
    if os.path.exists(db_path):
        os.remove(db_path)
        logger.info(f"🗑️  Removed existing index: {db_path}")

    logger.info(f"💾 Creating index database: {db_path}")
    _init_db(db_path)

    records = []
    for rec in file_records:
        # Simple checksum: mtime + size
        checksum = f"{rec.get('modified_at', '')}_{rec.get('file_size', 0)}"
        records.append({
            "file_name": rec["name"],
            "file_path": rec["path"],
            "file_size": rec.get("file_size", 0),
            "created_at": rec.get("created_at"),
            "modified_at": rec.get("modified_at"),
            "category": rec.get("category", "unclassified"),
            "tags": [],
            "summary": rec.get("summary", ""),
            "checksum": checksum,
        })

    total = _store_files(db_path, records)
    logger.info(f"✅ Indexed {total} files in {db_path}")

    outputs = _merge_outputs(outputs, {
        "db_path": db_path,
        "indexed_count": total,
    })

    return {
        "outputs": outputs,
        "current_step": None,
        "execution_result": {
            "step": "store",
            "db_path": db_path,
            "indexed_count": total,
        },
    }
