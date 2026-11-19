"""
Workflow Product Distribution — distributors.

Distributor ABC + builtin implementations:
- FileDistributor: writes the product markdown to data/monitor/
- DisplayDistributor: registers the product in the display index
  (data/monitor/products.json) that the frontend "Workflow
  Products" page reads

The registry + create_default_distributors() follow the
established pipeline pattern (ABC → Registry → factory) — new
channels (email, sms, toast) plug in as new distributor classes.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from .models import DeliveryResult, WorkflowProduct

logger = logging.getLogger(__name__)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _products_dir() -> Path:
    """data/monitor at the project root — via the Paths locator (the
    pathing discipline 2026-08-17)."""
    from app.core.config import Paths, get_settings
    return Paths.from_settings(get_settings()).monitor_dir


class WorkflowDistributor(ABC):
    """Deliver a WorkflowProduct to one channel."""

    name: str = "base"

    @abstractmethod
    def deliver(self, product: WorkflowProduct) -> DeliveryResult:
        """Deliver the product. Must not raise — return a DeliveryResult."""


class FileDistributor(WorkflowDistributor):
    """Write the product as a markdown file in data/monitor/."""

    name = "file"

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or _products_dir()

    def deliver(self, product: WorkflowProduct) -> DeliveryResult:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            ext = "md"
            # UNIQUE filename (the collision fix, 2026-08-18): the old
            # {type}-{date} name collided for same-day same-type
            # products — every delivery overwrote ONE file while the
            # index kept all entries pointing at it (the overwrite
            # trap + the selection/delete/viewer collisions). The
            # time suffix makes each delivery's file unique.
            # the full timestamp (ms included) — the second-truncation
            # still collided for same-second deliveries (2026-08-18)
            # the stamp: date + time (ms if present — some created_at
            # values carry .mmm, others stop at the second + a 'Z')
            raw = product.created_at.replace("T", "-").replace(":", "").replace(".", "-")
            stamp = raw.rstrip("Z")[:23]
            path = self.base_dir / f"{product.product_type}-{stamp}.{ext}"
            path.write_text(f"# {product.title}\n\n{product.body}\n", encoding="utf-8")
            product.path = str(path)
            return DeliveryResult(
                distributor=self.name,
                success=True,
                detail=f"wrote {path.name}",
                path=str(path),
            )
        except Exception as e:  # noqa: BLE001 — distributors must not raise
            logger.warning("FileDistributor failed: %s", e)
            return DeliveryResult(distributor=self.name, success=False, detail=str(e))


class DisplayDistributor(WorkflowDistributor):
    """Register the product in the display index (products.json).

    The frontend Workflow Products page reads this index — the
    product is 'delivered' to a display surface without any push
    infrastructure (the page polls the endpoint).
    """

    name = "display"
    MAX_ENTRIES = 100

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or _products_dir()

    def _index_path(self) -> Path:
        return self.base_dir / "products.json"

    def deliver(self, product: WorkflowProduct) -> DeliveryResult:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            index_path = self._index_path()
            entries: list[dict[str, Any]] = []
            if index_path.exists():
                try:
                    entries = json.loads(index_path.read_text(encoding="utf-8"))
                    if not isinstance(entries, list):
                        entries = []
                except (json.JSONDecodeError, OSError):
                    entries = []
            entry = {
                "product_type": product.product_type,
                "title": product.title,
                "source_template": product.source_template,
                "created_at": product.created_at,
                "path": product.path,
                "meta": product.meta,
                # FULL body — the truncation capped the modal at 2000
                # chars; the full-page viewer needs the whole report
                # (the report-viewer mini-map, 2026-08-17)
                "body": product.body,
            }
            entries.insert(0, entry)
            entries = entries[: self.MAX_ENTRIES]
            index_path.write_text(
                json.dumps(entries, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return DeliveryResult(
                distributor=self.name,
                success=True,
                detail=f"registered {len(entries)} products",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("DisplayDistributor failed: %s", e)
            return DeliveryResult(distributor=self.name, success=False, detail=str(e))


class ToastDistributor(WorkflowDistributor):
    """Append the product to the toast queue (toasts.json).

    The frontend polls GET /workflows/toasts and shows each entry
    as an in-app toast (notificationStore) with a link to the
    product. The queue keeps unread entries; the frontend drains
    by marking the cursor it has seen (the endpoint returns
    entries newer than a since= timestamp).
    """

    name = "toast"
    MAX_ENTRIES = 200

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or _products_dir()

    def _queue_path(self) -> Path:
        return self.base_dir / "toasts.json"

    def deliver(self, product: WorkflowProduct) -> DeliveryResult:
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            queue_path = self._queue_path()
            entries: list[dict[str, Any]] = []
            if queue_path.exists():
                try:
                    entries = json.loads(queue_path.read_text(encoding="utf-8"))
                    if not isinstance(entries, list):
                        entries = []
                except (json.JSONDecodeError, OSError):
                    entries = []
            entry = {
                "product_type": product.product_type,
                "title": product.title,
                "source_template": product.source_template,
                "created_at": product.created_at,
                "path": product.path,
            }
            entries.insert(0, entry)
            entries = entries[: self.MAX_ENTRIES]
            queue_path.write_text(
                json.dumps(entries, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return DeliveryResult(
                distributor=self.name,
                success=True,
                detail=f"queued toast ({len(entries)} in queue)",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("ToastDistributor failed: %s", e)
            return DeliveryResult(distributor=self.name, success=False, detail=str(e))


class AgentDistributor(WorkflowDistributor):
    """Hand a product to an ADDRESSED agent (ARM Phase D — the
    agent-recipient channel, the long-deferred todo).

    The recipient is named in product.meta["recipient_agent"] —
    REGISTRY IDENTITY (a unique agent name, Phase A). Modes:
    - file-it: write the product into the agent's inbox folder
      (agents/<name>/inbox/)
    - hand-it-a-task: create/use a chat session for the agent and
      post the product body as a message (its task inbox)
    The registry resolves the name STRICT — an unknown agent fails
    loudly (dead-letter, not a hang).
    """

    name = "agent"

    def __init__(
        self, agents_root: Optional[Path] = None,
        session_factory=None,
    ) -> None:
        self.agents_root = agents_root or Path("agents")
        # injectable for tests; defaults to the app's session factory
        self.session_factory = session_factory

    def _session(self):
        if self.session_factory is not None:
            return self.session_factory()
        from app.core.database import AsyncSessionLocal
        return AsyncSessionLocal()

    def deliver(self, product: WorkflowProduct) -> DeliveryResult:
        recipient = (product.meta or {}).get("recipient_agent")
        if not recipient:
            return DeliveryResult(
                distributor=self.name, success=False,
                detail="no recipient_agent in product.meta (address by name)",
            )
        mode = (product.meta or {}).get("recipient_mode", "file-it")

        # THE EXA DESK (2026-08-20): recipient 'exa' (or the
        # external-agent surface's id) files into the workspace
        # inbox — .exa-workspace/inbox/ — NOT a DB agent's folder.
        # Exa is not a registry row; the registry resolution below
        # would fail loudly. The desktop is the home/workspace
        # split: .hermes/ = identity, .exa-workspace/ = the desk.
        if recipient in ("exa", "Exa", "external"):
            try:
                from app.core.config import Paths as _Paths
                inbox = _Paths.exa_workspace / "inbox"
                inbox.mkdir(parents=True, exist_ok=True)
                path = inbox / f"{product.product_type}-{product.created_at[:10]}.md"
                path.write_text(f"# {product.title}\n\n{product.body}\n", encoding="utf-8")
                product.path = str(path)
                return DeliveryResult(
                    distributor=self.name, success=True,
                    detail=f"filed to the Exa desktop inbox ({path.name})",
                    path=str(path),
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("AgentDistributor exa-file-it failed: %s", e)
                return DeliveryResult(
                    distributor=self.name, success=False,
                    detail=f"exa-file-it failed: {e}",
                )
        try:
            # Resolve the name via the registry (the white pages)
            import asyncio
            from app.domain.agents.services import AgentService

            async def _resolve() -> int:
                async with self._session() as db:
                    agent = await AgentService(db).resolve_agent(recipient)
                    return agent.id

            agent_id = asyncio.run(_resolve())
        except ValueError as e:
            return DeliveryResult(
                distributor=self.name, success=False,
                detail=f"registry: {e}",  # unknown recipient — loud
            )
        except Exception as e:  # noqa: BLE001
            return DeliveryResult(
                distributor=self.name, success=False, detail=f"resolve failed: {e}",
            )

        if mode == "hand-it-a-task":
            try:
                import asyncio
                from app.domain.chat.services import ChatService

                async def _handoff() -> int:
                    async with self._session() as db:
                        from app.domain.chat.schemas import ChatRequest
                        svc = ChatService(db)
                        session = await svc._get_or_create_session(None, agent_id)
                        await svc.send_message(
                            ChatRequest(
                                agent_id=agent_id,
                                message=(
                                    f"## Task from a workflow\n\n"
                                    f"{product.title}\n\n{product.body}"
                                ),
                                session_id=session.id,
                            )
                        )
                        return session.id

                sid = asyncio.run(_handoff())
                return DeliveryResult(
                    distributor=self.name, success=True,
                    detail=f"handed to '{recipient}' (session {sid})",
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("AgentDistributor handoff failed: %s", e)
                return DeliveryResult(
                    distributor=self.name, success=False, detail=f"handoff failed: {e}",
                )

        # file-it (default): the agent's inbox folder
        try:
            inbox = self.agents_root / recipient / "inbox"
            inbox.mkdir(parents=True, exist_ok=True)
            path = inbox / f"{product.product_type}-{product.created_at[:10]}.md"
            path.write_text(f"# {product.title}\n\n{product.body}\n", encoding="utf-8")
            product.path = str(path)
            return DeliveryResult(
                distributor=self.name, success=True,
                detail=f"filed to '{recipient}' inbox ({path.name})",
                path=str(path),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("AgentDistributor file-it failed: %s", e)
            return DeliveryResult(
                distributor=self.name, success=False, detail=f"file-it failed: {e}",
            )




DISTRIBUTOR_CLASSES: Dict[str, type[WorkflowDistributor]] = {
    FileDistributor.name: FileDistributor,
    DisplayDistributor.name: DisplayDistributor,
    ToastDistributor.name: ToastDistributor,
    AgentDistributor.name: AgentDistributor,
}


def create_default_distributors() -> Dict[str, WorkflowDistributor]:
    """Factory — the builtin distributor set (pipeline pattern)."""
    return {name: cls() for name, cls in DISTRIBUTOR_CLASSES.items()}


def deliver_product(
    product: WorkflowProduct,
    distributors: Optional[Dict[str, WorkflowDistributor]] = None,
    names: Optional[list[str]] = None,
) -> list[DeliveryResult]:
    """Deliver a product through the named distributors.

    Args:
        product: the product to deliver
        distributors: distributor map (defaults to create_default_distributors())
        names: distributor names to use; None → all registered

    Returns:
        One DeliveryResult per distributor used (never raises).
    """
    pool = distributors if distributors is not None else create_default_distributors()
    targets = names or list(pool.keys())
    results: list[DeliveryResult] = []
    for name in targets:
        dist = pool.get(name)
        if dist is None:
            results.append(DeliveryResult(distributor=name, success=False, detail="unknown distributor"))
            continue
        try:
            results.append(dist.deliver(product))
        except Exception as e:  # noqa: BLE001
            logger.warning("deliver_product %s failed: %s", name, e)
            results.append(DeliveryResult(distributor=name, success=False, detail=str(e)))
    return results


def clear_products(base_dir: Optional[Path] = None) -> int:
    """Delete all product files + the display index.

    Returns the number of files removed. Used by the Products
    page's Clear action (stale-data reset).
    """
    base = base_dir or _products_dir()
    removed = 0
    if not base.exists():
        return 0
    # remove the index + product markdown files (not state.json — that's
    # dedup state for monitors, not a product)
    for f in base.iterdir():
        if f.name == "state.json":
            continue
        if f.is_file() and (f.suffix in {".md", ".json"} or f.name == "products.json"):
            try:
                f.unlink()
                removed += 1
            except OSError:
                logger.warning("clear_products: could not remove %s", f.name)
    return removed


def delete_product(product_id: str, base_dir: Optional[Path] = None) -> bool:
    """Delete ONE product: its file (if any) + its display-index entry.

    The single-product delete (Phase G, 2026-08-17) — the Products
    page's per-row + bulk delete. Returns True if the index entry
    was removed (the file may not exist — the index is the truth).

    The product_id is the entry's CREATED_AT — the true per-entry
    identity (the collision fix, 2026-08-18: the old basename
    matching deleted EVERY entry sharing a same-day same-type file
    name — e.g. 15 'readiness_report-2026-08-15.md' entries at
    once). created_at is unique per entry. The entry's path tells
    us which file to remove. Never removes state.json (monitor
    dedup state, not a product).
    """
    base = base_dir or _products_dir()
    if not base.exists():
        return False
    # 1. remove the index entry (match by created_at — the identity)
    index_path = base / "products.json"
    removed_entry = False
    removed_path = None
    if index_path.exists():
        try:
            import json as _json
            entries = _json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(entries, list):
                kept = []
                for e in entries:
                    if e.get("created_at") == product_id:
                        removed_path = e.get("path")
                        removed_entry = True
                    else:
                        kept.append(e)
                if removed_entry:
                    index_path.write_text(
                        _json.dumps(kept, indent=2, ensure_ascii=False),
                        encoding="utf-8",
                    )
        except (json.JSONDecodeError, OSError):
            logger.warning("delete_product: could not read the index %s", index_path.name)
    # 2. remove the product file (the entry's path, if it exists).
    # Relative entry paths (e.g. "data/monitor/r1.md") resolve against
    # the base_dir — never the process cwd (the 2026-08-18 fix: the
    # cwd-resolution silently no-op'd the file removal).
    if removed_path:
        f = Path(removed_path)
        if not f.is_absolute():
            f = base / removed_path  # relative entry paths live under the base_dir
        if f.exists() and f.is_file():
            try:
                f.unlink()
            except OSError:
                logger.warning("delete_product: could not remove %s", f.name)
    return removed_entry
