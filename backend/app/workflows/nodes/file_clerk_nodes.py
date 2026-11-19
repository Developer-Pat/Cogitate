"""
File Clerk Workflow Nodes.

Nodes for the File Clerk document organization pipeline:
1. list_files_node — List markdown files in target folder
2. summarize_all_node — Summarize each file (parallel via sequential loop)
3. classify_subjects_node — LLM classifies files into categories
4. create_folders_node — Create category directories
5. move_files_node — Move files into their category folders

All file operations use the sandboxed tools (file-info, file-manager).
"""

import os
import json
import logging
import asyncio
from datetime import datetime, UTC
from typing import cast
from langchain_core.messages import HumanMessage, SystemMessage

from ..state.workflow_state import WorkflowState, RunMetadata

logger = logging.getLogger(__name__)


async def _execute_tool(tool_slug: str, config: dict, **kwargs):
    """Execute a tool via the ToolRegistry singleton."""
    from app.domain.tools.registry import ToolRegistry
    registry = ToolRegistry.get_instance()
    return await registry.execute_tool(tool_slug=tool_slug, tool_config=config, arguments=kwargs)


def _merge_outputs(existing: dict | None, new: dict) -> dict:
    """Merge new outputs into existing outputs."""
    merged = dict(existing) if existing else {}
    merged.update(new)
    return merged


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_cancellation(state: WorkflowState) -> bool:
    """Check if workflow has been cancelled."""
    try:
        from ..utils.cancellation import is_workflow_cancelled
        return is_workflow_cancelled(state["workflow_id"])
    except Exception:
        return False


def _previous_step_failed(state: WorkflowState) -> bool:
    """Check if the previous step resulted in an error."""
    exec_result = state.get("execution_result")
    if exec_result and isinstance(exec_result, dict) and "error" in exec_result:
        return True
    meta = state.get("metadata")
    if meta and hasattr(meta, "status") and meta.status == "error":
        return True
    if meta and isinstance(meta, dict) and meta.get("status") == "error":
        return True
    return False


def _cancelled_state(state: WorkflowState, elapsed: int = 0) -> dict:
    """Return state updates for a cancelled workflow."""
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    meta = state.get("metadata")
    return {
        "execution_result": {
            "result": "Cancelled",
            "elapsed_seconds": elapsed,
            "completed_at": now,
        },
        "current_step": None,
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=getattr(meta, "started_at", None),
            completed_at=now,
            status="cancelled",
            error="Cancelled by user",
            config=meta.config if hasattr(meta, "config") else None,
            tags=meta.tags if hasattr(meta, "tags") else None,
        ),
    }


def _error_state(state: WorkflowState, error: str, step: str) -> dict:
    """Return state updates for an error."""
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
            config=meta.config if hasattr(meta, "config") else None,
            tags=meta.tags if hasattr(meta, "tags") else None,
        ),
    }


def _get_sandbox_path(state: WorkflowState) -> str:
    """Get the sandbox base_path from inputs or template config."""
    inputs = state.get("inputs", {})
    folder_path = inputs.get("folder_path") or inputs.get("base_path")
    if folder_path:
        return cast(str, folder_path)
    # Fall back to template config
    meta = state.get("metadata")
    config = meta.config if hasattr(meta, "config") else (meta.get("config") if isinstance(meta, dict) else None)
    if config and config.get("base_path"):
        return cast(str, config["base_path"])
    # Last resort default
    return "/tmp/file-clerk-test"


# ---------------------------------------------------------------------------
# Node 1: List Files
# ---------------------------------------------------------------------------

def list_files_node(state: WorkflowState) -> dict:
    """
    List markdown files in the target sandbox folder.

    Uses the file-info tool (operation: list) to enumerate files.
    Stores the file list in outputs["file_list"].
    """
    if _check_cancellation(state):
        logger.warning("Workflow cancelled before list_files")
        return _cancelled_state(state, 0)

    sandbox = _get_sandbox_path(state)
    logger.info(f"📂 Listing files in sandbox: {sandbox}")

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _execute_tool(
                    "file-info",
                    {"base_path": sandbox, "max_depth": 1, "allow_symlinks": False},
                    operation="list",
                    path=sandbox,
                    show_hidden=False,
                )
            )
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"❌ list_files failed: {e}")
        return _error_state(state, f"Failed to list files: {e}", "list_files")

    # Extract file entries — result structure depends on file-info handler
    files = []
    if isinstance(result, dict):
        items = result.get("items") or result.get("files") or []
        for item in items:
            name = item.get("name", "")
            path = item.get("path", "")
            is_file = item.get("type") == "file" or item.get("is_file", False)
            if name.endswith(".md") and is_file:
                files.append({"name": name, "path": path})

    logger.info(f"📄 Found {len(files)} markdown files")

    outputs = _merge_outputs(state.get("outputs"), {"file_list": files, "sandbox_path": sandbox})

    return {
        "outputs": outputs,
        "current_step": "summarize_all",
        "execution_result": {"step": "list_files", "files_found": len(files)},
    }


# ---------------------------------------------------------------------------
# Node 2: Summarize All Files
# ---------------------------------------------------------------------------

def _read_file_content(file_path: str) -> str:
    """Read file content directly (bypassing tool for reading)."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.warning(f"Could not read {file_path}: {e}")
        return ""


async def _summarize_file(content: str, style: str = "brief") -> str:
    """Summarize file content using summarize-llm tool."""
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


def summarize_all_node(state: WorkflowState) -> dict:
    """
    Summarize every markdown file found in the list.

    Reads each file's content and calls summarize-llm.
    Stores summaries in outputs["summaries"] as {filename: summary}.
    """
    if _check_cancellation(state):
        logger.warning("Workflow cancelled before summarize_all")
        return _cancelled_state(state, 0)

    if _previous_step_failed(state):
        exec_result = state.get("execution_result") or {}
        logger.warning(f"Skipping summarize_all — previous step failed: {exec_result.get('error', 'unknown')}")
        return {
            "execution_result": exec_result,
            "current_step": None,
        }

    outputs = state.get("outputs", {}) or {}
    file_list = outputs.get("file_list", [])
    sandbox = outputs.get("sandbox_path", _get_sandbox_path(state))

    if not file_list:
        return _error_state(state, "No files found to summarize", "summarize_all")

    logger.info(f"📝 Summarizing {len(file_list)} files...")

    async def _summarize_all():
        summaries = {}

        async def _summarize_one(file_info: dict) -> tuple:
            """Summarize a single file, return (filename, summary)."""
            fname = file_info["name"]
            fpath = file_info["path"]
            if not os.path.isabs(fpath):
                fpath = os.path.join(sandbox, fpath)

            content = _read_file_content(fpath)
            if not content:
                return fname, "[Empty or unreadable file]"

            if _check_cancellation(state):
                logger.warning("Workflow cancelled during summarization")
                return fname, None

            summary = await _summarize_file(content, style="brief")
            logger.info(f"  ✅ Summarized: {fname}")
            return fname, summary

        # Fire all summaries concurrently — Ollama handles parallel requests
        tasks = [_summarize_one(fi) for fi in file_list]
        results = await asyncio.gather(*tasks)

        for fname, summary in results:
            if summary is not None:
                summaries[fname] = summary
        return summaries

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            summaries = loop.run_until_complete(_summarize_all())
        finally:
            loop.close()
    except Exception as e:
        logger.error(f"❌ summarize_all failed: {e}")
        return _error_state(state, f"Failed to summarize files: {e}", "summarize_all")

    outputs = _merge_outputs(state.get("outputs"), {"summaries": summaries})
    logger.info(f"✅ Summarized {len(summaries)} files")

    return {
        "outputs": outputs,
        "current_step": "classify_subjects",
        "execution_result": {"step": "summarize_all", "files_summarized": len(summaries)},
    }


# ---------------------------------------------------------------------------
# Node 3: Classify Subjects
# ---------------------------------------------------------------------------

CLASSIFICATION_PROMPT = """You are a document classifier. Your job is to analyze summaries of markdown files and GROUP them into a small number of logical subject categories.

CRITICAL INSTRUCTIONS:
- Your primary goal is GROUPING, not naming. Files that share topics, themes, or domains MUST go in the same category.
- Do NOT create one category per file. That defeats the purpose.
- Category names should describe the SUBJECT MATTER, not the filename. For example, "ai-ml" not "machine_learning_basics".
- Be creative with categories — don't just use "miscellaneous" as a catch-all. Try to find meaningful groupings even for diverse files.
- Example categories: "ai-ml", "programming", "cooking", "devops", "web-dev", "data-science", "productivity", "tips" — but use what fits the actual content.

Rules:
1. Create between 3 and 6 categories. Use enough categories to avoid a huge "miscellaneous" bucket.
2. Category names must be short, lowercase, and filesystem-safe (hyphens, no spaces).
3. Every file listed in the summaries MUST be assigned to exactly one category.
4. Count the files: make sure the total across all categories equals the number of files provided.
5. If a file truly doesn't fit anywhere, use "miscellaneous" — but try to find a home for every file first.
6. Return ONLY valid JSON — no preamble, no explanation, no markdown fences.

Format:
{
  "category-name-1": ["file1.md", "file2.md", "file3.md"],
  "category-name-2": ["file4.md", "file5.md"]
}

Here are the file summaries:
"""


def _get_llm():
    """Get LLM instance for classification.

    Uses llama3.2 for classification (better reasoning than phi4-mini).
    Falls back to DB default if llama3.2 is unavailable.
    """
    from app.domain.providers.llm_factory import get_llm_from_config
    from app.domain.providers.config_service import DefaultProviderService
    from app.core.database import AsyncSessionLocal
    from app.domain.providers.capabilities import NoProviderConfiguredError
    import asyncio
    import concurrent.futures

    async def _get_default_llm():
        async with AsyncSessionLocal() as db:
            default_service = DefaultProviderService()
            config = await default_service.get_default_provider(db)
            if config:
                return get_llm_from_config(config, temperature=0.0, max_tokens=2000)
            return None

    # Try llama3.2 first — better reasoning for classification
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model="llama3.2",
            base_url="http://localhost:11434",
            temperature=0.0,
            num_ctx=4096,
        )
    except Exception:
        logger.warning("llama3.2 not available, falling back to DB default")

    # Fall back to DB default
    try:
        try:
            asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _get_default_llm())
                llm = future.result()
        except RuntimeError:
            llm = asyncio.run(_get_default_llm())

        if llm is None:
            try:
                from langchain_openai import ChatOpenAI
                llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_tokens=2000)
            except Exception:
                raise NoProviderConfiguredError()

        return llm
    except NoProviderConfiguredError:
        raise
    except Exception as e:
        # No categorization: the honest report is the exception itself (the second organ this
        # phase retires — its "provider" was the client's class name, here with no client at all).
        logger.error(f"Failed to initialize LLM: {e}")
        raise


def classify_subjects_node(state: WorkflowState) -> dict:
    """
    Use LLM to classify file summaries into subject categories.

    Sends all summaries to LLM with a classification prompt.
    Stores classification in outputs["classification"] as {category: [files]}.
    """
    if _check_cancellation(state):
        logger.warning("Workflow cancelled before classify_subjects")
        return _cancelled_state(state, 0)

    if _previous_step_failed(state):
        exec_result = state.get("execution_result") or {}
        logger.warning(f"Skipping classify_subjects — previous step failed: {exec_result.get('error', 'unknown')}")
        return {
            "execution_result": exec_result,
            "current_step": None,
        }

    outputs = state.get("outputs", {}) or {}
    summaries = outputs.get("summaries", {})

    if not summaries:
        return _error_state(state, "No summaries available for classification", "classify_subjects")

    # Build the classification input
    summary_text = "\n\n".join(
        f"### {fname}\n{summary}" for fname, summary in summaries.items()
    )
    prompt = CLASSIFICATION_PROMPT + summary_text

    logger.info("🧠 Classifying files with LLM...")

    llm = _get_llm()
    classification = None
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response = loop.run_until_complete(
                    llm.ainvoke([
                        SystemMessage(content="You are a document classifier. Return ONLY valid JSON mapping category names to file lists."),
                        HumanMessage(content=prompt),
                    ])
                )
            finally:
                loop.close()

            # Parse JSON from response
            raw = response.content.strip()

            # Robust JSON extraction: handle markdown fences, text around JSON, etc.
            # Strategy 1: Try raw parse
            classification = None
            try:
                classification = json.loads(raw)
            except json.JSONDecodeError:
                pass

            # Strategy 2: Strip markdown code fences
            if classification is None:
                # Remove opening fence with optional language tag
                cleaned = raw
                if cleaned.startswith("```"):
                    first_nl = cleaned.index("\n")
                    cleaned = cleaned[first_nl + 1:]
                # Remove closing fence
                if cleaned.rstrip().endswith("```"):
                    last_backtick = cleaned.rfind("```")
                    cleaned = cleaned[:last_backtick].rstrip()
                cleaned = cleaned.strip()
                try:
                    classification = json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

            # Strategy 3: Find JSON block by searching for outermost braces
            if classification is None:
                start = raw.find("{")
                end = raw.rfind("}")
                if start != -1 and end != -1 and end > start:
                    json_block = raw[start:end + 1]
                    try:
                        classification = json.loads(json_block)
                    except json.JSONDecodeError:
                        pass

            if classification is None:
                logger.warning(f"⚠️ Attempt {attempt}/{max_attempts}: LLM returned invalid JSON (length {len(raw)} chars)")
                if attempt < max_attempts:
                    prompt += "\n\nERROR: Your previous response was not valid JSON. Please return ONLY a JSON object with category names as keys and file name arrays as values."
                continue

            # Parsed successfully
            logger.info(f"✅ Classification JSON parsed on attempt {attempt}/{max_attempts}")
            break

        except Exception as e:
            logger.warning(f"⚠️ Attempt {attempt}/{max_attempts}: LLM call failed: {e}")
            if attempt >= max_attempts:
                return _error_state(state, f"Classification failed after {max_attempts} attempts: {e}", "classify_subjects")

    if classification is None:
        logger.error(f"❌ LLM returned invalid JSON after {max_attempts} attempts")
        return _error_state(state, f"LLM classification returned invalid JSON after {max_attempts} attempts", "classify_subjects")

    logger.info(f"📊 Classification: {len(classification)} categories")
    for cat, files in classification.items():
        logger.info(f"  📁 {cat}: {len(files)} files")

    # Validate: ensure every file is classified
    all_summaries = set(summaries.keys())
    classified_files = set()
    for files in classification.values():
        classified_files.update(files)

    unclassified = all_summaries - classified_files
    if unclassified:
        logger.warning(f"⚠️ {len(unclassified)} file(s) not classified: {unclassified}")
        # Assign unclassified files to "miscellaneous"
        if "miscellaneous" not in classification:
            classification["miscellaneous"] = []
        classification["miscellaneous"].extend(list(unclassified))
        logger.info(f"  📁 miscellaneous: assigned {len(unclassified)} unclassified file(s)")

    # Double-check: any files still missing?
    classified_files = set()
    for files in classification.values():
        classified_files.update(files)
    still_missing = all_summaries - classified_files
    if still_missing:
        logger.error(f"❌ Still missing {len(still_missing)} files after fallback: {still_missing}")

    outputs = _merge_outputs(state.get("outputs"), {"classification": classification})

    return {
        "outputs": outputs,
        "current_step": "create_folders",
        "execution_result": {"step": "classify_subjects", "categories": len(classification)},
    }


# ---------------------------------------------------------------------------
# Node 4: Create Folders
# ---------------------------------------------------------------------------

def create_folders_node(state: WorkflowState) -> dict:
    """
    Create category directories in the sandbox folder.

    Uses file-manager tool (operation: mkdir) for each category.
    Stores created folders in outputs["created_folders"].
    """
    if _check_cancellation(state):
        logger.warning("Workflow cancelled before create_folders")
        return _cancelled_state(state, 0)

    if _previous_step_failed(state):
        exec_result = state.get("execution_result") or {}
        logger.warning(f"Skipping create_folders — previous step failed: {exec_result.get('error', 'unknown')}")
        return {
            "execution_result": exec_result,
            "current_step": None,
        }

    outputs = state.get("outputs", {}) or {}
    classification = outputs.get("classification", {})
    sandbox = outputs.get("sandbox_path", _get_sandbox_path(state))

    if not classification:
        return _error_state(state, "No classification data available", "create_folders")

    sandbox_config = {
        "base_path": sandbox,
        "dry_run": False,
    }

    created = []
    errors = []

    for category in classification.keys():
        folder_path = os.path.join(sandbox, category)
        logger.info(f"📁 Creating folder: {folder_path}")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    _execute_tool(
                        "file-manager",
                        sandbox_config,
                        operation="mkdir",
                        path=folder_path,
                        parents=True,
                    )
                )
            finally:
                loop.close()

            created.append(category)
            logger.info(f"  ✅ Created: {category}")
        except Exception as e:
            # Folder may already exist — that's OK
            if "exists" in str(e).lower():
                logger.info(f"  ℹ️  Folder already exists: {category}")
                created.append(category)
            else:
                logger.error(f"  ❌ Failed to create {category}: {e}")
                errors.append({"category": category, "error": str(e)})

    outputs = _merge_outputs(state.get("outputs"), {"created_folders": created, "folder_errors": errors})

    return {
        "outputs": outputs,
        "current_step": "move_files",
        "execution_result": {
            "step": "create_folders",
            "folders_created": len(created),
            "errors": errors,
        },
    }


# ---------------------------------------------------------------------------
# Node 5: Move Files
# ---------------------------------------------------------------------------

def move_files_node(state: WorkflowState) -> dict:
    """
    Move files into their assigned category folders.

    Uses file-manager tool (operation: move) for each file.
    Stores move results in outputs["move_results"].
    """
    if _check_cancellation(state):
        logger.warning("Workflow cancelled before move_files")
        return _cancelled_state(state, 0)

    if _previous_step_failed(state):
        exec_result = state.get("execution_result") or {}
        logger.warning(f"Skipping move_files — previous step failed: {exec_result.get('error', 'unknown')}")
        return {
            "execution_result": exec_result,
            "current_step": None,
        }

    outputs = state.get("outputs", {}) or {}
    classification = outputs.get("classification", {})
    sandbox = outputs.get("sandbox_path", _get_sandbox_path(state))

    if not classification:
        return _error_state(state, "No classification data available", "move_files")

    sandbox_config = {
        "base_path": sandbox,
        "dry_run": False,
    }

    moved = []
    errors = []

    for category, files in classification.items():
        dest_dir = os.path.join(sandbox, category)
        for fname in files:
            source = os.path.join(sandbox, fname)
            destination = os.path.join(dest_dir, fname)
            logger.info(f"📦 Moving: {fname} → {category}/{fname}")

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        _execute_tool(
                            "file-manager",
                            sandbox_config,
                            operation="move",
                            source=source,
                            destination=destination,
                        )
                    )
                finally:
                    loop.close()

                moved.append({"file": fname, "category": category, "status": "moved"})
                logger.info(f"  ✅ Moved: {fname}")
            except Exception as e:
                logger.error(f"  ❌ Failed to move {fname}: {e}")
                errors.append({"file": fname, "category": category, "error": str(e)})

    outputs = _merge_outputs(state.get("outputs"), {"move_results": {"moved": moved, "errors": errors}})

    # Build final summary
    total_files = sum(len(f) for f in classification.values())
    logger.info(f"✅ Moved {len(moved)}/{total_files} files into {len(classification)} categories")
    if errors:
        logger.warning(f"⚠️ {len(errors)} files failed to move")

    # Mark workflow complete
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    meta = state.get("metadata")

    return {
        "outputs": outputs,
        "current_step": None,
        "execution_result": {
            "step": "move_files",
            "files_moved": len(moved),
            "total_files": total_files,
            "categories": len(classification),
            "errors": errors,
            "completed_at": now,
        },
        "metadata": RunMetadata(
            workflow_id=state["workflow_id"],
            template_id=state["template_id"],
            started_at=getattr(meta, "started_at", None),
            completed_at=now,
            status="completed",
            config=meta.config if hasattr(meta, "config") else None,
            tags=meta.tags if hasattr(meta, "tags") else None,
        ),
    }
