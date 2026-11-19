"""
Tool Execution Service.

Central service for orchestrating tool execution across the application.
Provides unified interface for executing tools on behalf of agents,
with configuration resolution, error handling, and usage logging.
"""

from __future__ import annotations
import json

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.tools.registry import ToolRegistry
from app.domain.tools.capabilities import is_keyed
from app.domain.tools.grant_service import AgentToolGrantService
from app.domain.tools.services import (
    ToolRegistryService,
    AgentToolService,
    ToolUsageService,
)
logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    """
    Result of a tool execution.

    Attributes:
        success: Whether the execution was successful
        tool_slug: URL-friendly identifier of the tool
        tool_name: Human-readable tool name
        result: The execution result (if successful)
        error: Error message (if failed)
        error_type: Type/class of error (if failed)
        execution_time_ms: Execution time in milliseconds
        tokens_used: Number of tokens consumed (if applicable)
        metadata: Additional execution metadata
        call_id: The LLM-assigned tool call ID (e.g. "call_abc123") used for message correlation
        pass_through: If True, result bypasses LLM context and goes directly to user via SSE
        summary: Short (<280 char) summary of the result for LLM context when pass_through is True
    """

    success: bool
    tool_slug: str
    tool_name: str
    result: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    execution_time_ms: int = 0
    tokens_used: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    call_id: Optional[str] = None
    pass_through: bool = False
    summary: Optional[str] = None

    @property
    def tool_call_id(self) -> Optional[str]:
        """Alias for ``call_id`` — the LLM-assigned unique call identifier.

        Provided so that consumers that expect the chat-layer field name
        (``tool_call_id``) work without modification after the duplicate
        ``chat.ToolExecutionResult`` class was removed from ``schemas.py``.
        """
        return self.call_id

    def to_llm_message(self) -> Dict[str, Any]:
        """
        Convert result to LLM-readable message format.

        ``call_id`` is the unique ID the LLM assigned to the tool call
        (e.g. ``call_abc123``).  It must be used as ``tool_call_id`` so the
        model can correlate the result with the original request.  Falling back
        to ``tool_slug`` is kept for safety but will break multi-call
        correlation when the same tool is invoked more than once in a turn.

        Returns:
            Dictionary in tool response format for LLM consumption
        """
        tool_call_id = self.call_id or self.tool_slug
        if self.success:
            return {
                "role": "tool",
                "content": str(self.result),
                "tool_call_id": tool_call_id,
            }
        else:
            return {
                "role": "tool",
                "content": f"Error: {self.error}",
                "tool_call_id": tool_call_id,
            }

    def to_message_dict(self) -> Dict[str, Any]:
        """
        Convert result to the chat-layer message dict format expected by
        ``build_tool_messages`` and the LLM API.

        Identical to ``to_llm_message`` but includes the ``name`` field,
        which some providers use for display purposes.

        Returns:
            Dictionary in tool-response format for LLM consumption
        """
        tool_call_id = self.call_id or self.tool_slug
        if self.success:
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": str(self.result),
                "name": self.tool_name,
            }
        else:
            return {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": f"Error: {self.error}",
                "name": self.tool_name,
            }

    def to_user_message(self) -> Dict[str, Any]:
        """
        Format result for direct user display via SSE (pass-through).

        Used when ``pass_through`` is True — the result is sent directly
        to the frontend as a ``tool_output`` SSE event, bypassing the LLM.

        Returns:
            Dictionary in SSE event format for frontend consumption
        """
        return {
            "type": "tool_output",
            "tool": self.tool_slug,
            "tool_name": self.tool_name,
            "content": str(self.result) if self.success else str(self.error),
            "success": self.success,
            "done": True,
        }

    def to_summary_message(self) -> Dict[str, Any]:
        """
        Format a thin summary for LLM context injection.

        Used when ``pass_through`` is True — injects a short summary
        (``<280`` chars) into the LLM context instead of the full tool output,
        keeping the model informed without consuming token budget on verbose results.

        Falls back to ``"Called {tool_name}"`` when ``summary`` is not set.

        Uses ``role: "user"`` (not ``role: "tool"``) because pass-through
        summaries are injected **without** a preceding ``role: "assistant"``
        message carrying ``tool_calls``.  DeepSeek (and other API providers
        with strict message ordering) rejects ``role: "tool"`` messages that
        lack a corresponding ``tool_calls`` predecessor.  Using ``user`` role
        avoids this requirement while keeping the model informed.

        Returns:
            Dictionary in system-notification format for LLM consumption
        """
        summary = self.summary or f"Called {self.tool_name}"
        tool_call_id = self.call_id or self.tool_slug
        return {
            "role": "user",
            "content": f"[System: Pass-through tool '{self.tool_name}' completed. Summary: {summary}]",
            "tool_call_id": tool_call_id,
        }


def declared_refusal(result: Any) -> Optional[Tuple[str, Optional[str]]]:
    """A handler's OWN verdict, when it returned one instead of raising (F3).

    The house convention for a handler that refuses is a dict —
    ``{"success": False, "error": "…", "error_type": "not_found"}`` is written by
    dozens of handlers in `app/domain/tools/registry.py` — and every one of them used
    to be stamped `success=True` by the caller, because only a RAISED exception was
    read as a failure. The consequences were measured, not guessed (see
    `local/_archive/tool-reliability/wrap-check.out.txt`): the log said
    `✅ TOOL EXECUTION SUCCESS`, the turn's tracker recorded the call as a success,
    and the refusal reached the MODEL as one, with the real verdict buried inside
    the payload.

    Returns ``(error, error_type)`` when the handler declared a failure, else
    ``None``. An unclassified refusal keeps ``error_type=None`` — the tracker counts
    those as `failures_unnamed` rather than inventing a class the handler never
    named.
    """
    if not isinstance(result, Mapping):
        return None
    if result.get("success") is not False:
        return None
    error = result.get("error") or result.get("message") or "the tool reported a failure"
    error_type = result.get("error_type")
    return str(error), (str(error_type) if error_type else None)


class ToolExecutionService:
    """
    Central service for tool execution.
    
    Provides unified interface for executing tools on behalf of agents,
    with configuration resolution, error handling, and usage logging.
    
    Example usage:
        ```python
        from app.domain.tools.execution_service import ToolExecutionService
        
        async with get_db_session() as db:
            service = ToolExecutionService(db)
            result = await service.execute_tool_for_agent(
                agent_id="agent-123",
                tool_slug="run-python",
                arguments={"code": "result = 2 + 2"},
                session_id="session-456",
            )
            
            if result.success:
                print(f"Result: {result.result}")
            else:
                print(f"Error: {result.error}")
        ```
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the Tool Execution Service.
        
        Args:
            db: AsyncSession database connection
        """
        self.db = db
        self.tool_registry = ToolRegistry.get_instance()
        self.tool_service = ToolRegistryService(db)
        self.agent_tool_service = AgentToolService(db)
        self.usage_service = ToolUsageService(db)

    async def execute_tool_for_agent(
        self,
        agent_id: int | None,
        tool_slug: str,
        arguments: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> ToolExecutionResult:
        """
        Execute a tool on behalf of an agent.

        Args:
            agent_id: Agent identifier (integer)
            tool_slug: Tool slug to execute
            arguments: Tool arguments from LLM
            session_id: Optional session ID for logging

        Returns:
            ToolExecutionResult with success status and result

        Raises:
            No exceptions raised - errors are captured in ToolExecutionResult
        """
        start_time = time.time()

        try:
            # 1. Validate the tool is available to the agent
            # THE PARADIGM COMPLETION (2026-08-19): GRAS tools are
            # available BY DEFAULT (minus explicit exclusions); keyed
            # tools need the enabled link (the grant check follows).
            # The system-manager path (agent_id None) keeps its
            # tool-collection permissions path.
            agent_tool = None  # Initialize for system manager (agent_id is None) path
            if agent_id is not None:
                from app.domain.tools.capabilities import tier_for as _tier_for
                # THE TIER comes from the REGISTRY definition first (the
                # paradigm surface — the DB row may lag or be absent for
                # builtins in tests); the DB row is the fallback.
                reg_tool = self.tool_registry.get(tool_slug)
                if reg_tool is not None:
                    capability = getattr(reg_tool, "capability", None)
                    meta = getattr(reg_tool, "metadata", {}) or {}
                    tier_override = meta.get("access_tier")
                else:
                    tool_probe = await self.tool_service.get_tool_by_slug(tool_slug)
                    if tool_probe is None:
                        error_msg = f"Tool '{tool_slug}' not found in database"
                        logger.warning(f"⚠️  {error_msg}")
                        return ToolExecutionResult(
                            success=False,
                            tool_slug=tool_slug,
                            tool_name=tool_slug,
                            error=error_msg,
                            error_type="ToolNotFound",
                        )
                    capability = getattr(tool_probe, "capability", None)
                    tier_override = getattr(tool_probe, "access_tier", None)
                # the declared access_tier is used DIRECTLY (gras/keyed);
                # else derive from the capability
                if tier_override in ("gras", "keyed"):
                    tier = tier_override
                else:
                    tier = _tier_for(capability)
                # THE KIT IS THE TOOL SURFACE (2026-09-10). Visibility —
                # the tool list sent to the LLM — comes from the agent's
                # KITS (get_enabled_tools_for_agent), but this permission
                # check read the legacy agent_tools table instead. On a
                # kit-provisioned agent that table is EMPTY, so every
                # keyed tool was OFFERED and then refused ("not enabled
                # for this agent"); the LLM believed it had a tool, was
                # told it did not, and replied empty. The kit is the one
                # home — consult it. The agent_tools row survives only as
                # an explicit exclusion.
                agent_tool = await self.agent_tool_service.get_agent_tool_by_slug(
                    str(agent_id), tool_slug
                )
                kit_slugs = await self._toolkit_slugs_for_agent(str(agent_id))
                in_kit = kit_slugs is not None and tool_slug in kit_slugs
                if tier == "gras":
                    # default-on: blocked ONLY by an explicit exclusion
                    # (an agent_tools row with is_enabled=0)
                    if agent_tool is not None and not agent_tool.is_enabled:
                        error_msg = f"Tool '{tool_slug}' is excluded for this agent"
                        logger.warning(f"⚠️  {error_msg}")
                        return ToolExecutionResult(
                            success=False,
                            tool_slug=tool_slug,
                            tool_name=tool_slug,
                            error=error_msg,
                            error_type="ToolExcluded",
                        )
                else:
                    # keyed: the kit membership (or a legacy enabled link)
                    # is the entry gate (the grant check follows at step 2.5)
                    if not (in_kit or (agent_tool is not None and agent_tool.is_enabled)):
                        error_msg = f"Tool '{tool_slug}' is not enabled for this agent"
                        logger.warning(f"⚠️  {error_msg}")
                        return ToolExecutionResult(
                            success=False,
                            tool_slug=tool_slug,
                            tool_name=tool_slug,
                            error=error_msg,
                            error_type="ToolNotEnabled",
                        )

            # 2. Get tool definition from database
            tool_def = await self.tool_service.get_tool_by_slug(tool_slug)
            if not tool_def:
                error_msg = f"Tool '{tool_slug}' not found in database"
                logger.warning(f"⚠️  {error_msg}")  # WARNING - expected failure
                return ToolExecutionResult(
                    success=False,
                    tool_slug=tool_slug,
                    tool_name=tool_slug,
                    error=error_msg,
                    error_type="ToolNotFound",
                )

            # 2.5 KEYED TIER (Phase C): a keyed tool needs an explicit
            # grant (study 11 — slug = identity, grant = access).
            # The system-manager path (agent_id None) is not gated
            # here — it uses tool-collection permissions until Phase D.
            if agent_id is not None:
                capability = tool_def.capability
                # per-tool tier override (ARM Phase B): a read-only
                # tool in a keyed family (agent-select = gras despite
                # agent-admin) declares access_tier on the tool row
                tier_override = getattr(tool_def, "access_tier", None)
                keyed = is_keyed(tier_override if tier_override else capability)
                if keyed:
                    grant_service = AgentToolGrantService(self.db)
                    has_grant = await grant_service.has_grant(
                        str(agent_id), tool_def.id
                    )
                    if not has_grant:
                        error_msg = (
                            f"Tool '{tool_slug}' requires a grant to execute "
                            f"(keyed tier: {capability})."
                        )
                        logger.warning(f"🔑 {error_msg}")
                        return ToolExecutionResult(
                            success=False,
                            tool_slug=tool_slug,
                            tool_name=tool_slug,
                            error=error_msg,
                            error_type="ToolKeyRequired",
                        )

            # 3. Resolve configuration (agent > global)
            # When agent_tool is None (system manager path), use empty dict as config
            config = self._resolve_config(
                agent_tool.config if agent_tool else {},
                tool_def.config_schema
            )

            # 3.5 THE WORKSPACE-READ GRANT (2026-08-24): a tool
            # declaring needs_workspace gets the AGENT'S OWN
            # workspace injected as the base_path (the agent owns
            # its workspace; the sandbox's read_file/list_dir are
            # scoped to it). An explicit config base_path wins.
            if config.get("base_path") in (None, "", ".") and agent_id is not None:
                # the "." case: a schema default of "." (the file-info
                # trap, 2026-09-09) resolves to the process CWD — the
                # backend dir, NOT the agent's workspace. Treat it as
                # unset so the injection still applies.
                reg = self.tool_registry.get(tool_slug)
                # needs_workspace lives on the HANDLER's class (the
                # instance — the same __self__ pattern register_builtin
                # uses for capability/access_tier)
                _handler = getattr(reg, "handler", None)
                _needs_ws = bool(
                    _handler is not None
                    and getattr(getattr(_handler, "__self__", None), "needs_workspace", False)
                )
                if _needs_ws:
                    try:
                        from sqlalchemy import select
                        from app.infrastructure.database.models import Agent as _Agent
                        from app.core.config import Paths as _Paths
                        row = await self.db.execute(
                            select(_Agent.workspace_key).where(_Agent.id == int(agent_id))
                        )
                        wk = row.scalar_one_or_none()
                        if wk:
                            config["base_path"] = str(_Paths.agents_dir / wk)
                            logger.info(
                                "🔓 run-python workspace grant: %s", config["base_path"]
                            )
                    except Exception as _we:  # noqa: BLE001
                        logger.warning("workspace grant resolution failed: %s", _we)

            # 4. Validate arguments against schema (skip for registry-based tools)
            # Registry-based tools (builtin tools) validate their own arguments in handlers
            # arguments_schema describes what the LLM must supply; config_schema is for admin
            # settings and must NOT be used here.
            registry_tool = self.tool_registry.get(tool_slug)
            if registry_tool is None:
                # Only validate for non-registry tools (external tools)
                validation_error = self._validate_arguments(
                    arguments,
                    tool_def.arguments_schema or {}
                )
                if validation_error:
                    logger.warning(
                        f"⚠️  Tool '{tool_slug}' argument validation failed: {validation_error}"
                    )
                    return ToolExecutionResult(
                        success=False,
                        tool_slug=tool_slug,
                        tool_name=tool_def.name,
                        error=validation_error,
                        error_type="ValidationError",
                    )

            # 5. Execute tool
            result = await self._execute_tool(tool_slug, arguments, config, tool_def)

            # 6. Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)

            # 6b. THE HANDLER'S OWN VERDICT (F3, the tool-reliability arc). A handler
            # reports a refusal by RETURNING a dict with `success: False` — the house
            # convention — and until this line the wrapper stamped `success=True` over
            # every one of them: the log said ✅, the tracker recorded a success, and
            # the refusal was handed to the model as one. The verdict is read ONCE
            # here and everything below (the usage row, the honesty loop, what the
            # caller and the model receive) follows it.
            refusal = declared_refusal(result)
            call_succeeded = refusal is None

            # 7. Log usage with the outcome the call actually HAD
            try:
                await self.usage_service.log_usage(
                    tool_id=tool_def.id,
                    agent_id=str(agent_id),
                    session_id=session_id,
                    success=call_succeeded,
                    execution_time_ms=execution_time_ms,
                    metadata={"arguments": arguments, "result": result},
                )
            except Exception as log_error:
                logger.warning(f"Failed to log tool usage: {log_error}")

            # 7b. Increment usage_count REGARDLESS of the log row —
            # log_usage silently skips non-UUID agent_ids, but the
            # operational signal must be honest for every call
            # (Phase E — the ARM selection signal). A refusal was still a call.
            try:
                from app.domain.tools.services import ToolRegistryService
                await ToolRegistryService(self.db).increment_usage_count(
                    tool_def.id
                )
            except Exception as count_error:
                logger.warning(f"Failed to increment usage count: {count_error}")

            # THE HONESTY-LOOP RECORD (2026-09-01, the user's go —
            # the candidate standard for new agents): every tool
            # execution records its claimed-vs-verified outcome to the
            # track record. The loop's power: it doesn't make the
            # agent honest, it makes the SYSTEM verify.
            try:
                from app.domain.verification import store as _vstore

                _vstore.record_operation(
                    agent=f"agent:{agent_id}",
                    operation=f"tool:{tool_slug}",
                    claimed=json.dumps(arguments)[:200],
                    verified="success" if call_succeeded else "failure",
                    outcome="verified" if call_succeeded else "mismatched",
                )
            except Exception:
                pass

            if refusal is not None:
                error_text, error_type = refusal
                logger.warning(
                    "⚠️  Tool '%s' reported a failure: %s (error_type=%s) — the "
                    "caller is told, and so is the model (F3)",
                    tool_slug, error_text, error_type,
                )
                return ToolExecutionResult(
                    success=False,
                    tool_slug=tool_slug,
                    tool_name=tool_def.name,
                    # the handler's own payload rides along: the verdict is now the
                    # caller's, but nothing the handler said is thrown away
                    result=result,
                    summary=result.get("summary") if isinstance(result, dict) else None,
                    error=error_text,
                    error_type=error_type,
                    execution_time_ms=execution_time_ms,
                )

            return ToolExecutionResult(
                success=True,
                tool_slug=tool_slug,
                tool_name=tool_def.name,
                result=result,
                summary=result.get("summary") if isinstance(result, dict) else None,
                execution_time_ms=execution_time_ms,
            )

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Log as ERROR - unexpected exception
            logger.error(
                f"❌ Tool '{tool_slug}' execution threw exception: {e}",
                exc_info=True
            )

            # Log failure (skip on error to avoid schema issues)
            tool_def = await self.tool_service.get_tool_by_slug(tool_slug)
            if tool_def:
                try:
                    await self.usage_service.log_usage(
                        tool_id=tool_def.id,
                        agent_id=str(agent_id),
                        session_id=session_id,
                        success=False,
                        execution_time_ms=execution_time_ms,
                        error_message=str(e),
                    )
                except Exception as log_error:
                    logger.warning(f"Failed to log tool usage: {log_error}")

            # THE HONESTY-LOOP RECORD — the failure side (the
            # claimed vs the mismatch).
            try:
                from app.domain.verification import store as _vstore

                _vstore.record_operation(
                    agent=f"agent:{agent_id}",
                    operation=f"tool:{tool_slug}",
                    claimed=json.dumps(arguments)[:200],
                    verified="failure",
                    outcome="mismatched",
                )
            except Exception:
                pass

            return ToolExecutionResult(
                success=False,
                tool_slug=tool_slug,
                tool_name=tool_slug,
                error=str(e),
                error_type=type(e).__name__,
                execution_time_ms=execution_time_ms,
            )

    async def get_enabled_tools_for_agent(
        self,
        agent_id: str,
    ) -> List[Dict[str, Any]]:
        """Get the agent's available tools in LLM-ready format.

        THE PARADIGM COMPLETION (2026-08-19, the user's call): the
        manual agent_tools grid was the unfinished half of the
        tooling rewrite. The canonical rule (study 11 / Phase C):
        - GRAS tools (read-only tier) are available to every agent
          BY DEFAULT — no assignment row needed. An explicit
          agent_tools row with is_enabled=0 EXCLUDES one.
        - KEYED tools need an assignment row (is_enabled=1) — and
          the grant, enforced at execution.
        """
        from app.domain.tools.capabilities import tier_for
        # the agent's explicit links: enabled (keyed grants) + the
        # disabled ones (GRAS exclusions)
        agent_tools = await self.agent_tool_service.list_agent_tools(str(agent_id))
        enabled_slugs = {
            at.tool.slug for at in agent_tools
            if at.tool and at.is_enabled
        }
        excluded_slugs = {
            at.tool.slug for at in agent_tools
            if at.tool and not at.is_enabled
        }

        # THE TOOLKIT POLICY (2026-08-24, the proposal's core rule):
        # the agent OWNS a kit — agents.kit_id references a TOOL-typed
        # collection (entity_type='tool'). The OWNED kit IS the
        # surface — the GRAS default is SUPPRESSED. The surface = the
        # tools granted to the owned kit (tool_collection_permissions).
        # An agent owning an EMPTY kit gets NO tools (a shallow bot
        # with nothing to hallucinate). Agents without a kit keep the
        # current default.
        kit_slugs: set[str] | None = None
        try:
            kit_slugs = await self._toolkit_slugs_for_agent(str(agent_id))
        except Exception as _e:
            logger.warning(f"Toolkit policy lookup failed (falling back to the default): {_e}")
            kit_slugs = None

        tool_definitions = []
        seen = set()

        if kit_slugs is not None:
            # THE KIT IS THE SURFACE: ONLY the kit's granted tools —
            # no GRAS default, no agent_tools links. An EMPTY kit =
            # zero tools (the shallow-bot fix: nothing to
            # hallucinate). The kit's tools come from the registry
            # (matched by slug).
            for tool in self.tool_registry.list_tools():
                slug = getattr(tool, "slug", None)
                if not slug or slug not in kit_slugs:
                    continue
                tool_def = self._convert_tool_to_llm_format(tool)
                tool_definitions.append(tool_def)
                seen.add(slug)
            return tool_definitions

        # 1. the REGISTRY surface: GRAS tools default-on (minus
        #    exclusions); keyed tools need the enabled link
        for tool in self.tool_registry.list_tools():
            slug = getattr(tool, "slug", None)
            if not slug:
                continue
            capability = getattr(tool, "capability", None)
            # the tier override lives in metadata (access_tier) — its
            # VALUE is 'gras'/'keyed' directly (not a capability to
            # look up); else derive from the capability
            meta = getattr(tool, "metadata", {}) or {}
            tier_override = meta.get("access_tier")
            if tier_override in ("gras", "keyed"):
                tier = tier_override
            else:
                tier = tier_for(capability)
            if tier == "gras":
                # default-on, minus the explicit exclusions
                if slug in excluded_slugs:
                    continue
            else:
                # keyed: requires the enabled link
                if slug not in enabled_slugs:
                    continue
            tool_def = self._convert_tool_to_llm_format(tool)
            tool_definitions.append(tool_def)
            seen.add(slug)

        # 2. the DB-only surface (custom/external tools — created via
        #    create_tool, never in the registry): they are listed only
        #    when explicitly enabled for the agent (no tier default)
        for at in agent_tools:
            if not at.tool or not at.is_enabled:
                continue
            slug = at.tool.slug
            if slug in seen:
                continue
            tool_def = self._convert_tool_to_llm_format(at.tool)
            tool_definitions.append(tool_def)

        return tool_definitions

    async def _toolkit_slugs_for_agent(self, agent_id: str) -> set[str] | None:
        """The agent's toolkit surface, or None if no kit is owned.

        THE POLICY (2026-08-24, the user's ownership correction;
        2026-09-04, the _35 build P2 — THE UNION): the agent OWNS
        its kits — the agent_kits JOIN rows (plural, many-to-many)
        ∪ the singular agents.kit_id slot (the back-compat read —
        covers mid-run adoptions written before the boot sync). NOT
        a membership: 'the agent owns the kit, the kit should not
        own the agent'. The surface = the UNION of all owned kits'
        granted tools (tool_collection_permissions), deduped.
        Returns None when the agent owns NO kit (the caller keeps
        the default surface); returns the (possibly EMPTY) slug set
        when the agent owns kits (the kits ARE the surface — any
        kit suppresses the GRAS default; all-empty kits = no tools).
        """
        from app.infrastructure.database.models import Agent
        from app.domain.agent_kits.model import AgentKit
        from app.domain.tools.tool_permission_models import ToolCollectionPermission
        from sqlalchemy import select

        # THE OWNED KITS: the JOIN rows (the truth) ∪ the singular
        # slot (the back-compat read — a mid-run adoption sets the
        # slot; the boot sync converges it into the join later).
        kit_ids: set[str] = set()
        join_rows = await self.db.execute(
            select(AgentKit.kit_id).where(AgentKit.agent_id == int(agent_id))
        )
        kit_ids.update(r[0] for r in join_rows.all() if r[0])
        slot_row = await self.db.execute(
            select(Agent.kit_id).where(Agent.id == int(agent_id))
        )
        slot_id = slot_row.scalar_one_or_none()
        if slot_id:
            kit_ids.add(slot_id)
        if not kit_ids:
            return None

        # the kits' granted tools (tool_collection_permissions)
        perm_rows = await self.db.execute(
            select(ToolCollectionPermission.tool_id).where(
                ToolCollectionPermission.collection_id.in_(kit_ids)
            )
        )
        tool_ids = [r[0] for r in perm_rows.all()]
        if not tool_ids:
            # the agent OWNS kits but they grant nothing — the empty
            # surface (a deliberately tool-less shallow bot)
            return set()

        # THE IMPORT FIX (2026-08-24, the silent-fallback bug): the
        # Tool model lives in app.domain.tools.models — the wrong
        # import made this raise ImportError, the except in the caller
        # swallowed it, and a kit agent silently fell back to the
        # full GRAS default surface (23 tools). The kit policy was
        # being defeated by a bad import path.
        from app.domain.tools.models import Tool
        slug_rows = await self.db.execute(
            select(Tool.slug).where(Tool.id.in_(tool_ids))
        )
        return {r[0] for r in slug_rows.all() if r[0]}

    def _convert_tool_to_llm_format(self, tool) -> Dict[str, Any]:
        """
        Convert tool to LLM function calling format.

        Args:
            tool: Tool object or dict from database

        Returns:
            Dictionary in OpenAI function calling format
        """
        # Handle both dict and object cases
        if isinstance(tool, dict):
            # It's a dict
            slug = tool.get('slug')
            description = tool.get('description', '')
            parameters = tool.get("arguments_schema") or tool.get("config_schema", {})
            tool_id = tool.get('id')
            icon = tool.get('icon')
            color = tool.get('color')
            category_name = tool.get('category', {}).get('name') if tool.get('category') else None
        else:
            # It's an object (pydantic model or ORM object)
            slug = getattr(tool, 'slug', None)
            description = getattr(tool, 'description', '')
            parameters = getattr(tool, 'arguments_schema', None) or getattr(tool, 'config_schema', {})
            tool_id = getattr(tool, 'id', None)
            icon = getattr(tool, 'icon', None)
            color = getattr(tool, 'color', None)
            category = getattr(tool, 'category', None)
            category_name = getattr(category, 'name', None) if category else None

        return {
            "type": "function",
            "function": {
                "name": slug,
                "description": description,
                "parameters": parameters,
            },
            "x-cogitate-tool": {
                "id": tool_id,
                "icon": icon,
                "color": color,
                "category": category_name,
            },
        }

    def _resolve_config(
        self,
        agent_config: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Resolve tool configuration with precedence.
        
        Precedence: agent_config > schema defaults
        
        Args:
            agent_config: Agent-specific configuration
            schema: Tool configuration schema
            
        Returns:
            Resolved configuration dictionary
        """
        config = {}

        # Start with schema defaults
        if schema.get("properties"):
            for prop_name, prop_schema in schema["properties"].items():
                if "default" in prop_schema:
                    config[prop_name] = prop_schema["default"]

        # Override with agent-specific config
        config.update(agent_config)

        return config

    def _validate_arguments(
        self,
        arguments: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Optional[str]:
        """
        Validate arguments against JSON schema.
        
        Args:
            arguments: Arguments to validate
            schema: JSON Schema for validation
            
        Returns:
            Error message if validation fails, None if valid
        """
        # Defense-in-depth: reject reserved keys that could collide with
        # execute_tool() parameters (slug, config).  These should never
        # appear in LLM-supplied arguments; if they do, the LLM receives
        # a clear, actionable error rather than a cryptic TypeError.
        RESERVED_KEYS = {"slug", "config"}
        for key in RESERVED_KEYS:
            if key in arguments:
                return (
                    f"Reserved argument key '{key}' is not allowed in tool arguments. "
                    f"The key '{key}' conflicts with internal execution parameters. "
                    f"Please remove it from the tool call arguments."
                )

        required = schema.get("required", [])
        properties = schema.get("properties", {})

        # Check required fields
        for field_name in required:
            if field_name not in arguments:
                return f"Missing required field: {field_name}"

        # Check field types — unknown fields are silently allowed.
        # JSON Schema permits additional properties by default (additionalProperties
        # is only false when explicitly declared).  LLMs often send optional context
        # fields that are valid to ignore.
        for field_name, value in arguments.items():
            if field_name not in properties:
                continue  # allow undeclared fields unless schema explicitly forbids them

            field_type = properties[field_name].get("type")
            if field_type == "string" and not isinstance(value, str):
                return f"Field '{field_name}' must be a string"
            elif field_type == "integer" and not isinstance(value, int):
                return f"Field '{field_name}' must be an integer"
            elif field_type == "number" and not isinstance(value, (int, float)):
                return f"Field '{field_name}' must be a number"
            elif field_type == "boolean" and not isinstance(value, bool):
                return f"Field '{field_name}' must be a boolean"

        return None

    async def _execute_tool(
        self,
        tool_slug: str,
        arguments: Dict[str, Any],
        config: Dict[str, Any],
        tool_def: Any = None,
    ) -> Any:
        """
        Execute a tool — in-process (the registry) or declaratively (an endpoint).

        TWO KINDS, ONE CALL. A `builtin` tool has a handler registered in code and
        runs through the ``ToolRegistry``. A DECLARATIVE tool is described by its
        database row and runs by calling its ``endpoint`` — the logic lives outside
        this process (``app.domain.tools.declarative``). The row is the
        discriminator: every builtin carries ``type="builtin"``.

        THE TRUST RULE (design §6): installation is wiring, not authority. A
        declarative tool that declares a KEYED capability is REFUSED — a tool that
        arrives as a database row must not inherit the power of the reviewed,
        code-registered admin tools. Enforced here rather than documented, because
        a rule nobody executes is a comment.

        All built-in tools are registered at startup by ``init_default_registry()``.
        If ``tool_slug`` has no registered handler a ``KeyError`` or ``RuntimeError``
        is raised; the caller (``execute_tool_for_agent``) catches all exceptions and
        wraps them in a ``ToolExecutionResult(success=False, ...)``.

        Args:
            tool_slug: Tool identifier
            arguments: Tool arguments
            config: Resolved configuration

        Returns:
            Tool execution result (raw dict or structured response from handler)

        Raises:
            KeyError: If the slug is not registered in the ToolRegistry.
            RuntimeError: If the tool is registered but has no handler.
        """
        from app.domain.tools.capabilities import KEYED, tier_for
        from app.domain.tools.declarative import is_declarative, execute_declarative_tool

        tool_type = getattr(tool_def, "type", None) if tool_def is not None else None

        if is_declarative(tool_type):
            capability = getattr(tool_def, "capability", None)
            if tier_for(capability) == KEYED:
                logger.warning(
                    "🚫 Declarative tool '%s' declares the KEYED capability '%s' — "
                    "refused. Installation is wiring, not authority (design §6).",
                    tool_slug,
                    capability,
                )
                return {
                    "success": False,
                    "error": (
                        f"Declarative tool '{tool_slug}' declares a keyed capability "
                        f"('{capability}'). A tool that arrives as a database row may "
                        "not reach the keyed tier."
                    ),
                    "error_type": "declarative_keyed_refused",
                }
            return await execute_declarative_tool(
                tool=tool_def, arguments=arguments, config=config
            )

        return await self.tool_registry.execute_tool(
            tool_slug=tool_slug,
            tool_config=config,
            arguments=arguments,
        )


