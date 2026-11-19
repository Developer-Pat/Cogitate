"""
Tools domain registry.

Provides tool registration, discovery, and runtime management.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def _db_path() -> Path:
    """THE DATABASE FILE this module reads and writes, resolved through settings.

    Never `Paths.shared_db`: that is a dataclass FIELD DEFAULT — a fixed
    `BASE_DIR/cogitate.db` — so it ignores `DATABASE_URL`. Reading the class
    attribute here is how the test suite came to write rows straight into the
    operator's live database while every redirected path (agents, trash, data)
    followed `Paths.from_settings`. One locator, and it is the settings one.
    """
    from app.core.config import get_settings
    from app.core.config import Paths

    return Paths.from_settings(get_settings()).shared_db


def _fix_mode_granted() -> bool:
    """The fix-mode gate (Phase 2): read the persisted external-agent
    config from UserSettings — fix_mode ON means the user granted
    the admin tier. Sync sqlite read (the TriggerService pattern);
    the grant state is the first-class object.

    Module-level since 2026-08-19 (it was nested in
    init_default_registry — untestable + unreachable for patching;
    the delete-agent tool + the tests reference it directly).
    """
    import sqlite3 as _sqlite
    import json as _json
    try:
        conn = _sqlite.connect(_db_path())
        conn.row_factory = _sqlite.Row
        row = conn.execute(
            "SELECT settings FROM user_settings WHERE user_key = 'default'"
        ).fetchone()
        conn.close()
        if row is None:
            return False
        raw = row["settings"]
        # FIX (2026-08-19): the settings are stored as a JSON
        # STRING — reading it as a dict made the grant NEVER
        # register as on (the restart-backend gate was silently
        # always-denied since Phase 2; the claimed/verified
        # discipline caught it while testing delete-agent).
        blob = _json.loads(raw) if isinstance(raw, str) else (raw or {})
        saved = blob.get("external_agent") if isinstance(blob, dict) else None
        return bool(saved and saved.get("fix_mode"))
    except Exception:
        return False


@dataclass
class ToolDefinition:
    """Runtime tool definition."""

    name: str
    slug: str
    description: str
    handler: Optional[Callable] = None
    config_schema: Dict[str, Any] = field(default_factory=dict)
    arguments_schema: Dict[str, Any] = field(default_factory=dict)
    is_builtin: bool = False
    pass_through: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    capability: Optional[str] = None  # Phase A: canonical capability slug
    # (the ARM selection vocabulary) — declared by the handler class,
    # mirrored in the tools table.


class ToolRegistry:
    """
    Central registry for tool definitions.

    Provides in-memory registration and discovery of tools
    at runtime. Complements the database-backed ToolRegistryService.
    """

    _instance: Optional["ToolRegistry"] = None

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}

    @classmethod
    def get_instance(cls) -> "ToolRegistry":
        """Get singleton registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset registry (mainly for testing)."""
        cls._instance = None

    def register(
        self,
        name: str,
        slug: str,
        description: str,
        capability: Optional[str] = None,
        handler: Optional[Callable] = None,
        config_schema: Optional[Dict[str, Any]] = None,
        arguments_schema: Optional[Dict[str, Any]] = None,
        is_builtin: bool = False,
        pass_through: bool = False,
        **metadata: Any,
    ) -> None:
        """
        Register a tool definition.

        Args:
            name: Human-readable tool name
            slug: URL-friendly identifier
            description: Tool description
            handler: Optional async function to execute the tool
            config_schema: JSON Schema for tool configuration
            arguments_schema: JSON Schema for tool arguments (for LLM)
            is_builtin: Whether this is a built-in tool
            pass_through: If True, tool output bypasses the LLM and goes
                          directly to the user via SSE (default: False)
            **metadata: Additional metadata (icon, color, tags, etc.)
        """
        if slug in self._tools:
            logger.warning(f"Tool '{slug}' is already registered, overwriting")

        tool_def = ToolDefinition(
            name=name,
            slug=slug,
            description=description,
            handler=handler,
            config_schema=config_schema or {},
            arguments_schema=arguments_schema or {},
            is_builtin=is_builtin,
            pass_through=pass_through,
            metadata=metadata,
            capability=capability,
        )
        self._tools[slug] = tool_def

        if handler:
            self._handlers[slug] = handler

        logger.info(f"Registered tool: {slug}")

    def unregister(self, slug: str) -> bool:
        """
        Unregister a tool.

        Args:
            slug: Tool slug

        Returns:
            True if tool was removed, False if not found
        """
        if slug in self._tools:
            del self._tools[slug]
            self._handlers.pop(slug, None)
            logger.info(f"Unregistered tool: {slug}")
            return True
        return False

    def get(self, slug: str) -> Optional[ToolDefinition]:
        """
        Get tool definition by slug.

        Args:
            slug: Tool slug

        Returns:
            Tool definition or None
        """
        return self._tools.get(slug)

    def get_handler(self, slug: str) -> Optional[Callable]:
        """
        Get tool handler function.

        Args:
            slug: Tool slug

        Returns:
            Handler function or None
        """
        return self._handlers.get(slug)

    def list_tools(
        self,
        builtin_only: bool = False,
        with_handlers_only: bool = False,
    ) -> List[ToolDefinition]:
        """
        List registered tools.

        Args:
            builtin_only: Filter to built-in tools only
            with_handlers_only: Filter to tools with handlers

        Returns:
            List of tool definitions
        """
        tools = list(self._tools.values())

        if builtin_only:
            tools = [t for t in tools if t.is_builtin]

        if with_handlers_only:
            tools = [t for t in tools if t.handler is not None]

        return tools

    def has_tool(self, slug: str) -> bool:
        """Check if tool is registered."""
        return slug in self._tools

    def get_all_slugs(self) -> List[str]:
        """Get all registered tool slugs."""
        return list(self._tools.keys())

    async def execute_tool(
        self,
        tool_slug: str,
        tool_config: Dict[str, Any],
        arguments: Dict[str, Any],
    ) -> Any:
        """
        Execute a tool by slug.

        Args:
            tool_slug: Tool slug identifier
            tool_config: Tool configuration
            arguments: Tool arguments dict (passed as kwargs to handler)

        Returns:
            Tool execution result

        Raises:
            KeyError: If tool not found
            RuntimeError: If tool has no handler
        """
        if tool_slug not in self._tools:
            raise KeyError(f"Tool not found: {tool_slug}")

        handler = self._handlers.get(tool_slug)
        if not handler:
            raise RuntimeError(f"Tool '{tool_slug}' has no registered handler")

        return await handler(tool_config, **arguments)


# =============================================================================
# Decorator for Tool Registration
# =============================================================================


def tool(
    name: str,
    slug: str,
    description: str,
    config_schema: Optional[Dict[str, Any]] = None,
    arguments_schema: Optional[Dict[str, Any]] = None,
    is_builtin: bool = False,
    pass_through: bool = False,
    **metadata: Any,
) -> Callable:
    """
    Decorator to register a function as a tool handler.

    Usage:
        @tool(
            name="Calculator",
            slug="calculator",
            description="Perform mathematical calculations",
            config_schema={...},
            arguments_schema={...},
            icon="calculator",
            color="#28A745",
        )
        async def calculator_tool(config, expression: str):
            # Tool implementation
            return result
    """
    def decorator(func: Callable) -> Callable:
        registry = ToolRegistry.get_instance()
        registry.register(
            name=name,
            slug=slug,
            description=description,
            handler=func,
            config_schema=config_schema,
            arguments_schema=arguments_schema,
            is_builtin=is_builtin,
            pass_through=pass_through,
            **metadata,
        )
        return func

    return decorator


# =============================================================================
# Built-in Tool Registration Helper
# =============================================================================


class BuiltinToolRegistrar:
    """Helper class for registering built-in tools."""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry.get_instance()
        self._registered: List[str] = []

    def register_builtin(
        self,
        name: str,
        slug: str,
        description: str,
        handler: Callable,
        config_schema: Optional[Dict[str, Any]] = None,
        arguments_schema: Optional[Dict[str, Any]] = None,
        pass_through: bool = False,
        capability: Optional[str] = None,
        **metadata: Any,
    ) -> None:
        """Register a built-in tool.

        capability defaults from the handler CLASS's ``capability``
        attribute (declared next to slug/description) when not
        explicitly passed — the code defines the vocabulary, the
        registration site need not repeat it.
        """
        handler_class = getattr(handler, "__self__", None)
        if capability is None:
            capability = getattr(handler_class, "capability", None)
        if metadata.get("access_tier") is None and handler_class is not None:
            tier = getattr(handler_class, "access_tier", None)
            if tier:
                metadata["access_tier"] = tier
        self.registry.register(
            name=name,
            slug=slug,
            description=description,
            handler=handler,
            config_schema=config_schema,
            arguments_schema=arguments_schema,
            is_builtin=True,
            pass_through=pass_through,
            capability=capability,
            **metadata,
        )
        self._registered.append(slug)
        logger.debug(f"Registered built-in tool: {slug}")

    def get_registered_slugs(self) -> List[str]:
        """Get list of registered tool slugs."""
        return self._registered

    def unregister_all(self) -> None:
        """Unregister all tools registered by this registrar."""
        for slug in self._registered:
            self.registry.unregister(slug)
        self._registered.clear()


# =============================================================================
# Default Tool Registry Initialization
# =============================================================================


def _validate_tool_contracts(registry: ToolRegistry) -> None:
    """Validate all registered tools have required schemas (Phase E).

    The soft-failure audit (proposal: audit-tool-registration-
    contracts, Phase 1): every registered tool's arguments_schema
    must cover what its handler expects. A parameter the handler
    requires but the schema omits = the LLM sees an incomplete
    tool and makes wrong calls — silently. This makes the
    mismatch LOUD at startup.

    Checks per tool:
    - arguments_schema is non-empty with properties
    - arguments_schema has a 'required' field
    - every required param in the handler's execute() signature
      is covered by the schema (properties keys)
    """
    import inspect

    issues = []
    for slug, tool in sorted(registry._tools.items()):
        if not tool.arguments_schema or not isinstance(tool.arguments_schema.get("properties"), dict):
            issues.append(f"  ❌ '{slug}' ({tool.name}): arguments_schema is empty or has no properties")
            continue
        if "required" not in tool.arguments_schema:
            issues.append(f"  ⚠️  '{slug}' ({tool.name}): arguments_schema has no 'required' field")
        elif tool.arguments_schema.get("required") == []:
            pass  # explicitly all-optional — legitimate (agent-select)

        # the signature check: required handler params must be in the schema
        handler = tool.handler
        if handler is not None:
            try:
                sig = inspect.signature(handler)
                schema_props = set(tool.arguments_schema.get("properties", {}).keys())
                for pname, param in sig.parameters.items():
                    if pname in ("self", "config", "kwargs", "args"):
                        continue
                    if param.default is param.empty and pname not in schema_props:
                        issues.append(
                            f"  ❌ '{slug}' ({tool.name}): handler requires "
                            f"'{pname}' but arguments_schema omits it"
                        )
            except (ValueError, TypeError):
                # builtins / C handlers without introspectable signatures
                pass

    if issues:
        logger.warning("Tool contract validation issues:")
        for issue in issues:
            logger.warning(issue)
        logger.warning("Total: %d tool(s) with contract issues", len(issues))
    else:
        logger.info("All %d tools passed contract validation", len(registry._tools))


_DEFAULT_REGISTRY_INITIALIZED = False


def init_default_registry() -> ToolRegistry:
    """
    Initialize the default tool registry with built-in tools.

    This is called at application startup to register all
    built-in tools that don't require external dependencies.

    IDEMPOTENT (2026-08-11): the registry is a singleton, and this
    is invoked from main.py + monitor_nodes + context_indexer_nodes.
    Repeated calls re-registered every builtin, logging
    "Tool 'X' is already registered, overwriting" at each startup.
    The warning was a real signal: double registration. Guard so the
    builtins register exactly once.
    """
    global _DEFAULT_REGISTRY_INITIALIZED
    if _DEFAULT_REGISTRY_INITIALIZED:
        return ToolRegistry.get_instance()
    _DEFAULT_REGISTRY_INITIALIZED = True

    registry = ToolRegistry.get_instance()
    registrar = BuiltinToolRegistrar(registry)

    # ── Phase-2 VERIFY + ADMIN tools (2026-08-18, exa-expertise
    # program): every operation tool has a matching verify tool (or
    # verifies internally); admin tools refuse without the fix-mode
    # grant. The claimed/verified pattern: tools return VERIFIED
    # state, not intent.

    async def verify_trigger_config_handler(config: Dict[str, Any], trigger_id: str | None = None, **kwargs) -> Dict[str, Any]:
        """Read back a workflow trigger's config from the DB — the
        verification half of schedule changes."""
        trigger_id = trigger_id or kwargs.get("trigger_id")
        if not trigger_id:
            return {"success": False, "error": "trigger_id is required.", "error_type": "missing_argument"}
        from app.domain.workflows.services.trigger_service import TriggerService
        trig = TriggerService().get_trigger(trigger_id)
        if trig is None:
            return {"success": False, "error": f"No trigger '{trigger_id}'.", "error_type": "not_found"}
        # PHASE-6: the verified-facts channel — the read-back IS the
        # verification; the fact persists with its source.
        try:
            from app.domain.verification import store as _vstore
            _vstore.record_verified_fact(
                claim=f"Trigger '{trigger_id}' config (read back)",
                verified_by="verify-trigger-config",
                source="workflow_triggers table",
                detail=dict(getattr(trig, "config", None) or {}),
            )
        except Exception:
            pass
        return {
            "success": True,
            "trigger_id": trigger_id,
            "verified": True,
            "config": dict(getattr(trig, "config", None) or {}),
            "name": getattr(trig, "name", None),
            "is_active": getattr(trig, "is_active", None),
            "note": "Read back from the DB — this is the trigger's CURRENT config.",
        }

    registrar.register_builtin(
        name="Verify Trigger Config",
        slug="verify-trigger-config",
        capability="workflow-admin",
        description="Read back a workflow trigger's config from the DB — the verification half of schedule changes. Use after setting a schedule.",
        handler=verify_trigger_config_handler,
        arguments_schema={
            "type": "object",
            "properties": {
                "trigger_id": {"type": "string", "description": "The trigger id (e.g. 'rss-monitor-trigger')."},
            },
            "required": ["trigger_id"],
        },
    )

    async def verify_backend_health_handler(config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Check the backend's health — the verified state, not a
        guess. Hits the health endpoint if reachable; otherwise
        reports the process/port reality."""
        import urllib.request
        import json as _json
        base = os.environ.get("COGITATE_BACKEND_URL", "http://127.0.0.1:8000")
        try:
            with urllib.request.urlopen(f"{base}/api/v1/health", timeout=5) as resp:
                body = _json.loads(resp.read().decode("utf-8", "replace"))
                try:
                    from app.domain.verification import store as _vstore
                    _vstore.record_verified_fact(
                        claim=f"The backend is {body.get('status', '?')}",
                        verified_by="verify-backend-health",
                        source="health endpoint",
                        detail={"http": resp.status},
                    )
                except Exception:
                    pass
                return {
                    "success": True,
                    "verified": True,
                    "status": body.get("status", "?"),
                    "http": resp.status,
                    "url": base,
                    "note": "The backend responded — this is the verified state.",
                }
        except Exception as e:
            return {
                "success": False,
                "verified": False,
                "status": "unreachable",
                "error": str(e),
                "url": base,
                "note": "The backend did NOT respond to the health check.",
            }

    registrar.register_builtin(
        name="Verify Backend Health",
        slug="verify-backend-health",
        capability="system-diag",
        description="Check the backend's health endpoint — returns the VERIFIED state (reachable/unreachable), not a guess.",
        handler=verify_backend_health_handler,
        arguments_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    )



    async def restart_backend_handler(config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """ADMIN-TIER: restart the backend + VERIFY. The operation
        that failed in the wild (2026-08-18) made safe: gated by the
        fix-mode grant; reports the ACTUAL state after the restart."""
        if not _fix_mode_granted():
            return {
                "success": False,
                "error": "The fix-mode grant is OFF — restarting the backend requires the explicit user grant. Turn on Fix Mode in the Exa panel first.",
                "error_type": "admin_denied",
            }
        import subprocess
        from app.core.config import Paths
        # the uvicorn restart: the backend is run from backend/ with
        # the venv; restart = kill the current uvicorn + spawn anew.
        # The actual command honors the project's run shape.
        venv_py = Paths.root / ".venv" / "bin" / "python3"
        proc = None
        try:
            # find + kill the current uvicorn on :8000 (fuser — targeted)
            subprocess.run(["fuser", "-k", "8000/tcp"], capture_output=True, timeout=10)
        except Exception:
            pass
        try:
            proc = subprocess.Popen(
                [str(venv_py), "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=str(Paths.root / "backend"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as e:
            return {"success": False, "error": f"Restart failed to spawn: {e}", "error_type": "restart_failed"}
        # VERIFY: poll the health endpoint for up to 30s
        import urllib.request
        import time as _time
        import json as _json
        base = os.environ.get("COGITATE_BACKEND_URL", "http://127.0.0.1:8000")
        healthy = False
        status = "down"
        for _ in range(30):
            _time.sleep(1)
            try:
                with urllib.request.urlopen(f"{base}/api/v1/health", timeout=2) as resp:
                    body = _json.loads(resp.read().decode("utf-8", "replace"))
                    status = body.get("status", "?")
                    healthy = resp.status == 200
                    if healthy:
                        break
            except Exception:
                continue
        pid = proc.pid if proc else None
        return {
            "success": healthy,
            "verified": True,
            "status": status,
            "http": 200 if healthy else None,
            "pid": pid,
            "note": ("Backend restarted + VERIFIED healthy." if healthy
                     else "Backend restarted but did NOT become healthy within 30s — investigate."),
        }

    registrar.register_builtin(
        name="Restart Backend",
        slug="restart-backend",
        capability="system-diag",
        access_tier="keyed",  # PHASE-6-FIX (2026-08-19): 'admin' was NOT
        #   in the tier vocabulary (tier_for falls back to gras) — the
        #   handler's own fix-mode gate protected it, but the DECLARED
        #   tier must be the canonical 'keyed' so the runtime gates it too.
        description="ADMIN-TIER: restart the backend and verify it comes back healthy. Requires the fix-mode grant.",
        handler=restart_backend_handler,
        arguments_schema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    )

    # delete-agent (2026-08-19): the system-agent lifecycle tool —
    # Exa retiring an agent through the SAME repository path the API
    # uses. KEYED (fix-mode grant) + VERIFIED (read-back the row).
    async def delete_agent_handler(config: Dict[str, Any], agent_id: int | None = None, hard: bool = False, **kwargs) -> Dict[str, Any]:
        """ADMIN-TIER: delete an agent the sanctioned way (soft-delete +
        archive + BOM) or the PERMANENT scrub (hard=True, 2026-08-19).
        Gated by the fix-mode grant; VERIFIES by reading the row back;
        records the track record. Hard deletes are IRREVERSIBLE — the
        caller must have explicit user confirmation."""
        agent_id = agent_id if agent_id is not None else kwargs.get("agent_id")
        if agent_id is None:
            return {"success": False, "error": "agent_id is required.", "error_type": "missing_argument"}
        if hard is None:
            hard = bool(kwargs.get("hard", False))
        if not _fix_mode_granted():
            return {
                "success": False,
                "error": "The fix-mode grant is OFF — deleting an agent requires the explicit user grant. Turn on Fix Mode in the Exa panel first.",
                "error_type": "admin_denied",
            }
        try:
            from app.core.database import AsyncSessionLocal
            from app.domain.agents.repository import get_agent_repository
            async with AsyncSessionLocal() as session:
                repo = get_agent_repository(session)
                try:
                    if hard:
                        report = await repo.hard_delete_agent(int(agent_id))
                    else:
                        report = await repo.delete_agent(int(agent_id))
                except ValueError as e:
                    # the built-in protection (403 in the API)
                    return {"success": False, "error": str(e), "error_type": "protected"}
                if not report.get("deleted"):
                    return {"success": False, "error": f"Agent {agent_id} not found or already deleted.", "error_type": "not_found"}
                # VERIFY: soft — the row survives (deleted_at +
                # archived_path). hard — the row is GONE (which IS the
                # verification for a scrub).
                import sqlite3 as _sqlite
                conn = _sqlite.connect(_db_path())
                conn.row_factory = _sqlite.Row
                row = conn.execute(
                    "SELECT id, name, is_active, deleted_at, archived_path FROM agents WHERE id = ?",
                    (int(agent_id),),
                ).fetchone()
                conn.close()
                if hard:
                    verified = row is None  # scrubbed — the row is gone
                else:
                    verified = (
                        row is not None
                        and row["deleted_at"] is not None
                        and row["is_active"] == 0
                        and row["archived_path"] is not None
                    )
                # RECORD the track record (the honesty loop)
                try:
                    from app.domain.verification import store as _vstore
                    _vstore.record_operation(
                        agent="external-agent",
                        operation="delete-agent" + ("-hard" if hard else ""),
                        claimed=f"delete agent {agent_id}" + (" (PERMANENT)" if hard else ""),
                        verified=("row gone" if hard else (row["archived_path"] if row is not None else "?")),
                        outcome="verified" if verified else "mismatched",
                    )
                except Exception:
                    pass
                return {
                    "success": verified,
                    "verified": True,
                    "agent_id": int(agent_id),
                    "deleted": verified,
                    "hard": hard,
                    "bom": report.get("bom", {}),
                    "archived_path": row["archived_path"] if (row is not None and not hard) else None,
                    "note": (("Agent PERMANENTLY deleted + VERIFIED (scrubbed — the row is gone)."
                              if hard else "Agent deleted + VERIFIED (soft-delete, archived, recoverable via Restore).")
                             if verified else "Delete reported but the VERIFY read-back failed — investigate."),
                }
        except Exception as e:
            return {"success": False, "error": f"Delete failed: {e}", "error_type": "delete_failed"}

    registrar.register_builtin(
        name="Delete Agent",
        slug="delete-agent",
        capability="agent-admin",
        access_tier="keyed",
        description="ADMIN-TIER: retire an agent the sanctioned way. SOFT (hard=false, default): deactivate + archive + BOM — RECOVERABLE via restore-agent. HARD (hard=true): PERMANENT scrub — IRREVERSIBLE, nothing restores it. Requires the fix-mode grant + explicit user confirmation for hard.",
        handler=delete_agent_handler,
        arguments_schema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "integer",
                    "description": "The agent's numeric DB id (the agents list shows it).",
                },
                "hard": {
                    "type": "boolean",
                    "description": "True = PERMANENT scrub (IRREVERSIBLE — the row + workspace + memory all go). False = the recoverable soft-delete. Requires explicit user confirmation for True.",
                    "default": False,
                },
            },
            "required": ["agent_id"],
        },
    )

    # list-archived-agents (2026-08-19): the READ half of the
    # lifecycle — Exa can see what is archived (the user's ask:
    # 'Exa knows how to read archived agents'). GRAS (read-only).
    async def list_archived_agents_handler(config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """List the soft-deleted (archived) agents — id, name,
        deleted_at, archive folder. READ-ONLY: the same data the
        /agents/deleted API returns."""
        try:
            import sqlite3 as _sqlite
            conn = _sqlite.connect(_db_path())
            conn.row_factory = _sqlite.Row
            rows = conn.execute(
                "SELECT id, name, deleted_at, archived_path FROM agents "
                "WHERE deleted_at IS NOT NULL ORDER BY id"
            ).fetchall()
            conn.close()
            archived = [{
                "id": r["id"],
                "name": r["name"],
                "deleted_at": str(r["deleted_at"]) if r["deleted_at"] else None,
                "archive_folder": (str(r["archived_path"]).split("/")[-1] if r["archived_path"] else None),
            } for r in rows]
            return {
                "success": True,
                "verified": True,
                "archived": archived,
                "count": len(archived),
                "note": "Read from the agents table — the soft-deleted (archived) agents. Restore them with restore-agent.",
            }
        except Exception as e:
            return {"success": False, "error": f"Listing archived agents failed: {e}", "error_type": "query_failed"}

    registrar.register_builtin(
        name="List Archived Agents",
        slug="list-archived-agents",
        capability="agent-admin",
        description="List the soft-deleted (archived) agents — id, name, deleted_at, archive folder. READ-ONLY.",
        handler=list_archived_agents_handler,
        arguments_schema={"type": "object", "properties": {}, "required": []},
    )

    # restore-agent (2026-08-19): the UNDO half of the lifecycle —
    # Exa can bring an archived agent back through the SAME repository
    # path the UI's Restore button uses. KEYED (fix-mode grant) +
    # VERIFIED (read the row back: deleted_at cleared, is_active=1).
    async def restore_agent_handler(config: Dict[str, Any], agent_id: int | None = None, **kwargs) -> Dict[str, Any]:
        """ADMIN-TIER: restore an archived (soft-deleted) agent — the
        workspace moves back from the archive, the delete markers
        clear. Gated by the fix-mode grant; VERIFIES by reading the
        row back; records the track record."""
        agent_id = agent_id if agent_id is not None else kwargs.get("agent_id")
        if agent_id is None:
            return {"success": False, "error": "agent_id is required.", "error_type": "missing_argument"}
        if not _fix_mode_granted():
            return {
                "success": False,
                "error": "The fix-mode grant is OFF — restoring an agent requires the explicit user grant. Turn on Fix Mode in the Exa panel first.",
                "error_type": "admin_denied",
            }
        try:
            from app.core.database import AsyncSessionLocal
            from app.domain.agents.repository import get_agent_repository
            async with AsyncSessionLocal() as session:
                repo = get_agent_repository(session)
                try:
                    agent = await repo.restore_agent(int(agent_id))
                except ValueError as e:
                    return {"success": False, "error": str(e), "error_type": "not_archived"}
                # VERIFY: read the row back — deleted_at cleared, active
                import sqlite3 as _sqlite
                conn = _sqlite.connect(_db_path())
                conn.row_factory = _sqlite.Row
                row = conn.execute(
                    "SELECT id, name, is_active, deleted_at, archived_path FROM agents WHERE id = ?",
                    (int(agent_id),),
                ).fetchone()
                conn.close()
                verified = (
                    row is not None
                    and row["deleted_at"] is None
                    and row["is_active"] == 1
                    and row["archived_path"] is None
                )
                # RECORD the track record (the honesty loop)
                try:
                    from app.domain.verification import store as _vstore
                    _vstore.record_operation(
                        agent="external-agent",
                        operation="restore-agent",
                        claimed=f"restore agent {agent_id}",
                        verified=str(getattr(agent, "name", "?")),
                        outcome="verified" if verified else "mismatched",
                    )
                except Exception:
                    pass
                return {
                    "success": verified,
                    "verified": True,
                    "agent_id": int(agent_id),
                    "restored": verified,
                    "name": getattr(agent, "name", None),
                    "note": ("Agent restored + VERIFIED — the profile is back in the pool."
                             if verified else "Restore reported but the VERIFY read-back failed — investigate."),
                }
        except Exception as e:
            return {"success": False, "error": f"Restore failed: {e}", "error_type": "restore_failed"}

    registrar.register_builtin(
        name="Restore Agent",
        slug="restore-agent",
        capability="agent-admin",
        access_tier="keyed",
        description="ADMIN-TIER: restore an archived (soft-deleted) agent — the workspace moves back, the profile returns to the pool. The UNDO of delete-agent (soft). Requires the fix-mode grant.",
        handler=restore_agent_handler,
        arguments_schema={
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "integer",
                    "description": "The archived agent's numeric DB id (list-archived-agents shows it).",
                }
            },
            "required": ["agent_id"],
        },
    )

    # audit-consistency (2026-08-19): the system's consistency
    # audit — Exa's read-only system check (the user's ask: "part of
    # our system health should run through a checklist of the agents,
    # collections, workflows and attempt to rationalize them").
    # GRAS (read-only by contract — it REPORTS; repair is a separate
    # keyed action, never automatic).
    async def audit_consistency_handler(config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Run the system consistency audit — walk the reference
        graph and report every dangling edge (tool links, usage logs,
        sessions, grants, collections, workflow configs naming
        missing agents). READ-ONLY: reports; repair is explicit."""
        try:
            from app.domain.audit import ConsistencyAudit
            audit = ConsistencyAudit(_db_path())
            return audit.run()
        except Exception as e:
            return {"success": False, "error": f"Audit failed: {e}", "error_type": "audit_failed"}

    registrar.register_builtin(
        name="Audit System Consistency",
        slug="audit-consistency",
        capability="system-diag",
        description="Run the system consistency audit — every dangling reference (tool links, usage logs, sessions, grants, collections, workflow configs naming missing agents). READ-ONLY: reports; repair is a separate explicit action.",
        handler=audit_consistency_handler,
        arguments_schema={"type": "object", "properties": {}, "required": []},
    )

    # repair-consistency (2026-08-21): the KEYED half of the audit —
    # scrub the dangling references the audit found. ONE grant, the
    # WHOLE fix: the user approves this tool once, it deletes every
    # dangling edge (agent_tools/usage_logs/collection_items rows
    # pointing at missing ids), re-runs the audit to VERIFY (the
    # read-back), and records to the verification store. The empty
    # collections finding is REPORTED but NOT auto-deleted (the
    # user's planned Exa system-management test — the tool leaves
    # that decision to the user). Requires the fix-mode grant.
    async def repair_consistency_handler(config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Scrub the audit's dangling references — the sanctioned
        repair. Deletes the rows pointing at missing ids, re-runs
        the audit, records the verified outcome. The empty-collection
        finding is reported, never auto-deleted."""
        try:
            import sqlite3 as _sqlite
            from app.domain.audit import ConsistencyAudit

            db = _db_path()
            conn = _sqlite.connect(str(db))
            conn.row_factory = _sqlite.Row
            deleted: dict[str, int] = {}
            try:
                # the dangling-reference tables (the audit's BOM scope)
                tables = [
                    ("agent_tools", "agent_id", "tool link"),
                    ("usage_logs", "agent_id", "usage log"),
                    ("chat_sessions", "agent_id", "chat session"),
                    # collection_items is handled SEPARATELY below —
                    # it is entity_type-scoped (the generic agent-id
                    # check would wrongly delete tool/workflow rows
                    # whose ids don't look like agent ids)
                ]
                existing = {
                    r[0] for r in conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).fetchall()
                }
                for table, col, label in tables:
                    if table not in existing:
                        continue
                    cur = conn.execute(
                        f"DELETE FROM {table} WHERE {col} NOT IN (SELECT id FROM agents)"
                    )
                    if cur.rowcount:
                        deleted[f"{table}.{col}"] = cur.rowcount
                # dangling collection items — THREE scoped passes
                # (the entity_type discriminator is what keeps this
                # safe: a tool row's id is not an agent id, so an
                # unscoped 'NOT IN agents' delete would wrongly
                # remove it)
                cur = conn.execute(
                    "DELETE FROM collection_items "
                    "WHERE entity_type = 'agent' AND entity_id NOT IN "
                    "         (SELECT CAST(id AS TEXT) FROM agents)"
                )
                if cur.rowcount:
                    deleted["collection_items.missing_agent"] = cur.rowcount
                cur = conn.execute(
                    "DELETE FROM collection_items "
                    "WHERE entity_type = 'tool' AND entity_id NOT IN "
                    "         (SELECT CAST(id AS TEXT) FROM tools)"
                )
                if cur.rowcount:
                    deleted["collection_items.missing_tool"] = cur.rowcount
                cur = conn.execute(
                    "DELETE FROM collection_items "
                    "WHERE entity_type = 'workflow_list' AND entity_id NOT IN "
                    "         (SELECT CAST(id AS TEXT) FROM workflow_compositions)"
                )
                if cur.rowcount:
                    deleted["collection_items.missing_workflow"] = cur.rowcount
                conn.commit()
            finally:
                conn.close()

            # the READ-BACK VERIFY — re-run the audit; the dangling
            # reference counts must be zero (the empty-collection
            # finding stays — reported, not scrubbed)
            audit = ConsistencyAudit(db)
            after = audit.run()
            remaining = sum(
                len(v) for k, v in after["checks"].items()
                if k not in ("orphaned_collections",)
            )
            verified = remaining == 0

            try:
                from app.domain.verification import store as _vstore
                _vstore.record_verified_fact(
                    claim=f"Repair consistency: {sum(deleted.values()) or 0} dangling reference(s) removed",
                    verified_by="repair-consistency",
                    source="cogitate.db audit re-run",
                    detail={"deleted": deleted, "remaining": remaining, "verified": verified},
                )
            except Exception:
                pass

            return {
                "success": True,
                "deleted": deleted,
                "total_deleted": sum(deleted.values()) or 0,
                "verified": verified,
                "remaining_findings": remaining,
                "orphaned_collections": [
                    {"collection_id": f["collection_id"], "name": f.get("name")}
                    for f in after["checks"].get("orphaned_collections", [])
                ],
                "note": ("Scrubbed + VERIFIED (audit re-run). The empty "
                         "collections are REPORTED, not deleted — the user's "
                         "decision (planned Exa system-management test).")
                     if verified else
                     "Scrub ran but the audit still reports dangling "
                     "references — investigate before proceeding.",
            }
        except Exception as e:
            return {"success": False, "error": f"Repair failed: {e}", "error_type": "repair_failed"}

    registrar.register_builtin(
        name="Repair System Consistency",
        slug="repair-consistency",
        capability="system-diag",  # the FROZEN vocabulary — the
        # repair is the keyed half of the same system-diag
        # capability as audit-consistency; the admin-ness is the
        # access_tier metadata (keyed), not a new capability slug
        # (the vocabulary is frozen at Phase A — a new slug would
        # break the capability-taxonomy tests)
        access_tier="keyed",
        description="ADMIN-TIER: scrub the dangling references the consistency audit found (tool links, usage logs, collection items, chat sessions pointing at missing agents) — ONE approval, the WHOLE fix. Re-runs the audit to verify + records. Requires the fix-mode grant. Empty collections are REPORTED, never auto-deleted.",
        handler=repair_consistency_handler,
        arguments_schema={"type": "object", "properties": {}, "required": []},
    )

    # verify-http-evidence (2026-08-20): the log-check as a tool —
    # given a method + path (+ optional time window), does the
    # access-evidence journal show the request? This is what the
    # 2026-08-19 session did BY HAND (the uvicorn-log proof that
    # Exa really hit the audit endpoint) — now a reusable GRAS
    # read tool. The journal is backend/logs/access.log (the
    # middleware), NOT uvicorn's stdout-bound access log.
    async def verify_http_evidence_handler(config: Dict[str, Any], method: str | None = None, path: str | None = None, since: str | None = None, **kwargs) -> Dict[str, Any]:
        """Verify that a request happened: search the access-evidence
        journal for method + path (optionally since an ISO timestamp).
        Returns the matching lines — the EVIDENCE, not a claim."""
        method = (method or kwargs.get("method") or "").upper()
        path = path or kwargs.get("path") or ""
        since = since or kwargs.get("since")
        if not method or not path:
            return {"success": False, "error": "method + path are required.", "error_type": "missing_argument"}
        try:
            from app.core.config import Paths as _Paths
            journal = _Paths.access_log
            if not journal.exists():
                return {
                    "success": True, "verified": True, "found": False,
                    "note": f"No access journal at {journal} — the middleware may not have recorded requests yet.",
                }
            matches = []
            with open(journal, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(" | ", 1)
                    if len(parts) < 2:
                        continue
                    ts, req = parts[0], parts[1]
                    # req = "METHOD path status"
                    rparts = req.split(" ")
                    if len(rparts) < 3:
                        continue
                    req_method, req_path, req_status = rparts[0], rparts[1], rparts[2]
                    if req_method != method:
                        continue
                    if path not in req_path:
                        continue
                    if since and ts < since:
                        continue
                    matches.append({"timestamp": ts, "status": req_status, "request": f"{req_method} {req_path}"})
            return {
                "success": True,
                "verified": True,
                "found": len(matches) > 0,
                "matches": matches[-10:],  # the most recent 10
                "count": len(matches),
                "note": ("The access-evidence journal confirms the request."
                         if matches else "No matching request in the access-evidence journal."),
            }
        except Exception as e:
            return {"success": False, "error": f"Evidence check failed: {e}", "error_type": "evidence_check_failed"}

    registrar.register_builtin(
        name="Verify HTTP Evidence",
        slug="verify-http-evidence",
        capability="system-diag",
        description="Verify that a request actually happened — search the access-evidence journal for method + path (+ optional since timestamp). The EVIDENCE for a claim, not a guess.",
        handler=verify_http_evidence_handler,
        arguments_schema={
            "type": "object",
            "properties": {
                "method": {"type": "string", "description": "The HTTP method (GET, POST, PUT, DELETE)."},
                "path": {"type": "string", "description": "A substring of the request path (e.g. /api/v1/system/audit/consistency)."},
                "since": {"type": "string", "description": "Optional ISO timestamp — only matches after it."},
            },
            "required": ["method", "path"],
        },
    )

    # search-knowledge (Phase-2 REGISTRY entry; functional in Phase 4
    # when the RAG is wired): the RAG lookup wrapper.
    async def search_knowledge_handler(config: Dict[str, Any], query: str | None = None, **kwargs) -> Dict[str, Any]:
        """Search the RAG index for system knowledge (Phase 4, wired
        2026-08-18): the query is embedded + ANN-searched against the
        whole-wiki index; the results carry the source paths + scores.
        Returns the VERIFIED hits — the index is the ground truth."""
        query = query or kwargs.get("query")
        if not query:
            return {"success": False, "error": "query is required.", "error_type": "missing_argument"}
        try:
            from app.core.database import AsyncSessionLocal
            from app.domain.providers.embeddings import resolve_embedding_service
            from app.domain.tools.builtin.doc_vector_store import DocVectorStore
            from app.core.config import Paths as _Paths

            # THE EMBEDDING SERVICE IS RESOLVED, NOT DEFAULTED (the service-literals arc's model
            # half): this handler passes the tool runner's `config` dict and no database session, so
            # one is opened here. The store used to be built with `db_path` alone, which left its
            # `DEFAULT_EMBEDDING_MODEL`/`DEFAULT_EMBEDDING_DIMS`/`DEFAULT_OLLAMA_BASE` to decide what
            # the search embedded with.
            async with AsyncSessionLocal() as session:
                embedding = await resolve_embedding_service(session)
            if not embedding.resolved:
                return {
                    "success": False,
                    "error": embedding.report(),
                    "error_type": "embedding_unconfigured",
                }

            store = DocVectorStore.get_instance(
                db_path=str(_Paths.rag_index_path), embedding=embedding
            )
            emb = store.embed_query(query)
            if not emb:
                return {"success": False, "error": "Embedding failed (is the embedding server up?).", "error_type": "embed_failed"}
            hits = store.search(emb, top_k=5, min_score=0.25)
            return {
                "success": True,
                "verified": True,
                "query": query,
                "hits": [
                    {
                        "source": h.get("source_path"),
                        "heading": h.get("heading"),
                        "score": round(float(h.get("similarity_score", 0)), 3),
                        "snippet": (h.get("chunk_text") or "")[:240],
                    }
                    for h in hits
                ],
                "note": "The hits are the index's actual matches — verified against the RAG DB.",
            }
        except Exception as e:
            return {"success": False, "error": f"Knowledge search failed: {e}", "error_type": "search_failed"}

    registrar.register_builtin(
        name="Search Knowledge",
        slug="search-knowledge",
        capability="doc-lookup",
        description="Search the RAG knowledge index for system documentation (Phase 4: not yet wired).",
        handler=search_knowledge_handler,
        arguments_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The knowledge question (e.g. 'how does the trigger service work?')."},
            },
            "required": ["query"],
        },
    )

    # graph-query (Phase-2 REGISTRY entry; functional in Phase 5 when
    # the GraphService lands): the FK-walk topology wrapper.
    async def graph_query_handler(config: Dict[str, Any], entity: str | None = None, **kwargs) -> Dict[str, Any]:
        """Query the system topology graph — the neighbors/edges of an
        entity (Phase 5, wired 2026-08-19): the derived FK walk + the
        wiki link graph, behind the GraphService seam."""
        entity = entity or kwargs.get("entity")
        if not entity:
            return {"success": False, "error": "entity is required.", "error_type": "missing_argument"}
        try:
            from app.domain.graph import GraphService
            from app.domain.graph.derived import DerivedGraphProvider
            from app.domain.graph.wiki import WikiGraphProvider
            svc = GraphService([DerivedGraphProvider(), WikiGraphProvider()])
            found = svc.get_entity(entity)
            if found is None:
                return {"success": False, "error": f"No entity '{entity}' in the graph.", "error_type": "not_found"}
            neighbors = svc.get_neighbors(entity)
            return {
                "success": True,
                "verified": True,
                "entity": found,
                "edges": neighbors.get("edges", []),
                "note": "The edges are read from the DB (FK graph) + the wiki (link graph) — the verified topology.",
            }
        except Exception as e:
            return {"success": False, "error": f"Graph query failed: {e}", "error_type": "query_failed"}

    registrar.register_builtin(
        name="Graph Query",
        slug="graph-query",
        capability="db-query",
        description="Query the system topology graph — the neighbors/edges of an entity (Phase 5: not yet wired).",
        handler=graph_query_handler,
        arguments_schema={
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "The entity id (e.g. a workflow template, trigger, or agent)."},
            },
            "required": ["entity"],
        },
    )

    # open-page — the model moved from GUESSING a destination to being HANDED
    # the list. The enum is generated from the frontend route table
    # (domain/tools/page_map.py), so it cannot drift. The handler VERIFIES the
    # request against that map and returns a path; it does NOT navigate.
    #
    # The frontend is the single navigator (the study's term): it sees this
    # call, reads `path`, and moves with `appNavigation.openTarget`, which is
    # where the new-tab convention lives. Keeping navigation in the frontend is
    # what preserves today's behaviour — routing it through the ui_navigate
    # bridge would have silently changed marker jumps from a new tab to in
    # place.
    async def open_page_handler(config: Dict[str, Any], page: str | None = None, **kwargs) -> Dict[str, Any]:
        """Resolve a page name to a real destination in the app.

        LOUD, never guessing: an unknown page returns the nearest known labels
        instead of a plausible-looking wrong path.
        """
        from app.domain.tools.page_map import resolve_page

        page = page or kwargs.get("page")
        if not page:
            return {"success": False, "error": "page is required.",
                    "error_type": "missing_argument"}

        entry, candidates = resolve_page(str(page))
        if entry is None:
            return {
                "success": False,
                "error": f"'{page}' is not a page in this app.",
                "error_type": "not_found",
                "candidates": [c.as_dict() for c in candidates],
                "hint": ("Pick from candidates, or call with no argument to list "
                         "every page. Do not invent a path."),
            }

        return {
            "success": True,
            "verified": True,
            "path": entry.key,
            "label": entry.label,
            "kind": entry.kind,
            "navigation_requested": True,
            "note": (f"Opening {entry.label}. The app resolves the tab; do not "
                     f"claim more than that the page was opened."),
        }

    from app.domain.tools.page_map import page_keys, page_prompt

    registrar.register_builtin(
        name="Open Page",
        slug="open-page",
        capability="ui-navigate",
        description=(
            "Open a page in this app for the user. The list below is the COMPLETE "
            "set of destinations — never invent a path.\n" + page_prompt()
        ),
        handler=open_page_handler,
        arguments_schema={
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "enum": page_keys(),
                    "description": "The destination, exactly as listed in the tool description.",
                },
            },
            "required": ["page"],
        },
    )

    # Register Clipboard Tool
    # Register DateTime Tool
    from app.domain.tools.builtin.datetime_handler import DateTimeTool
    datetime_tool = DateTimeTool()

    registrar.register_builtin(
        name=datetime_tool.name,
        slug=datetime_tool.slug,
        description=datetime_tool.description,
        handler=datetime_tool.execute,
        config_schema=datetime_tool.config_schema,
        icon=datetime_tool.icon,
        color=datetime_tool.color,
        tags=datetime_tool.tags,
        arguments_schema=datetime_tool.arguments_schema,
    )

    # Register Set Timer Tool (the EXA-TIMER, 2026-08-28)
    from app.domain.tools.builtin.set_timer_handler import register_set_timer_tool
    register_set_timer_tool(registrar)

    # Register File Info Tool
    from app.domain.tools.builtin.file_info_handler import FileInfoTool
    file_info_tool = FileInfoTool()

    registrar.register_builtin(
        name=file_info_tool.name,
        slug=file_info_tool.slug,
        description=file_info_tool.description,
        handler=file_info_tool.execute,
        config_schema=file_info_tool.config_schema,
        icon=file_info_tool.icon,
        color=file_info_tool.color,
        tags=file_info_tool.tags,
        arguments_schema=file_info_tool.arguments_schema,
    )

    # Register Workspace Search Tool (2026-09-10). THE DISCOVERABILITY
    # GAP: search shipped as an operation on File Info, but an agent
    # perceives its tools as a LIST OF NAMES — adding an operation
    # changes no name, so an agent asked to search its workspace saw
    # nothing called search and correctly reported the capability
    # missing. This tool exists for the NAME and carries no logic: it
    # delegates to the same implementation, so the two cannot drift.
    from app.domain.tools.builtin.workspace_search_handler import WorkspaceSearchTool
    workspace_search_tool = WorkspaceSearchTool()

    registrar.register_builtin(
        name=workspace_search_tool.name,
        slug=workspace_search_tool.slug,
        description=workspace_search_tool.description,
        handler=workspace_search_tool.execute,
        config_schema=workspace_search_tool.config_schema,
        icon=workspace_search_tool.icon,
        color=workspace_search_tool.color,
        tags=workspace_search_tool.tags,
        arguments_schema=workspace_search_tool.arguments_schema,
    )

    # Register Publish Tool (Phase D — agents as publishers)
    from app.domain.tools.builtin.publish_handler import PublishTool
    publish_tool = PublishTool()

    registrar.register_builtin(
        name=publish_tool.name,
        slug=publish_tool.slug,
        description=publish_tool.description,
        handler=publish_tool.execute,
        config_schema=publish_tool.config_schema,
        icon=publish_tool.icon,
        color=publish_tool.color,
        tags=publish_tool.tags,
        arguments_schema=publish_tool.arguments_schema,
    )

    # Register Send Notification Tool (the _23 F5 build — Exa's
    # purpose-built "send the user a message" affordance: the
    # notification shape, not the raw bus conventions)
    from app.domain.tools.builtin.send_notification_handler import (
        register_send_notification_tool,
    )

    register_send_notification_tool(registrar)

    # Register Line Editor Tool
    # Register Text Tools Tool
    # Register Wikipedia Tool
    # Register Tavily Tool
    # Register DuckDuckGo Tool
    from app.domain.tools.builtin.duckduckgo_handler import DuckDuckGoTool
    duckduckgo_tool = DuckDuckGoTool()

    registrar.register_builtin(
        name=duckduckgo_tool.name,
        slug=duckduckgo_tool.slug,
        description=duckduckgo_tool.description,
        handler=duckduckgo_tool.execute,
        config_schema=duckduckgo_tool.config_schema,
        icon=duckduckgo_tool.icon,
        color=duckduckgo_tool.color,
        tags=duckduckgo_tool.tags,
        arguments_schema=duckduckgo_tool.arguments_schema,
    )

    # Register Wikipedia (the encyclopedia lookup, restored 2026-08-24)
    from app.domain.tools.builtin.wikipedia_handler import WikipediaTool
    wikipedia_tool = WikipediaTool()

    registrar.register_builtin(
        name=wikipedia_tool.name,
        slug=wikipedia_tool.slug,
        description=wikipedia_tool.description,
        handler=wikipedia_tool.execute,
        config_schema=wikipedia_tool.config_schema,
        icon=wikipedia_tool.icon,
        color=wikipedia_tool.color,
        tags=wikipedia_tool.tags,
        arguments_schema=wikipedia_tool.arguments_schema,
    )

    # Register Run Python (the compute meta-tool, 2026-08-24)
    from app.domain.tools.builtin.run_python_handler import RunPythonTool
    run_python_tool = RunPythonTool()

    registrar.register_builtin(
        name=run_python_tool.name,
        slug=run_python_tool.slug,
        description=run_python_tool.description,
        handler=run_python_tool.execute,
        config_schema=run_python_tool.config_schema,
        arguments_schema=run_python_tool.arguments_schema,
        icon=run_python_tool.icon,
        color=run_python_tool.color,
        tags=run_python_tool.tags,
        capability=run_python_tool.capability,
    )

    # Register Jina Reader Tool
    from app.domain.tools.builtin.jina_reader_handler import JinaReaderTool
    jina_reader_tool = JinaReaderTool()

    registrar.register_builtin(
        name=jina_reader_tool.name,
        slug=jina_reader_tool.slug,
        description=jina_reader_tool.description,
        handler=jina_reader_tool.execute,
        config_schema=jina_reader_tool.config_schema,
        arguments_schema=jina_reader_tool.arguments_schema,
        icon=jina_reader_tool.icon,
        color=jina_reader_tool.color,
        tags=jina_reader_tool.tags,
    )

    # Register Summarize LLM Tool
    # Register SQLite Query Tool
    from app.domain.tools.builtin.sqlite_query_handler import SqliteQueryTool
    sqlite_query_tool = SqliteQueryTool()

    registrar.register_builtin(
        name=sqlite_query_tool.name,
        slug=sqlite_query_tool.slug,
        description=sqlite_query_tool.description,
        handler=sqlite_query_tool.execute,
        config_schema=sqlite_query_tool.config_schema,
        icon=sqlite_query_tool.icon,
        color=sqlite_query_tool.color,
        tags=sqlite_query_tool.tags,
        arguments_schema=sqlite_query_tool.arguments_schema,
    )

    # Register SQLite Manager Tool
    # Register File Manager Tool
    from app.domain.tools.builtin.file_manager_handler import FileManagerTool
    file_manager_tool = FileManagerTool()

    registrar.register_builtin(
        name=file_manager_tool.name,
        slug=file_manager_tool.slug,
        description=file_manager_tool.description,
        handler=file_manager_tool.execute,
        config_schema=file_manager_tool.config_schema,
        icon=file_manager_tool.icon,
        color=file_manager_tool.color,
        tags=file_manager_tool.tags,
        arguments_schema=file_manager_tool.arguments_schema,
    )

  
    # Register Doc Index Tool
    from app.domain.tools.builtin.doc_index import DocIndexTool
    doc_index_tool = DocIndexTool()

    registrar.register_builtin(
        name=doc_index_tool.name,
        slug=doc_index_tool.slug,
        description=doc_index_tool.description,
        handler=doc_index_tool.execute,
        config_schema=doc_index_tool.config_schema,
        arguments_schema=doc_index_tool.arguments_schema,
        icon=doc_index_tool.icon,
        color=doc_index_tool.color,
        tags=doc_index_tool.tags,
        pass_through=True,
    )

    # Register Run POST Tool
    from app.domain.tools.builtin.run_post import RunPostTool
    run_post_tool = RunPostTool()

    registrar.register_builtin(
        name=run_post_tool.name,
        slug=run_post_tool.slug,
        description=run_post_tool.description,
        handler=run_post_tool.execute,
        config_schema=run_post_tool.config_schema,
        arguments_schema=run_post_tool.arguments_schema,
        icon=run_post_tool.icon,
        color=run_post_tool.color,
        tags=run_post_tool.tags,
    )

    # Register Sequential Thinking Tool
    from app.domain.tools.builtin.sequential_thinking_handler import SequentialThinkingTool
    sequential_thinking_tool = SequentialThinkingTool()

    registrar.register_builtin(
        name=sequential_thinking_tool.name,
        slug=sequential_thinking_tool.slug,
        description=sequential_thinking_tool.description,
        handler=sequential_thinking_tool.execute,
        config_schema=sequential_thinking_tool.config_schema,
        arguments_schema=sequential_thinking_tool.arguments_schema,
        icon=sequential_thinking_tool.icon,
        color=sequential_thinking_tool.color,
        tags=sequential_thinking_tool.tags,
    )

    # ── Mode Catalog Tool ─────────────────────────────────────────────────────

    # Register Mode Catalog Tool

    # Register Skill Reader Tool — the class shape (2026-09-02):
    # needs_workspace=True so the execution service injects the
    # agent's own folder as base_path — the reader then scans the
    # agent's personal skills (agents/<key>/skills/) in addition to
    # the global dir (the skills partition: generic repo-level,
    # agent-specific in the folder, one surface).
    from app.domain.tools.builtin.skill_reader_handler import SkillReaderTool
    skill_reader_tool = SkillReaderTool()
    registrar.register_builtin(
        name=skill_reader_tool.name,
        slug=skill_reader_tool.slug,
        capability=skill_reader_tool.capability,
        description=skill_reader_tool.description,
        handler=skill_reader_tool.execute,
        config_schema=skill_reader_tool.config_schema,
        arguments_schema=skill_reader_tool.arguments_schema,
        icon=skill_reader_tool.icon,
        color=skill_reader_tool.color,
        tags=skill_reader_tool.tags,
    )

    # Register Consult Tool (Consulting Agent)
    from app.domain.tools.builtin.consult_handler import consult_handler
    registrar.register_builtin(
        name="Consult",
        slug="consult",
        capability="system-diag",
        description="Ask the external agent (Hermes/OpenClaw) for a second opinion "
        "on what you observe. Pass your state as context + a question.",
        handler=consult_handler,
        config_schema={"type": "object", "properties": {}},
        arguments_schema={
            "type": "object",
            "properties": {
                "context": {"type": "string", "description": "What you observe (state, logs, snippet, error) — the ONLY information sent to the consultant"},
                "question": {"type": "string", "description": "The question to ask the consultant"},
                "skill_hint": {"type": "string", "description": "Optional Cogitate skill name for the consultant to follow (e.g. create-agent, analyze-logs)"},
            },
            "required": ["context", "question"],
        },
        icon="message-circle-question",
        color="#0EA5E9",
        tags=["consult", "external-agent", "debugging", "second-opinion"],
    )

    # Register Macro Manager
    from app.domain.tools.builtin.agent_manager_handler import AgentManagerTool
    from app.domain.tools.builtin.document_manager_handler import DocumentManagerTool
    from app.domain.tools.builtin.macro_manager_handler import MacroManagerTool
    registrar.register_builtin(
        name=MacroManagerTool.name,
        slug=MacroManagerTool.slug,
        description=MacroManagerTool.description,
        handler=MacroManagerTool.execute,
        config_schema=MacroManagerTool.config_schema,
        icon=MacroManagerTool.icon,
        color=MacroManagerTool.color,
        tags=MacroManagerTool.tags,
        arguments_schema=MacroManagerTool.arguments_schema,
    )
    registrar.register_builtin(
        name=DocumentManagerTool.name,
        slug=DocumentManagerTool.slug,
        description=DocumentManagerTool.description,
        handler=DocumentManagerTool.execute,
        config_schema=DocumentManagerTool.config_schema,
        icon=DocumentManagerTool.icon,
        color=DocumentManagerTool.color,
        tags=DocumentManagerTool.tags,
        arguments_schema=DocumentManagerTool.arguments_schema,
    )

    registrar.register_builtin(
        name=AgentManagerTool.name,
        slug=AgentManagerTool.slug,
        description=AgentManagerTool.description,
        handler=AgentManagerTool.execute,
        config_schema=AgentManagerTool.config_schema,
        icon=AgentManagerTool.icon,
        color=AgentManagerTool.color,
        tags=AgentManagerTool.tags,
        arguments_schema=AgentManagerTool.arguments_schema,
    )

    # Register Agent Select Tool (ARM Phase B — the yellow pages)
    from app.domain.tools.builtin.agent_select_handler import AgentSelectTool
    agent_select_tool = AgentSelectTool()
    registrar.register_builtin(
        name=agent_select_tool.name,
        slug=agent_select_tool.slug,
        description=agent_select_tool.description,
        handler=agent_select_tool.execute,
        config_schema=agent_select_tool.config_schema,
        arguments_schema=agent_select_tool.arguments_schema,
        icon=agent_select_tool.icon,
        color=agent_select_tool.color,
        tags=agent_select_tool.tags,
    )

    # Register Workflow Manager Tool
    from app.domain.tools.builtin.workflow_manager_handler import WorkflowManagerTool
    workflow_manager_tool = WorkflowManagerTool()
    registrar.register_builtin(
        name=workflow_manager_tool.name,
        slug=workflow_manager_tool.slug,
        description=workflow_manager_tool.description,
        handler=workflow_manager_tool.execute,
        config_schema=workflow_manager_tool.config_schema,
        arguments_schema=workflow_manager_tool.arguments_schema,
        tags=workflow_manager_tool.tags,
    )

    # Register Provider Manager Tool
    from app.domain.tools.builtin.provider_manager_handler import ProviderManagerTool
    provider_manager_tool = ProviderManagerTool()
    registrar.register_builtin(
        name=provider_manager_tool.name,
        slug=provider_manager_tool.slug,
        description=provider_manager_tool.description,
        handler=provider_manager_tool.execute,
        config_schema=provider_manager_tool.config_schema,
        arguments_schema=provider_manager_tool.arguments_schema,
        tags=provider_manager_tool.tags,
    )

    # Register System Diagnostics Tool
    from app.domain.tools.builtin.system_diagnostics_handler import SystemDiagnosticsTool
    system_diagnostics_tool = SystemDiagnosticsTool()
    registrar.register_builtin(
        name=system_diagnostics_tool.name,
        slug=system_diagnostics_tool.slug,
        description=system_diagnostics_tool.description,
        handler=system_diagnostics_tool.execute,
        config_schema=system_diagnostics_tool.config_schema,
        arguments_schema=system_diagnostics_tool.arguments_schema,
        tags=system_diagnostics_tool.tags,
    )



    # Register the AGENT SELF-STATE tools (2026-09-02, the shallow-
    # agent build): the keyed write tools an agent uses to maintain
    # its OWN workspace state (sources + facts). needs_workspace on
    # the handler classes gets the agent's folder injected as
    # base_path at execution (the 2026-08-24 grant mechanism).
    from app.domain.tools.builtin.agent_state_handler import (
        UpdateSourcesTool, UpdateStateTool,
    )
    # The AGENT BEAT tool (2026-09-10, the News Team arc): the agent
    # co-authors its own beat sheet (news-beats/<name>.md) while the
    # user talks — "add Janet Yellen to the people of interest". Same
    # workspace grant as the state tools, same verified read-back.
    from app.domain.tools.builtin.agent_beat_handler import UpdateBeatTool
    for _tool in (UpdateSourcesTool(), UpdateStateTool(), UpdateBeatTool()):
        registrar.register_builtin(
            name=_tool.name,
            slug=_tool.slug,
            description=_tool.description,
            handler=_tool.execute,
            config_schema=_tool.config_schema,
            arguments_schema=_tool.arguments_schema,
            icon=_tool.icon,
            color=_tool.color,
            tags=_tool.tags,
        )

    # THE NOTEBOOK (2026-10-13, the research-run arc): the per-assignment notebook the news
    # runs keep while they gather — measured, the alternative is re-fetching 91 URLs (26.9 M
    # chars over ~7 weeks) and losing the results at the end of every turn. Same workspace
    # grant as the state tools (needs_workspace -> the agent's own folder as base_path).
    from app.domain.tools.builtin.assignment_handler import (
        AddNoteTool,
        CloseAssignmentTool,
        OpenAssignmentTool,
        ReadAssignmentTool,
    )
    for _notebook_tool in (
        OpenAssignmentTool(), AddNoteTool(), ReadAssignmentTool(), CloseAssignmentTool(),
    ):
        registrar.register_builtin(
            name=_notebook_tool.name,
            slug=_notebook_tool.slug,
            description=_notebook_tool.description,
            handler=_notebook_tool.execute,
            config_schema=_notebook_tool.config_schema,
            arguments_schema=_notebook_tool.arguments_schema,
            icon=_notebook_tool.icon,
            color=_notebook_tool.color,
            tags=_notebook_tool.tags,
        )

    logger.info(
        f"Initialized default tool registry with {len(registrar.get_registered_slugs())} built-in tools"
    )

    _validate_tool_contracts(registry)
    return registry
