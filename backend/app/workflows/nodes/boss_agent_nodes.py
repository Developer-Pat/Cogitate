"""
BossAgent Workflow Nodes.

Nodes for the BossAgent document organization pipeline:
1. boss_dispatch_node — Analyzes file list, decides batch strategy
2. batch_workers_node — Runs File Clerk (summarize + classify) per batch
3. boss_merge_node — LLM merges overlapping categories from all batches

The BossAgent orchestrates File Clerk classification at scale by:
- Batching large file sets (avoids LLM attention dilution)
- Using a higher-powered LLM (Nemotron) for orchestration decisions
- Reusing File Clerk nodes as batch workers
"""

import logging
import os
from datetime import datetime, UTC
from typing import Any, cast

from ..state.workflow_state import WorkflowState, RunMetadata
from .file_clerk_nodes import (
    summarize_all_node,
    classify_subjects_node,
)

logger = logging.getLogger(__name__)

# Batch size limits
MIN_FILES_FOR_BATCHING = 15  # Below this, single-pass is fine
MAX_BATCH_SIZE = 12  # Files per batch for worker nodes


# ---------------------------------------------------------------------------
# Node 1: Boss Dispatch
# ---------------------------------------------------------------------------


def boss_dispatch_node(state: WorkflowState) -> dict:
    """
    Analyze the file list and decide on batch strategy.

    Uses file count alone to decide batching. No file reading,
    no LLM calls for dispatch planning — just structural decisions.
    """
    if _check_cancellation(state):
        logger.warning("Workflow cancelled before boss_dispatch")
        return _cancelled_state(state, 0)

    outputs = state.get("outputs", {}) or {}
    file_list = outputs.get("file_list", [])
    sandbox = outputs.get("sandbox_path", _get_sandbox_path(state))

    if not file_list:
        return _error_state(state, "No files found for BossAgent dispatch", "boss_dispatch")

    total = len(file_list)
    logger.info(f"📋 Boss dispatch: {total} files found")

    if total < MIN_FILES_FOR_BATCHING:
        logger.info(f"  ℹ️  {total} < {MIN_FILES_FOR_BATCHING} — using single-pass (File Clerk mode)")
        batch_plan = {
            "strategy": "single",
            "total_files": total,
            "batches": [{"batch_id": 1, "files": file_list}],
        }
    else:
        # Pure count-based sequential batching — no LLM, no file reading
        # F1 (2026-08-23): batch_size from the template config (the
        # user's knob — the poke profile uses 3; the full run 12).
        _cfg = state.get("metadata")
        _ccfg = _cfg.config if _cfg and hasattr(_cfg, "config") and _cfg.config else {}
        _batch_size = int(_ccfg.get("batch_size", MAX_BATCH_SIZE))
        num_batches = (total + _batch_size - 1) // _batch_size
        logger.info(f"  📦 Creating {num_batches} batches of max {_batch_size} files")

        batch_plan = {
            "strategy": "batched",
            "total_files": total,
            "batches": [],
        }
        for i in range(0, total, _batch_size):
            chunk = file_list[i:i + _batch_size]
            batches: list[dict[str, Any]] = batch_plan["batches"]  # type: ignore[assignment]
            batches.append({
                "batch_id": len(batches) + 1,
                "files": chunk,
            })
        for batch in batch_plan["batches"]:  # type: ignore[attr-defined]
            logger.info(f"    Batch {batch['batch_id']}: {len(batch['files'])} files")

    # Store in outputs
    from ..nodes.file_clerk_nodes import _merge_outputs
    merged = _merge_outputs(outputs, {"batch_plan": batch_plan, "sandbox_path": sandbox})

    return {
        "outputs": merged,
        "current_step": "batch_workers",
        "execution_result": {
            "step": "boss_dispatch",
            "strategy": batch_plan["strategy"],
            "total_files": total,
            "num_batches": len(list(batch_plan.get("batches", []))),  # type: ignore[call-overload]
        },
    }


# ---------------------------------------------------------------------------
# Node 2: Batch Workers
# ---------------------------------------------------------------------------

def _journal(path: str | None, record: dict) -> None:
    """Append one JSONL row to the run journal.

    THE RUN JOURNAL (2026-09-10): a fan-out over hundreds of batches is
    unreadable as console output and unrecoverable after the fact. One
    JSON line per batch (plus the run bookends) makes the post-run
    analysis trivial. Failures here are logged, never raised — the
    journal is an observer, not part of the pipeline.
    """
    if not path:
        return
    try:
        import json as _json
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(_json.dumps(record, default=str) + "\n")
    except Exception as e:  # noqa: BLE001
        logger.error(f"  ❌ journal write failed: {e}")


def batch_workers_node(state: WorkflowState) -> dict:
    """
    Run File Clerk (summarize + classify) for each batch.

    For each batch, creates a mini WorkflowState, runs summarize_all_node
    and classify_subjects_node, then collects the classification result.
    """
    if _check_cancellation(state):
        logger.warning("Workflow cancelled before batch_workers")
        return _cancelled_state(state, 0)

    if _previous_step_failed(state):
        exec_result = state.get("execution_result") or {}
        logger.warning(f"Skipping batch_workers — previous step failed: {exec_result.get('error', 'unknown')}")
        return {
            "execution_result": exec_result,
            "current_step": None,
        }

    outputs = state.get("outputs", {}) or {}
    batch_plan = outputs.get("batch_plan", {})
    file_list = outputs.get("file_list", [])
    sandbox = outputs.get("sandbox_path", _get_sandbox_path(state))

    if not batch_plan or "batches" not in batch_plan:
        return _error_state(state, "No batch plan available", "batch_workers")

    strategy = batch_plan.get("strategy", "batched")
    batches = batch_plan["batches"]

    # If single-pass, just run summarize + classify on all files directly
    if strategy == "single":
        logger.info("📝 Single-pass mode: running File Clerk directly")

        # Build a mini-state for the full file list
        mini_state = cast(WorkflowState, {
            "workflow_id": state["workflow_id"],
            "template_id": state["template_id"],
            "outputs": {"file_list": file_list, "sandbox_path": sandbox},
            "current_step": "summarize_all",
        })

        # Run summarize
        summary_result = summarize_all_node(mini_state)
        if summary_result.get("execution_result") and "error" in summary_result["execution_result"]:
            return _error_state(state, f"Summarize failed: {summary_result['execution_result'].get('error', 'unknown')}", "batch_workers")

        # Run classify
        classify_state = cast(WorkflowState, {
            "workflow_id": state["workflow_id"],
            "template_id": state["template_id"],
            "outputs": summary_result.get("outputs", {}),
            "current_step": "classify_subjects",
        })
        classify_result = classify_subjects_node(classify_state)
        if classify_result.get("execution_result") and "error" in classify_result["execution_result"]:
            return _error_state(state, f"Classification failed: {classify_result['execution_result'].get('error', 'unknown')}", "batch_workers")

        classification = classify_result.get("outputs", {}).get("classification", {})
        logger.info(f"✅ Single-pass complete: {len(classification)} categories")

        from ..nodes.file_clerk_nodes import _merge_outputs
        merged = _merge_outputs(outputs, {
            "classification": classification,
            "batch_results": [{"batch_id": 1, "classification": classification}],
        })

        return {
            "outputs": merged,
            "current_step": "boss_merge",
            "execution_result": {
                "step": "batch_workers",
                "batches_processed": 1,
                "strategy": "single",
            },
        }

    # Batched mode: run batches in parallel using thread pool
    logger.info(f"🔄 Processing {len(batches)} batches in parallel...")

    def _process_one_batch(batch: dict, worker_fn=None, total_batches: int | None = None) -> dict:
        """Process a single batch in its own thread.

        THE FAN-OUT GENERALIZATION (2026-08-23, the tag-survey):
        the worker is PLUGGABLE — the workflow declares the worker
        function via the state's worker_fn channel (a dotted name);
        the default is the File Clerk pair (summarize + classify).
        The tag-survey workers extract frontmatter tags instead.
        """
        batch_id = batch["batch_id"]
        batch_files = batch["files"]

        logger.info(f"  📦 Processing batch {batch_id} ({len(batch_files)} files)...")

        if worker_fn is not None:
            # The pluggable worker: one call, returns the tag rows.
            try:
                result = worker_fn({
                    "workflow_id": state["workflow_id"],
                    "template_id": state["template_id"],
                    "outputs": {"file_list": batch_files, "sandbox_path": sandbox},
                    "current_step": "tag_extract",
                })
                tag_rows = result.get("outputs", {}).get("tag_rows", [])
                # THE PROVENANCE PASS-THROUGH (2026-08-23): the worker's
                # worker_meta (llm_fired/llm_rows) was DROPPED here —
                # the collector counted 0 LLM rows despite the log
                # showing llm_fired=True. The meta rides with the rows.
                worker_meta = result.get("outputs", {}).get("worker_meta", {})
                logger.info(f"  ✅ Batch {batch_id}: {len(tag_rows)} tag rows")

                # PHASE C — THE BATCH:DONE EVENT (2026-08-24): the
                # fan-out's progress on the bus — the SSE stream shows
                # each batch completing live. The row count is the
                # payload; the workflow_id comes from the state.
                try:
                    from app.domain.messaging.services import publish
                    publish(f"batch:{batch_id}:done", {
                        "batch_id": batch_id,
                        "rows": len(tag_rows),
                        "workflow_id": state.get("workflow_id"),
                        # THE ESTIMATE DATA (Phase F2, 2026-08-24):
                        # total_batches lets the frontend compute
                        # done/total + the remaining estimate from
                        # the batch:done timestamps.
                        "total_batches": total_batches or 0,
                    })
                except Exception as _e:
                    logger.error(f"  ❌ batch:done publish failed: {_e}")

                return {"batch_id": batch_id, "tag_rows": tag_rows, "worker_meta": worker_meta}
            except Exception as e:
                logger.error(f"  ❌ Batch {batch_id} worker threw: {e}")
                return {"batch_id": batch_id, "error": str(e), "step": "tag_extract"}

        # Build mini-state for this batch
        mini_state = cast(WorkflowState, {
            "workflow_id": state["workflow_id"],
            "template_id": state["template_id"],
            "outputs": {"file_list": batch_files, "sandbox_path": sandbox},
            "current_step": "summarize_all",
        })

        # Run summarize
        summary_result = summarize_all_node(mini_state)
        if summary_result.get("execution_result") and "error" in summary_result["execution_result"]:
            err = summary_result["execution_result"].get("error", "unknown")
            logger.error(f"  ❌ Batch {batch_id} summarize failed: {err}")
            return {"batch_id": batch_id, "error": err, "step": "summarize"}

        # Run classify
        classify_state = cast(WorkflowState, {
            "workflow_id": state["workflow_id"],
            "template_id": state["template_id"],
            "outputs": summary_result.get("outputs", {}),
            "current_step": "classify_subjects",
        })
        classify_result = classify_subjects_node(classify_state)
        if classify_result.get("execution_result") and "error" in classify_result["execution_result"]:
            err = classify_result["execution_result"].get("error", "unknown")
            logger.error(f"  ❌ Batch {batch_id} classify failed: {err}")
            return {"batch_id": batch_id, "error": err, "step": "classify"}

        classification = classify_result.get("outputs", {}).get("classification", {})
        logger.info(f"  ✅ Batch {batch_id}: {len(classification)} categories")
        return {"batch_id": batch_id, "classification": classification}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_batch_results = []
    errors = []

    # THE PLUGGABLE WORKER (2026-08-23): the workflow's template
    # config can declare worker_fn (a dotted path) — resolved here
    # and passed to each batch thread. Default None = File Clerk.
    worker_fn = None
    _wf = state.get("metadata")
    _cfg = _wf.config if _wf and hasattr(_wf, "config") and _wf.config else {}
    _wf_name = _cfg.get("worker_fn")
    if _wf_name:
        try:
            import importlib
            _mod, _fn = _wf_name.rsplit(".", 1)
            worker_fn = getattr(importlib.import_module(_mod), _fn)
            logger.info(f"🧩 Worker fn: {_wf_name}")
        except Exception as e:
            logger.warning(f"⚠️  worker_fn {_wf_name} unresolved ({e}) — File Clerk default")

    # THE LOCAL-MODEL CONCURRENCY CAP (2026-08-23, the granite4
    # run): 44 parallel workers + a single local Ollama GPU = a
    # queue (Ollama processes requests serially) — the run hung on
    # contention. The template config can declare max_workers
    # (default: all batches for cloud APIs; local models should set
    # 1-2). The user's testing goal: a SUCCESSFUL run that really
    # uses the models and collates their output — serial beats hung.
    _max_workers = int(_cfg.get("max_workers", len(batches)))
    # F4 — THE LIMITED RUN (2026-08-23, the user's call): the
    # template config can declare max_batches — the run stops after
    # N batches (a smoke-before-full-run gate: 5-10 batches tell us
    # if the system works, no sense waiting for the full 44). The
    # partial results + a 'limited' flag flow to the collector.
    _max_batches = int(_cfg.get("max_batches", len(batches)))
    _limited = _max_batches < len(batches)
    if _limited:
        logger.info(f"🔀 LIMITED RUN: first {_max_batches} of {len(batches)} batches")
    _batches_run = batches[:_max_batches]

    # THE RUN JOURNAL (see _journal): config-declared, else a per-run file
    # under local/runs/ (untracked). One row per batch + the bookends.
    _journal_path = _cfg.get("journal_path") or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))),
        "local", "runs", f"fanout-{state.get('workflow_id') or 'unknown'}.jsonl",
    )
    _run_t0 = datetime.now(UTC)
    _journal(_journal_path, {
        "event": "run_start",
        "workflow_id": state.get("workflow_id"),
        "ts": _run_t0.isoformat(),
        "batches_total": len(batches),
        "batches_ran": len(_batches_run),
        "limited": _limited,
        "max_workers": _max_workers,
        # the batches carry their own file lists — derive rather than
        # assume a config key (the dispatch node's _batch_size is local
        # to it, and an invented name here crashed the first run)
        "batch_size": len(_batches_run[0].get("files", [])) if _batches_run else 0,
        "worker_fn": _wf_name,
        "journal": _journal_path,
    })
    logger.info(f"🧾 Run journal: {_journal_path}")

    # THE PAUSE STATE (2026-09-10, found by the full run): _delay was
    # re-read from config inside the loop, so the trickle halved 5->2.5
    # forever and never converged. It is carried here instead.
    _delay = float(_cfg.get("batch_delay_seconds", 0))
    _last_good_delay = _delay

    with ThreadPoolExecutor(max_workers=_max_workers) as executor:
        futures = {executor.submit(_process_one_batch, batch, worker_fn, len(_batches_run)): batch["batch_id"] for batch in _batches_run}
        for future in as_completed(futures):
            batch_id = futures[future]
            # `result` is read by the adaptive-pause block below (the
            # trickle's booted-detection), so it must be bound on every
            # path — a batch that THREW previously left it unbound and
            # crashed the node with UnboundLocalError (found by the
            # first trickle run). The except binds an error dict, which
            # is what the trickle wants to see anyway.
            result: dict = {}
            try:
                result = future.result()
                if "error" in result:
                    errors.append({"batch_id": batch_id, "error": result["error"], "step": result["step"]})
                else:
                    all_batch_results.append(result)
            except Exception as e:
                logger.error(f"  ❌ Batch {batch_id} threw exception: {e}")
                errors.append({"batch_id": batch_id, "error": str(e), "step": "unknown"})
                result = {"batch_id": batch_id, "error": str(e), "step": "unknown"}
            # the batch's journal row — timing, rows, tokens, chain
            # attempts, or the error. Written on every path.
            _wm = (result.get("worker_meta") or {}) if isinstance(result, dict) else {}
            _journal(_journal_path, {
                "event": "batch_done",
                "batch_id": batch_id,
                "ts": datetime.now(UTC).isoformat(),
                "ok": "error" not in result,
                "error": result.get("error"),
                "step": result.get("step"),
                "rows": len(result.get("tag_rows") or []),
                "usage": _wm.get("usage"),
                "llm_seconds": _wm.get("llm_seconds"),
                "served_by": _wm.get("served_by"),
                "attempts": _wm.get("attempts"),
                "mechanical": _wm.get("mechanical"),
            })
            # F5 — THE BATCH PAUSE (2026-08-23, the user's call):
            # the pause between completions makes the run an
            # INSPECTABLE sequence (watch batch 1's rows + the
            # log, then batch 2 fires). The poke profile: 20s
            # between minimal batches, watching free-LLM behavior
            # live. Only between completions, not the last.
            if batch_id != _batches_run[-1]["batch_id"]:
                # F6 — THE TRICKLE MODE (2026-08-23, the user's
                # call): the self-calibrating pause. Start with the
                # configured delay, HALVE it each batch; if a batch
                # gets booted (rate-limited / 502 / 429), restore
                # the last pause that worked and hold it. The goal:
                # find the fastest pause the free tier tolerates
                # without a full probe.
                _trickle = _cfg.get("trickle", False)
                if _trickle:
                    # THE BOOTED-DETECTION (2026-09-10, fixed after the full
                    # run): read the CHAIN's attempts, not only the batch
                    # error. The worker CATCHES a 429 and the fallback
                    # succeeds, so the batch reports ok while the free route
                    # was rate-limited — batches 22/23 hit exactly that and
                    # the pause never reacted.
                    _last_err = result.get("error", "") if isinstance(result, dict) else ""
                    _attempts = (result.get("worker_meta") or {}).get("attempts") or []
                    _step_errs = " ".join(
                        str(a.get("error", "")) for a in _attempts if not a.get("ok")
                    )
                    _signal = f"{_last_err} {_step_errs}".lower()
                    _booted = any(k in _signal for k in ("429", "502", "rate", "overload", "too many"))
                    if _booted:
                        # restore the last-good pause (double back)
                        _delay = max(_delay * 2, _last_good_delay)
                        logger.warning(
                            f"🐌  TRICKLE: booted ({_signal.strip()[:60]}) — "
                            f"restoring the pause to {_delay:.0f}s"
                        )
                    else:
                        # halve the pause (find the floor)
                        _last_good_delay = max(_delay, 1.0)
                        _delay = max(_delay / 2, 1.0)
                        logger.info(f"⏱  TRICKLE: halving the pause to {_delay:.1f}s (not booted)")
                if _delay > 0:
                    logger.info(f"⏸  Pausing {_delay:.1f}s before the next batch (batch {batch_id} done)")
                    import time as _t
                    _t.sleep(_delay)

    # Sort results by batch_id for consistent ordering
    all_batch_results.sort(key=lambda x: x["batch_id"])
    errors.sort(key=lambda x: x["batch_id"])

    if not all_batch_results:
        return _error_state(
            state,
            f"All {len(batches)} batches failed: {errors}",
            "batch_workers",
        )

    logger.info(f"✅ Batch workers complete: {len(all_batch_results)}/{len(batches)} batches succeeded")

    from ..nodes.file_clerk_nodes import _merge_outputs
    merged = _merge_outputs(outputs, {
        "batch_results": all_batch_results,
        "batch_errors": errors,
        "batch_limited": _limited,
        "batch_total": len(batches),
        "batch_ran": len(_batches_run),
    })

    return {
        "outputs": merged,
        "current_step": "boss_merge",
        "execution_result": {
            "step": "batch_workers",
            "batches_processed": len(all_batch_results),
            "batches_failed": len(errors),
            "strategy": strategy,
        },
    }


# ---------------------------------------------------------------------------
# Node 3: Boss Merge
# ---------------------------------------------------------------------------


def boss_merge_node(state: WorkflowState) -> dict:
    """
    Merge category classifications from all batches into a unified result.

    Pure dictionary merge — no LLM needed. Categories with identical names
    across batches get their file lists concatenated. Deduplicates files.
    For single-pass mode, this is a passthrough (no merge needed).
    """
    if _check_cancellation(state):
        logger.warning("Workflow cancelled before boss_merge")
        return _cancelled_state(state, 0)

    if _previous_step_failed(state):
        exec_result = state.get("execution_result") or {}
        logger.warning(f"Skipping boss_merge — previous step failed: {exec_result.get('error', 'unknown')}")
        return {
            "execution_result": exec_result,
            "current_step": None,
        }

    outputs = state.get("outputs", {}) or {}
    batch_results = outputs.get("batch_results", [])
    batch_plan = outputs.get("batch_plan", {})
    strategy = batch_plan.get("strategy", "unknown")

    if not batch_results:
        return _error_state(state, "No batch results available to merge", "boss_merge")

    # Single-pass: classification is already done, just pass through
    if strategy == "single":
        classification = outputs.get("classification", {})
        logger.info(f"📊 Single-pass: {len(classification)} categories (no merge needed)")
        return {
            "outputs": outputs,
            "current_step": "create_folders",
            "execution_result": {
                "step": "boss_merge",
                "categories": len(classification),
                "strategy": "single",
            },
        }

    # Batched mode: simple dictionary merge with deduplication
    logger.info(f"🔀 Merging categories from {len(batch_results)} batches...")

    merged_classification: dict[str, list[Any]] = {}
    for br in batch_results:
        for cat, files in br["classification"].items():
            if cat not in merged_classification:
                merged_classification[cat] = []
            for f in files:
                if f not in merged_classification[cat]:
                    merged_classification[cat].append(f)

    logger.info(f"📊 Merged classification: {len(merged_classification)} categories")
    for cat, files in merged_classification.items():
        logger.info(f"  📁 {cat}: {len(files)} files")

    from ..nodes.file_clerk_nodes import _merge_outputs
    merged_outputs = _merge_outputs(outputs, {
        "classification": merged_classification,
        "merged": True,
    })

    return {
        "outputs": merged_outputs,
        "current_step": "create_folders",
        "execution_result": {
            "step": "boss_merge",
            "categories": len(merged_classification),
            "strategy": "batched",
            "batches_merged": len(batch_results),
        },
    }



# ---------------------------------------------------------------------------
# Helpers (mirrored from file_clerk_nodes for self-containment)
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
            # defensive reads — a terminal-state builder must never raise
            workflow_id=state.get("workflow_id") or getattr(meta, "workflow_id", None) or "unknown",
            template_id=state.get("template_id") or getattr(meta, "template_id", None) or "unknown",
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
            # An error path must never raise. These read defensively
            # (flat key → metadata → "unknown"): a state missing the flat
            # ids crashed HERE and hid the original failure behind a
            # KeyError from the error handler itself (found by the
            # trickle run).
            workflow_id=state.get("workflow_id") or getattr(meta, "workflow_id", None) or "unknown",
            template_id=state.get("template_id") or getattr(meta, "template_id", None) or "unknown",
            started_at=getattr(meta, "started_at", None),
            completed_at=now,
            status="error",
            error=error,
            config=meta.config if hasattr(meta, "config") else None,
            tags=meta.tags if hasattr(meta, "tags") else None,
        ),
    }


def _get_sandbox_path(state: WorkflowState) -> str:
    """Get the sandbox path from workflow inputs."""
    inputs = state.get("inputs", {}) or {}
    return cast(str, inputs.get("folder_path", "/tmp/file-clerk-test"))
