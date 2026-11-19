"""Monitor workflow family — nodes.

The monitor → analyze → report pattern with different cadences:
- rss_monitor: hourly, fetch feeds → dedup via checkpoint state →
  summarize → digest file
- market_watch: 5-min, fetch prices → threshold/trend compare →
  alert file

Cross-run state ("what did I already report?") lives in the
checkpoint (per-thread, persists across invocations) — this is
checkpoint-as-memory, dogfooding the execution-identity work.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..error_handling.grades import node_grade

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared state helpers
# ---------------------------------------------------------------------------

MONITOR_KEYS = [
    "last_seen",       # dict: feed_url -> list of item ids already seen
    "digest_path",     # str: the digest/alert file written this run
    "new_items",       # list: items fetched this run (pre-summary)
    "report_text",     # str: the final report text
    "errors",          # list: per-run error strings (never fails the workflow)
]


def _digest_dir() -> Path:
    """Where monitor reports land (gitignored data/ dir)."""
    from app.core.config import Paths, get_settings
    d = Paths.from_settings(get_settings()).monitor_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _distributor_names(state: Dict[str, Any]) -> List[str]:
    """Distributors from the run's config (default: file + display + toast).

    A workflow's config JSON may declare
    "distributors": ["file", "display"]; falling back to the
    full default set keeps existing runs working unchanged.
    (Triggers ship deactivated, so toasts only fire on manual
    runs — no noise risk from scheduled monitors.)
    """
    inputs = state.get("inputs") or {}
    cfg = inputs.get("distributors")
    if isinstance(cfg, list) and cfg:
        return [str(x) for x in cfg]
    return ["file", "display", "toast"]


def _state_file() -> Path:
    """Persistent dedup state (survives restarts, not thread-bound)."""
    return _digest_dir() / "state.json"


def _load_state() -> Dict[str, Any]:
    """Load the persisted dedup state (feeds -> seen item ids)."""
    try:
        raw = _state_file().read_text(encoding="utf-8")
        data = json.loads(raw)
        return dict(data) if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    _state_file().write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# RSS monitor nodes
# ---------------------------------------------------------------------------

# TOLERANT BY CONSTRUCTION (see error_handling/grades.py): a monitor exists to keep
# going when a feed, an API or the summariser is down. Its failures go to the state's
# own `errors` list and NEVER mark the run — no `metadata.status`, no statement — so a
# dead feed leaves the run completed and clean. Declared, not inferred: a reader and
# the tests read this, and grading a monitor fatal would start failing runs on a feed.
@node_grade("tolerant")
def rss_fetch_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch configured RSS feeds, extract items, mark new vs seen.

    Uses jina_reader semantics (URL → markdown, no API key) via
    urllib. Items are deduped against checkpoint state
    (state["last_seen"]).
    """
    # The feeds come from the TEMPLATE CONFIG — the router seeds it
    # into metadata.config (WorkflowState has no feeds/config channel;
    # the 2026-08-18 wiring fix: the monitor read state.feeds which
    # never existed in the seeded state, so every run got 0 items).
    #
    # THE SECOND DOOR (2026-10-13). That fix taught the API path to seed `state.config` and
    # stopped there; the SCHEDULER seeded `"config": None`, so every scheduled run still got 0
    # items — and this node CRASHED on the way to finding out (`None.get` → AttributeError), which
    # `@node_grade("tolerant")` swallowed into a clean-looking cycle. Both are fixed at the source
    # (one reader, `app/workflows/template_config.py`); what stays here is the shape tolerance:
    # every channel is read defensively, because a monitor that cannot read its config must still
    # run, and must SAY it found nothing rather than report "no new items".
    meta = state.get("metadata") or {}
    meta_config = getattr(meta, "config", None)
    if not isinstance(meta_config, dict):
        meta_config = meta.get("config") if isinstance(meta, dict) else None
    if not isinstance(meta_config, dict):
        meta_config = {}
    config = state.get("config")
    if not isinstance(config, dict):
        config = {}
    inputs = state.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}

    feeds: List[str] = (
        list(meta_config.get("feeds") or [])
        or list(state.get("feeds") or [])
        or list(inputs.get("feeds") or [])
        or list(config.get("feeds") or [])
    )
    max_items: int = int(inputs.get("max_items") or config.get("max_items") or 5)

    # Dedup state lives in a state file (monitors are stateless per
    # run — each trigger fire is a fresh thread, so checkpoint state
    # can't carry "last seen" across invocations).
    persisted = _load_state()
    last_seen: Dict[str, List[str]] = persisted.get("last_seen", {})

    new_items: List[Dict[str, Any]] = []
    errors: List[str] = list(state.get("errors") or [])
    per_feed_seen: Dict[str, List[str]] = {}

    # AN EMPTY FEED LIST IS NEWS (2026-10-13). It used to be silence: the loop below did not run,
    # the state file was written as `{"last_seen": {}}` and the digest read "No new items this
    # cycle." — a clean cycle that was really *this run did not carry its template's config*. A
    # monitor is allowed to fail quietly on a dead feed; it is not allowed to fail quietly on
    # having nothing to watch.
    if not feeds:
        errors.append(
            "no feeds resolved for this run — checked state.config.feeds, state.feeds and "
            "inputs.feeds; a scheduled run is seeded with its template's config, so an empty "
            "list here means the run did not carry one"
        )

    for feed_url in feeds:
        try:
            markdown = _fetch_url(feed_url)
            items = _parse_markdown_items(markdown, feed_url, max_items)
            seen = set(last_seen.get(feed_url, []))
            fresh = [it for it in items if it["id"] not in seen]
            new_items.extend(fresh)
            per_feed_seen[feed_url] = list(seen | {it["id"] for it in items})
        except Exception as e:  # never fail the workflow on fetch error
            errors.append(f"fetch {feed_url}: {e}")
            logger.warning("rss_fetch_node: %s", e)

    _save_state({"last_seen": {**last_seen, **per_feed_seen}})

    return {
        "new_items": new_items,
        "last_seen": {**last_seen, **per_feed_seen},
        "errors": errors,
        "current_step": "rss_fetch",
    }


@node_grade("tolerant")
def rss_summarize_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize new items via summarize-llm (local, no key).

    Falls back to a plain text digest if the LLM path fails (the
    monitor must never block on the LLM).
    """
    new_items: List[Dict[str, Any]] = state.get("new_items") or []
    errors: List[str] = list(state.get("errors") or [])

    if not new_items:
        return {
            "report_text": "No new items this cycle.",
            "current_step": "rss_summarize",
        }

    try:
        summary = _llm_summarize(new_items)
    except Exception as e:
        errors.append(f"summarize: {e}")
        summary = None

    if not summary:
        lines = []
        for it in new_items:
            lines.append(f"- **{it['title']}** ({it['source']})\n  {it['url']}")
        summary = "## New items\n\n" + "\n".join(lines)

    return {
        "report_text": summary,
        "errors": errors,
        "current_step": "rss_summarize",
    }


@node_grade("tolerant")
def rss_format_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Format the digest as a structured markdown digest.

    The 2026-08-18 add: the LLM summary path dropped the URLs
    (headlines only). This node GUARANTEES the structure — the
    linked item list is built deterministically from the items;
    the LLM summary (if any) becomes the 'At a glance' intro.
    Deterministic control flow around the stochastic step (the
    factoring hypothesis in practice).
    """
    new_items: List[Dict[str, Any]] = state.get("new_items") or []
    summary: str = state.get("report_text") or ""
    errors: List[str] = list(state.get("errors") or [])

    sections: List[str] = []

    if summary and summary != "No new items this cycle.":
        sections.append("## At a glance\n\n" + summary.strip())

    if new_items:
        lines = []
        for it in new_items:
            title = (it.get("title") or "untitled").strip()
            url = (it.get("url") or "").strip()
            source = (it.get("source") or "").strip()
            linked = f"[{title}]({url})" if url else title
            lines.append(f"- {linked} — {source}")
        sections.append("## New items\n\n" + "\n".join(lines))

    formatted = "\n\n".join(sections) if sections else (
        # "No new items" is a CLAIM, and with errors on the state it is a false one: a run that
        # could not read its config gathered nothing because it looked at nothing. The two cases
        # have to read differently or the quiet failure comes back.
        "Nothing gathered this cycle — see the errors below."
        if errors
        else "No new items this cycle."
    )
    return {
        "report_text": formatted,
        "current_step": "rss_format",
    }


@node_grade("tolerant")
def rss_deliver_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Package the digest as a WorkflowProduct and deliver it.

    Delivery goes through the distributor registry (file +
    display by default) — the distribution layer replaces the
    hardcoded file write (roadmap: workflow product distribution).
    """
    from app.workflows.distribution import WorkflowProduct, deliver_product

    report: str = state.get("report_text") or ""
    new_items: List[Dict[str, Any]] = state.get("new_items") or []
    errors: List[str] = list(state.get("errors") or [])
    ts = _now()

    header = f"# RSS Digest — {ts}\n\n_Items: {len(new_items)} · Errors: {len(errors)}_\n\n"
    body = report + ("\n\n## Errors\n\n" + "\n".join(f"- {e}" for e in errors) if errors else "")

    product = WorkflowProduct(
        product_type="rss_digest",
        title=f"RSS Digest — {ts[:10]}",
        body=header + body,
        source_template="rss-monitor",
        created_at=ts,
        meta={"items": len(new_items), "errors": len(errors)},
    )
    results = deliver_product(product, names=_distributor_names(state))
    return {
        "digest_path": product.path or "",
        "report_text": report,
        "current_step": "rss_deliver",
        "delivery": [r.as_dict() for r in results],
    }


# ---------------------------------------------------------------------------
# Market watch nodes
# ---------------------------------------------------------------------------

@node_grade("tolerant")
def market_fetch_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch a keyless crypto price (CoinGecko simple price)."""
    symbol: str = (
        state.get("symbol")
        or state.get("inputs", {}).get("symbol")
        or state.get("config", {}).get("symbol", "bitcoin")
    )
    threshold: float = float(
        state.get("inputs", {}).get("threshold_pct")
        or state.get("config", {}).get("threshold_pct", 2.0)
    )

    errors: List[str] = list(state.get("errors") or [])
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
        raw = _fetch_url(url, timeout=15)
        data = json.loads(raw)
        price = float(data.get(symbol, {}).get("usd", 0.0))
    except Exception as e:
        errors.append(f"market fetch: {e}")
        price = 0.0

    prev_price = state.get("last_price")
    alert_lines: List[str] = []
    if prev_price and price:
        pct = (price - prev_price) / prev_price * 100
        if abs(pct) >= threshold:
            direction = "▲ up" if pct > 0 else "▼ down"
            alert_lines.append(
                f"- {symbol}: ${price:,.2f} ({direction} {pct:+.2f}% vs ${prev_price:,.2f})"
            )
        else:
            alert_lines.append(f"- {symbol}: ${price:,.2f} (change {pct:+.2f}% — within threshold)")

    return {
        "last_price": price,
        "report_text": "\n".join(alert_lines) if alert_lines else f"- {symbol}: ${price:,.2f}",
        "errors": errors,
        "current_step": "market_fetch",
    }


@node_grade("tolerant")
def market_deliver_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Package the market alert as a WorkflowProduct and deliver it."""
    from app.workflows.distribution import WorkflowProduct, deliver_product

    report: str = state.get("report_text") or ""
    ts = _now()

    product = WorkflowProduct(
        product_type="market_alert",
        title=f"Market Watch — {ts[:10]}",
        body=f"# Market Watch — {ts}\n\n{report}\n",
        source_template="market-watch",
        created_at=ts,
        meta={"symbols": state.get("symbols") or []},
    )
    results = deliver_product(product, names=_distributor_names(state))
    return {
        "digest_path": product.path or "",
        "current_step": "market_deliver",
        "delivery": [r.as_dict() for r in results],
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _fetch_url(url: str, timeout: int = 20) -> str:
    """Fetch a URL → text (jina_reader semantics: markdown-friendly)."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Cogitate Monitor)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
        return str(data.decode("utf-8", errors="replace"))


def _parse_markdown_items(markdown: str, feed_url: str, max_items: int) -> List[Dict[str, Any]]:
    """Extract (title, url) pairs from RSS XML (or a jina markdown).

    Real RSS feeds are XML — parse with xml.etree (stdlib,
    deterministic, no external service). The item id is the link URL
    (stable dedup key). If the body isn't XML (e.g. a jina_reader
    markdown render), fall back to markdown link scanning.
    """
    import xml.etree.ElementTree as ET

    body = markdown.strip()
    items: List[Dict[str, Any]] = []
    seen_urls: set[str] = set()

    # Try XML parse first (real RSS/Atom feeds)
    try:
        root = ET.fromstring(body)
        # item elements live under channel (RSS) or the root (Atom)
        entries: List[Any] = []
        for tag in ("item", "entry"):
            entries.extend(root.iter(tag))
        for entry in entries:
            title_el = entry.find("title")
            link_el = entry.find("link")
            title = (title_el.text or "").strip() if title_el is not None else ""
            # RSS: <link>text</link>; Atom: <link href="...">
            url = ""
            if link_el is not None:
                if link_el.text and link_el.text.startswith("http"):
                    url = link_el.text.strip()
                else:
                    url = (link_el.get("href") or "").strip()
            if not title or not url or url in seen_urls:
                continue
            seen_urls.add(url)
            items.append({
                "id": url,
                "title": title[:200],
                "url": url,
                "source": feed_url,
            })
            if len(items) >= max_items:
                break
        if items:
            return items
    except ET.ParseError:
        pass  # not XML — fall through to markdown scan

    # Fallback: markdown link scanning (jina_reader renders)
    for m in re.finditer(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", body):
        title, url = m.group(1).strip(), m.group(2).strip()
        if not title or url in seen_urls:
            continue
        seen_urls.add(url)
        items.append({
            "id": url,
            "title": title[:200],
            "url": url,
            "source": feed_url,
        })
        if len(items) >= max_items:
            break
    return items


def _llm_summarize(items: List[Dict[str, Any]]) -> Optional[str]:
    """Run the summarize-llm builtin tool if available.

    Uses the registry's execute_tool (the tool-calling layer) —
    builtin handlers are wrapped as plain functions by get_handler;
    calling handler.execute() on them raises AttributeError. This
    path silently fell back to the plain-text digest until the
    2026-08-10 live verification caught it.
    """
    try:
        import asyncio
        from app.domain.tools.registry import init_default_registry
        registry = init_default_registry()
        handler = registry.get_handler("summarize-llm")
        if handler is None:
            logger.warning("_llm_summarize: summarize-llm handler not registered")
            return None
        text = "\n".join(f"- {it['title']} — {it['url']}" for it in items)

        async def _run() -> Any:
            # Builtin handlers are plain callables: handler(config, **kwargs).
            # get_handler returns the unwrapped function; execute_tool would
            # also work but requires the tool to be in the singleton _tools.
            return await handler(
                {"model": "ollama/llama3.2", "max_tokens": 500, "temperature": 0.3},
                content=text,
                instruction="Summarize these news headlines into 3-5 concise bullet points.",
                style="bullet-points",
            )

        result = asyncio.run(_run())
        if isinstance(result, dict):
            if result.get("success") and result.get("summary"):
                return str(result["summary"])
            if result.get("error"):
                logger.warning("_llm_summarize: %s", result["error"])
                return None
            return str(result) if result else None
        return str(result) if result else None
        if isinstance(result, dict):
            summary = result.get("summary") or result.get("result") or result.get("output")
            return str(summary) if summary is not None else None
        return str(result) if result else None
    except Exception as e:
        logger.warning("_llm_summarize: %s", e)
        return None


# ---------------------------------------------------------------------------
# First-run readiness check nodes
# ---------------------------------------------------------------------------

@node_grade("tolerant")
def readiness_probe_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the system readiness probes: POST suite + providers +
    agents + curated models + env keys.

    Manual trigger (TestingDashboard) — immediate results. Uses
    run-post (health suite) + direct DB/env checks. Never fails the
    workflow; collects everything into a report.

    Note: RunPostTool.execute is async; the graph router invokes
    synchronously, so we bridge with asyncio.run (no running loop
    inside a sync graph invoke).
    """
    import asyncio
    from app.domain.tools.builtin.run_post import RunPostTool

    results: List[str] = []
    errors: List[str] = list(state.get("errors") or [])

    # 1. POST health suite (llm, database, api, config, connectivity)
    try:
        post = RunPostTool()
        out = asyncio.run(post.execute({}, checks="all"))
        checks = out.get("checks", []) if isinstance(out, dict) else []
        passed = sum(1 for c in checks if c.get("status") == "pass")
        failed = sum(1 for c in checks if c.get("status") == "fail")
        results.append(f"- POST health suite: {passed} passed / {failed} failed")
        for c in checks:
            if c.get("status") == "fail":
                results.append(f"  - FAIL {c.get('name', '?')}: {c.get('detail', '')}")
    except Exception as e:
        errors.append(f"post suite: {e}")

    # 2. Providers + env keys (EnvKeyStore)
    try:
        from app.domain.providers.env_key_store import env_key_store
        conn = _main_db()
        rows = conn.execute(
            "SELECT name, provider_type, is_active FROM providers ORDER BY priority"
        ).fetchall()
        conn.close()
        results.append(f"- Providers: {len(rows)} configured")
        for name, ptype, active in rows:
            has_key = bool(env_key_store.get_key(ptype))
            key_state = "key: env" if has_key else ("key: n/a" if ptype == "ollama" else "key: MISSING")
            results.append(f"  - {name} ({ptype}) active={bool(active)} {key_state}")
    except Exception as e:
        errors.append(f"providers: {e}")

    # 3. Agents + curated models
    try:
        conn = _main_db()
        agents = conn.execute("SELECT COUNT(*) FROM agents WHERE is_active=1").fetchone()[0]
        models = conn.execute("SELECT COUNT(*) FROM curated_models").fetchone()[0]
        conn.close()
        results.append(f"- Agents active: {agents} · Curated models: {models}")
    except Exception as e:
        errors.append(f"db counts: {e}")

    report = "## Readiness Report\n\n" + "\n".join(results)
    if errors:
        report += "\n\n## Errors\n\n" + "\n".join(f"- {e}" for e in errors)

    return {
        "report_text": report,
        "errors": errors,
        "current_step": "readiness_probe",
    }


@node_grade("tolerant")
def readiness_deliver_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Package the readiness report as a WorkflowProduct and deliver it."""
    from app.workflows.distribution import WorkflowProduct, deliver_product

    report: str = state.get("report_text") or ""
    ts = _now()

    product = WorkflowProduct(
        product_type="readiness_report",
        title=f"First-Run Readiness — {ts[:10]}",
        body=f"# First-Run Readiness — {ts}\n\n{report}\n",
        source_template="readiness-check",
        created_at=ts,
        meta={"errors": len(state.get("errors") or [])},
    )
    results = deliver_product(product, names=_distributor_names(state))
    return {
        "digest_path": product.path or "",
        "current_step": "readiness_deliver",
        "delivery": [r.as_dict() for r in results],
    }


def _main_db():
    """Open the main cogitate.db (read-only intent)."""
    import sqlite3
    from app.core.config import Paths, get_settings
    db_path = Paths.from_settings(get_settings()).shared_db
    return sqlite3.connect(db_path)
