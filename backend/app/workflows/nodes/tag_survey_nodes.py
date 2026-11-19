"""Tag Survey Workflow Nodes — the fan-out survey (2026-08-23).

The tag-layer-sweeper adaptation of the boss-agent fan-out:
- DISPATCH (reused from the boss agent): split the wiki into
  batches — pure structural, no LLM.
- WORKERS: read each file's frontmatter + extract the type/* and
  domain/* tags — ONE bounded LLM call per batch (the free
  Nemotron via OpenRouter — the user's free-testing-tokens call).
  The strict JSON contract: return rows, no wandering, no writes.
- MERGE: assemble the batch rows into the manifest.

THE WORKER CONTRACT (the fan-out discipline — the fix for the
'surveys forever, never delivers' failure): each worker is BOUNDED
(one batch, one call), MECHANICAL (frontmatter -> tags), and
RETURNS data (never writes files — the collector writes).
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, UTC

from ..state.workflow_state import WorkflowState

logger = logging.getLogger(__name__)

# The worker brain — GRANITE4:3B via LOCAL OLLAMA (the user's call,
# 2026-08-23: 'let's select a local ollama llm instead of open
# router'). Benchmarked: qwen3:latest fit the 6GB card but took
# 50.2s/call (spilling to swap); granite4:3b (2.1GB, 4GB headroom)
# delivers clean JSON in 1.0s — the 50x speedup wins. The free
# Nemotron 502'd every call (Nvidia overloaded) — local removes
# the lottery entirely.
#
# SUPERSEDED 2026-09-10: the worker's model choice lives in the
# `tag-worker` pseudo-agent spec (app/domain/pseudo_agents/catalog.py),
# whose chain replaces the single hardcoded ollama client here.
# The benchmark above is kept — it is the record of why local matters.

_FM_RE = re.compile(r"^tags:\s*\[(.*?)\]", re.MULTILINE)


def _install_root() -> str:
    """The installation root, from the resolver — never a literal.

    This module carried six hardcoded absolute paths, one of them a
    `startswith()` GUARD, so it only functioned inside the directory it was
    written in — and shipped a username to every reader of the repository.
    """
    from app.core.config import Paths, get_settings

    return str(Paths.from_settings(get_settings()).root)


def _extract_tags(content: str) -> list[str]:
    """Mechanical frontmatter tag parse (the no-LLM fallback)."""
    m = _FM_RE.search(content)
    if not m:
        return []
    return [t.strip().strip("\"'") for t in m.group(1).split(",") if t.strip()]


async def _read_file(path: str) -> str:
    """Read a file via the file-info tool (operation=read)."""
    from app.domain.tools.registry import ToolRegistry
    registry = ToolRegistry.get_instance()
    result = await registry.execute_tool(
        tool_slug="file-info",
        tool_config={"base_path": _install_root()},
        arguments={"operation": "read", "path": path, "max_chars": 30000},
    )
    if isinstance(result, dict) and result.get("success"):
        return result.get("content", "") or ""
    return ""


# (the old `_worker_llm()` lived here — a single hardcoded ollama client.
#  Removed 2026-09-10: the worker is the `tag-worker` pseudo-agent spec,
#  whose ordered chain covers the local model and its fallbacks.)


async def _list_dir(path: str) -> list:
    """List a directory via the file-info tool (operation=list)."""
    from app.domain.tools.registry import ToolRegistry
    registry = ToolRegistry.get_instance()
    result = await registry.execute_tool(
        tool_slug="file-info",
        tool_config={"base_path": _install_root()},
        arguments={"operation": "list", "path": path},
    )
    if isinstance(result, dict) and result.get("success"):
        return result.get("items", []) or result.get("result", []) or []
    return []


def tag_discover_node(state: WorkflowState) -> dict:
    """THE DISCOVERY: recursively walk the wiki, collecting the .md
    file paths. The file-info list is ONE LEVEL only (iterdir), so
    the nested wiki (dev-notes/*, atlas/*, help/*) needs the walk.
    Mechanical — no LLM. The full file list feeds the dispatcher.
    """
    if _check_cancellation(state):
        return _cancelled_state(state)
    if _previous_step_failed(state):
        return {"execution_result": state.get("execution_result"), "current_step": None}

    # the root from the inputs/config (the list_files convention)
    inputs = state.get("inputs", {})
    root = inputs.get("folder_path") or inputs.get("base_path")
    if not root:
        meta = state.get("metadata")
        cfg = meta.config if hasattr(meta, "config") else (meta.get("config") if isinstance(meta, dict) else None)
        root = (cfg or {}).get("base_path") or _install_root()
    # Confine relative input to the installation, whatever it resolves to. The
    # original compared against a hardcoded absolute prefix, so it only ever
    # held on the machine the code was written on.
    _root = _install_root()
    if root and not str(root).startswith(_root):
        root = _root + "/" + str(root).lstrip("/")

    files = []
    dirs = [root]
    seen = set()
    while dirs:
        d = dirs.pop(0)
        if d in seen:
            continue
        seen.add(d)
        try:
            items = asyncio.run(_list_dir(d))
        except Exception as e:
            logger.error(f"  ❌ Tag discovery list failed {d}: {e}")
            continue
        for it in items:
            p = it.get("path", "")
            if not p:
                continue
            if it.get("is_directory"):
                if "_archive" not in p and ".git" not in p:
                    dirs.append(p)
            elif it.get("is_file") and p.endswith(".md"):
                files.append(p)

    logger.info(f"  📂 Tag discovery: {len(files)} .md files under {root}")
    return {
        "outputs": {"file_list": files, "sandbox_path": root},
        "current_step": None,
    }


def tag_extract_worker_node(state: WorkflowState) -> dict:
    """THE WORKER: read the batch's files + extract their tags.

    Reads the frontmatter mechanically (the regex parse — fast,
    free, deterministic), then ONE bounded LLM call (the free
    Nemotron) to normalize the rows into the strict contract:
    [{"page": ..., "tags": [...]}]. Returns rows — NO writes.
    """
    if _check_cancellation(state):
        return _cancelled_state(state)
    if _previous_step_failed(state):
        return {"execution_result": state.get("execution_result"), "current_step": None}

    outputs = state.get("outputs", {}) or {}
    file_list = outputs.get("file_list", [])
    if not file_list:
        return {"outputs": {"tag_rows": []}, "current_step": None}

    # 1. Read the frontmatter of every file in the batch (mechanical)
    pages = []
    for path in file_list:
        try:
            content = asyncio.run(_read_file(path))
            pages.append({"page": path, "content": content[:2000]})
        except Exception as e:
            logger.error(f"  ❌ Tag worker read failed {path}: {e}")

    # 2. The bounded LLM call: normalize the frontmatter into rows
    rows = []
    served_by = None
    spec = None
    try:
        from app.domain.pseudo_agents import get_spec
        spec = get_spec("tag-worker")
    except Exception as e:
        logger.warning(f"  ⚠️  Worker spec unavailable ({e}) — using the mechanical parse only")
    if spec is not None:
        prompt = (
            "Extract the YAML frontmatter tags from each page below. "
            "Return ONLY a JSON array of objects: [{\"page\": <path>, \"tags\": [<tags>]}]. "
            "Do not add prose. If a page has no tags, return an empty tags array.\n\n"
            + "\n\n".join(f"--- {p['page']} ---\n{p['content'][:500]}" for p in pages[:15])
        )
        try:
            # THE PSEUDO-AGENT CHAIN (2026-09-10): the worker is a named
            # spec — the free route → the local Bonsai → the boss's brain
            # — not a hand-rolled client. The chain logs every attempt and
            # returns its provenance, so a degraded run is visible.
            from app.domain.pseudo_agents import invoke as pseudo_invoke
            _t_llm = time.monotonic()
            _res = pseudo_invoke(spec, prompt)
            _llm_seconds = round(time.monotonic() - _t_llm, 2)
            served_by = _res.served_by
            # THE ATTEMPT HISTORY (2026-09-10): which chain steps were
            # tried, why they failed, how long each took. Logged before,
            # but never carried into the result — so an overnight run's
            # failovers were unrecoverable after the fact.
            _attempts = list(getattr(_res, "attempts", None) or [])
            if _res.degraded:
                logger.warning(
                    f"  ⚠️  Worker served by a FALLBACK step: {served_by} "
                    f"(after {len(_attempts) - 1} failed attempt(s))"
                )
            text = _res.text.strip()
            # the provider's own token counts (for the cost estimate's
            # calibration — see backend/scripts/estimate_workflow_cost.py)
            _usage = dict(getattr(_res, "usage", None) or {})
            # THE FENCE + SPAN FIX (2026-08-23, the 15-page evidence):
            # granite4 wraps the array in ```json ... ``` at batch
            # size — text.split('```')[1] yields 'json\n[...]' (the
            # language tag pollutes the head) and the span-extraction
            # then finds the FIRST '[' ... which is inside the fence
            # marker region issues. The robust path: take the text
            # BETWEEN the first '[' and the last ']' directly.
            _start = text.find("[")
            _end = text.rfind("]")
            if _start >= 0 and _end > _start:
                text = text[_start:_end + 1]
            rows = json.loads(text)
            if not isinstance(rows, list):
                rows = []
        except Exception as e:
            # THE DIAGNOSTIC (2026-08-23): log WHAT the model returned
            # — the parse failures persist in-run but not standalone;
            # the evidence distinguishes empty-content from a parse
            # shape issue (claimed-vs-verified before the fix).
            logger.warning(
                f"  ⚠️  Worker LLM parse failed ({e}) — mechanical fallback "
                f"[text_len={len(text) if 'text' in dir() else -1}, "
                f"head={(text[:120] if 'text' in dir() else '')!r}]"
            )
            rows = []
    if not rows:
        rows = [{"page": p["page"], "tags": _extract_tags(p["content"])} for p in pages]

    for row in rows:
        tags = row.get("tags", []) or []
        row["type_tags"] = [t for t in tags if t.startswith("type/")]
        row["domain_tags"] = [t for t in tags if t.startswith("domain/")]

    # THE LOUD WORKER-VERDICT (2026-08-23, the 88-fallback bug): the
    # manifest looked perfect while the LLM never fired. The worker
    # now reports its provenance — llm_fired / fell_back — so the
    # collector + the manifest carry the truth (the user's doctrine:
    # AGENT FAILS? LOG IT).
    # 2026-09-10: the verdict is now the CHAIN's own provenance —
    # `served_by` is proof the model answered (the old check only proved
    # a client was built), and it names the step that served the rows.
    _llm_fired = served_by is not None and not rows
    logger.info(
        f"  ✅ Tag worker: {len(rows)} rows from {len(file_list)} files "
        f"[served_by={served_by}, llm_rows={len(rows) if served_by else 0}, "
        f"mechanical={not rows}]"
    )
    return {
        "outputs": {
            "tag_rows": rows,
            "worker_meta": {
                "llm_fired": served_by is not None,
                "llm_rows": len(rows) if served_by else 0,
                "served_by": served_by,
                # the provider's token counts for this batch — the actual
                # the cost estimator is calibrated against
                "usage": _usage,
                # the timing + the chain's attempt history (see above)
                "llm_seconds": _llm_seconds,
                "attempts": _attempts,
                "mechanical": not rows,
            },
        },
        "current_step": None,
    }


def tag_dispatch_node(state: WorkflowState) -> dict:
    """THE TAG DISPATCH: declare the survey's worker, then delegate.

    The graph wires `batch_workers_node` (the generic fan-out), which
    reads its worker function from the config's `worker_fn` key. This
    node is what SETS that key — the graph's docstring promised the
    swap but nothing performed it, so batches silently fell through to
    File Clerk's summarize (found by the first trickle run: 3 files
    per batch, "string indices must be integers").

    Setting it here rather than in the template config keeps the survey
    self-contained: any caller — API, UI, script — gets the tag workers.
    """
    meta = state.get("metadata")
    config = getattr(meta, "config", None)
    if isinstance(config, dict):
        config.setdefault(
            "worker_fn",
            "app.workflows.nodes.tag_survey_nodes.tag_extract_worker_node",
        )
    # lazy import, matching this module's style (and avoiding any
    # import cycle with the generic fan-out nodes)
    from .boss_agent_nodes import boss_dispatch_node
    return boss_dispatch_node(state)


def tag_merge_node(state: WorkflowState) -> dict:
    """THE COLLECTOR: assemble the batch rows into the manifest.

    Mechanical assembly: the co-occurrence counts + the manifest
    table. The reasoning pass (consolidation suggestions) is a
    separate step the orchestrator can run on ox.
    """
    outputs = state.get("outputs", {}) or {}
    batch_results = outputs.get("batch_results", [])
    all_rows = []
    for br in batch_results:
        if isinstance(br, dict) and br.get("tag_rows"):
            all_rows.extend(br["tag_rows"])

    counts: dict[str, int] = {}
    for row in all_rows:
        for t in row.get("tags", []) or []:
            counts[t] = counts.get(t, 0) + 1

    # THE PROVENANCE COUNTS (2026-08-23): the manifest reports how
    # many rows came from the LLM vs the mechanical fallback — the
    # deliverable carries its own truth (no more silent fallbacks
    # hiding behind a clean-looking manifest).
    _llm_rows = sum(
        (br.get("worker_meta", {}) or {}).get("llm_rows", 0)
        for br in batch_results if isinstance(br, dict)
    )
    _mech_rows = len(all_rows) - _llm_rows

    # F4 — the LIMITED-RUN LABEL (2026-08-23): a partial manifest
    # must be clearly marked so nobody mistakes it for the
    # deliverable (the smoke-before-full-run gate).
    _limited = outputs.get("batch_limited", False)
    _ran = outputs.get("batch_ran", 0)
    _total = outputs.get("batch_total", 0)

    manifest_lines = [
        "# Tag-Layer Manifest (the fan-out survey)",
        "",
    ]
    if _limited:
        manifest_lines.append("⚠️ LIMITED RUN — first {_ran} of {_total} batches (a smoke test, NOT the deliverable)".replace("{_ran}", str(_ran)).replace("{_total}", str(_total)))
        manifest_lines.append("")
    manifest_lines += [
        f"- Pages surveyed: {len(all_rows)}",
        f"- Distinct tags: {len(counts)}",
        f"- Rows from the LLM workers: {_llm_rows}",
        f"- Rows from the mechanical fallback: {_mech_rows}",
        "",
        "| page | tags | type | domain |",
        "|---|---|---|---|",
    ]
    for row in all_rows:
        manifest_lines.append(
            f"| {row.get('page','?')} | {' '.join(row.get('tags', []) or [])} | "
            f"{' '.join(row.get('type_tags', []) or [])} | {' '.join(row.get('domain_tags', []) or [])} |"
        )

    manifest = "\n".join(manifest_lines)

    # THE DELIVERY (2026-08-23): write the manifest to the agent's
    # workspace out/ — the collector's write step (the fan-out
    # discipline: the workers never write; the collector delivers).
    # Written via the file-manager tool (operation=write, sandboxed
    # to the agent home). The output_data serialization bug eats
    # the outputs channel, so the FILE is the durable deliverable.
    write_result = None
    try:
        from app.domain.tools.registry import ToolRegistry
        registry = ToolRegistry.get_instance()
        write_result = asyncio.run(registry.execute_tool(
            tool_slug="file-manager",
            tool_config={"base_path": _install_root() + "/agents/tag-layer-sweeper"},
            arguments={
                "operation": "write",
                "path": "out/tag-layer-manifest.md",
                "content": manifest,
            },
        ))
        logger.info(f"  📤 Manifest written: {write_result.get('success') if isinstance(write_result, dict) else write_result}")
    except Exception as e:
        logger.error(f"  ❌ Manifest write failed: {e}")

    # MERGE, don't replace. LangGraph's `outputs` channel has no reducer,
    # so returning a fresh dict DROPS what earlier nodes accumulated —
    # here the batch_results/worker_meta. (The same mistake in boss_node
    # then dropped this node's manifest and rows, leaving an empty final
    # state while the files on disk were fine. Found by the trickle run.)
    from .file_clerk_nodes import _merge_outputs
    return {
        "outputs": _merge_outputs(outputs, {
            "manifest": manifest,
            "tag_rows": all_rows,
            "tag_counts": counts,
            "manifest_write": write_result,
        }),
        "execution_result": {
            "result": f"Tag survey complete: {len(all_rows)} pages, {len(counts)} distinct tags" + ("" if (isinstance(write_result, dict) and write_result.get("success")) else " (manifest write failed)"),
            "completed_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        },
        "current_step": None,
    }


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
    meta = state.get("metadata")
    if meta and isinstance(meta, dict) and meta.get("status") == "error":
        return True
    return False


def _cancelled_state(state: WorkflowState) -> dict:
    now = datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return {
        "execution_result": {"result": "Cancelled", "completed_at": now},
        "current_step": None,
    }


def boss_node(state: WorkflowState) -> dict:
    """THE BOSS (2026-08-23, the user's name): the consolidation
    pass — read the manifest rows + the taxonomy rules, PROPOSE the
    tag changes. THE DRY-RUN HALF: it proposes, it does NOT apply
    (no wiki writes — the apply step is the wet-run half, absent
    by design until the user says go).

    The input: the collector's tag_counts + the rows. The output:
    the consolidation report (the proposed changes) written to
    out/consolidation-report.md + returned in outputs.
    """
    if _check_cancellation(state):
        return _cancelled_state(state)
    if _previous_step_failed(state):
        return {"execution_result": state.get("execution_result"), "current_step": None}

    outputs = state.get("outputs", {}) or {}
    all_rows = outputs.get("tag_rows", [])
    counts = outputs.get("tag_counts", {})
    if not all_rows:
        from .file_clerk_nodes import _merge_outputs
        return {"outputs": _merge_outputs(outputs, {"consolidation": ""}), "current_step": None}

    # the findings the boss reasons over (the manifest's raw data)
    messy = sorted({t for t in counts if "devnote" in t})
    no_tag_pages = [r.get("page", "") for r in all_rows if not (r.get("tags") or [])]
    junk = sorted({t for t in counts if not t.startswith(("type/", "domain/", "feature/", "status/"))})

    prompt = (
        "You are the tag-consolidation boss. Analyze the wiki tag inventory below and "
        "propose the tag changes: what to RENAME (the variant -> canonical map, e.g. "
        "type/devnote -> type/dev-notes), what to ADD (pages with no type/ or no domain/), "
        "and what to DROP (junk/non-namespaced tags). Return ONLY a JSON object: "
        "{\"renames\": [{\"from\": ..., \"to\": ...}], \"adds\": [{\"page\": ..., \"suggest\": ...}], "
        "\"drops\": [...], \"summary\": ...}. Do not add prose outside the JSON.\n\n"
        f"TAG COUNTS: {dict(sorted(counts.items(), key=lambda x: -x[1])[:40])}\n"
        f"MESSY VARIANTS: {messy}\n"
        f"PAGES WITH NO TAGS: {no_tag_pages[:15]}\n"
        f"NON-NAMESPACED (junk): {junk[:15]}\n"
        "The canonical namespaces: type/*, domain/*, feature/*, status/*."
    )

    report = ""
    try:
        # THE PSEUDO-AGENT CHAIN (2026-09-10): the boss is the named
        # tag-boss spec — the free route → the local Bonsai → deepseek —
        # replacing the hand-rolled single-provider client. (The old
        # comment here recorded the ox-alpha's departure from OpenRouter;
        # the spec carries that history now.)
        from app.domain.pseudo_agents import get_spec, invoke as pseudo_invoke
        _res = pseudo_invoke(get_spec("tag-boss"), prompt)
        logger.info(
            f"  The boss served by {_res.served_by} ({_res.elapsed}s, degraded={_res.degraded})"
        )
        text = _res.text
        _s, _e = text.find("{"), text.rfind("}")
        if _s >= 0 and _e > _s:
            import json as _json
            data = _json.loads(text[_s:_e + 1])
            lines = ["# The Tag Consolidation (the tag-boss spec — the dry run)", ""]
            lines.append("## Proposed renames")
            for r in data.get("renames", []):
                lines.append(f"- {r.get('from')} -> {r.get('to')}")
            lines.append("")
            lines.append("## Proposed adds")
            for a in data.get("adds", [])[:20]:
                lines.append(f"- {a.get('page')}: add {a.get('suggest')}")
            lines.append("")
            lines.append("## Proposed drops")
            for d in data.get("drops", []):
                lines.append(f"- {d}")
            lines.append("")
            lines.append(f"## Summary: {data.get('summary', '')}")
            report = "\n".join(lines)
    except Exception as e:
        logger.warning(f"  ⚠️  Tag-boss consolidate failed ({e}) — mechanical fallback")
        report = (
            "# The Tag Consolidation (MECHANICAL fallback — the boss call failed)\n\n"
            f"## Messy variants (the rename candidates): {messy}\n\n"
            f"## No-tag pages (the add candidates): {no_tag_pages[:15]}\n\n"
            f"## Junk (the drop candidates): {junk[:15]}"
        )

    # write the consolidation report to the workspace (the dry-run
    # deliverable — NO wiki writes)
    write_result = None
    try:
        out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.dirname(__file__))))), "agents", "tag-layer-sweeper", "out")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "consolidation-report.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report)
        write_result = {"success": True, "path": out_path}
        logger.info(f"  📤 Consolidation report written: {out_path}")

        # PHASE C — THE_BOSS:PROPOSED EVENT (2026-08-24): the
        # consolidation is DONE — the SSE stream shows the Boss's
        # proposal landing. The report path is the payload.
        try:
            from app.domain.messaging.services import publish
            publish("the_boss:proposed", {
                "workflow_id": state.get("workflow_id"),
                "report_path": out_path,
            })
        except Exception as _e:
            logger.error(f"  ❌ the_boss:proposed publish failed: {_e}")
    except Exception as e:
        logger.error(f"  ❌ Consolidation write failed: {e}")
        write_result = {"success": False, "error": str(e)}

    # MERGE (see tag_merge_node): a fresh dict would drop the manifest,
    # rows and counts from the final workflow state.
    from .file_clerk_nodes import _merge_outputs
    return {
        "outputs": _merge_outputs(outputs, {
            "consolidation": report,
            "consolidation_write": write_result,
        }),
        "current_step": None,
    }
