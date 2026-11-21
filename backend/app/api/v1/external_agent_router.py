"""
External agent (Hermes/OpenClaw) — API for the agent side panel.

A thin bridge: the panel's WebSocket connects here; the router
drives the ACP subprocess via the AcpClient service and streams
agent_message_chunk / agent_thought_chunk events back. No agent
logic lives in this module — it's transport only.
"""

from __future__ import annotations

import asyncio
import time
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.domain.external_agent import (
    ExternalAgentConfig,
    ExternalAgentConfigUpdate,
    ExternalAgentInactive,
    ExternalAgentStatus,
    command_parts,
    get_acp_client,
    get_config,
    probe_runnable,
    save_config,
)

router = APIRouter(prefix="/external-agent", tags=["external-agent"])

# Two-stage halt grace (2026-08-13): after session/cancel, how long to
# wait for the agent's NATURAL stream end before escalating to the kill.
# Real ACP agents (Hermes) honor session/cancel within ~1s (the turn
# completes with an interrupted stop); a runaway that ignores it needs
# the escalation after this window.
FRESH_TURN_GRACE_SECONDS = 15
CANCEL_GRACE_SECONDS = 5.0
logger = logging.getLogger(__name__)


async def _db():
    from app.infrastructure.database import get_db_session
    async for session in get_db_session():
        yield session


async def _dialable_providers(db) -> str:
    """What this install can dial — the list a refusal offers.

    The row names it actually has, plus the registry's types for anything no row covers.
    """
    from sqlalchemy import select

    from app.domain.providers.provider_endpoints import PROVIDER_ENDPOINTS
    from app.infrastructure.database.models import Provider as ProviderRow

    names = list((await db.execute(select(ProviderRow.name))).scalars().all())
    return ", ".join(names + sorted(set(PROVIDER_ENDPOINTS) - set(names)))


@router.get("/config", response_model=ExternalAgentConfig)
async def get_external_agent_config(db=Depends(_db)):
    return await get_config(db)


@router.put("/config", response_model=ExternalAgentConfig)
async def update_external_agent_config(
    update: ExternalAgentConfigUpdate, db=Depends(_db)
):
    current = await get_config(db)
    # the 3-way permission tier (2026-08-21): the tier wins; the
    # DEPRECATED fix_mode bool maps only when the tier is absent
    # (backward compat with the pre-yolo persisted configs)
    if update.permission_tier is not None:
        tier = update.permission_tier
    elif update.fix_mode is not None:
        tier = "fix" if update.fix_mode else "chat"
    else:
        tier = current.permission_tier
    new = ExternalAgentConfig(
        # THE ACTIVATION (2026-11-18): carried like every other field — this
        # construction is EXPLICIT, so a field left out of it is validated and
        # then silently reset to its default by the next write.
        enabled=update.enabled if update.enabled is not None else current.enabled,
        command=update.command if update.command is not None else current.command,
        cwd=update.cwd if update.cwd is not None else current.cwd,
        permission_tier=tier,
        max_turn_seconds=(
            update.max_turn_seconds
            if update.max_turn_seconds is not None
            else current.max_turn_seconds
        ),
        # THE BUDGET FIELDS (2026-09-08 — the PUT-merge gap: they were
        # in the schema + the persisted-keys set but NOT in this
        # explicit construction, so every config write silently reset
        # them to the defaults. Caught live by the regime test.)
        max_tool_calls_per_turn=(
            update.max_tool_calls_per_turn
            if update.max_tool_calls_per_turn is not None
            else current.max_tool_calls_per_turn
        ),
        tool_call_checkin_every=(
            update.tool_call_checkin_every
            if update.tool_call_checkin_every is not None
            else current.tool_call_checkin_every
        ),
        image=update.image if update.image is not None else current.image,
        # THE BRAIN LIST (2026-10-10): carried over like every other field — this
        # construction is EXPLICIT, so a field left out of it is validated and then
        # silently reset to its default by the next write (the budget fields' own
        # 2026-09-08 incident).
        brains=update.brains if update.brains is not None else current.brains,
    )
    await save_config(db, new)
    # config changed → the running subprocess may need a fresh start;
    # close the current one so the next connection spawns with new config
    try:
        client = get_acp_client()
        if client.connected:
            await client.close()
    except Exception as e:
        logger.warning("external-agent: closing client after config change: %s", e)
    return new


@router.get("/skills/{name}")
async def external_agent_skill(name: str):
    """Return a Cogitate skill's SKILL.md body (consult-tool-injected
    delivery: WE read the skill and include it in the prompt — the
    external agent's own skill loader does not see repo skills)."""
    from app.domain.tools.builtin.consult_handler import _load_skill
    body = _load_skill(name)
    if not body:
        raise HTTPException(404, f"skill not found: {name}")
    return {"name": name, "body": body}


@router.get("/status", response_model=ExternalAgentStatus)
async def external_agent_status(db=Depends(_db)):
    cfg = await get_config(db)
    # the status call is also where the live singleton learns the decision —
    # a surface that reads state syncs the gate as a side effect of reading
    client = get_acp_client(enabled=cfg.enabled)
    # Phase D: the badge reads the GRANT state (the flag is a view
    # over the session grants — the first-class object)
    from app.domain.external_agent.services import get_fix_grant_state
    fix_mode = await get_fix_grant_state(db) or cfg.fix_mode
    m = _read_exa_model_config()
    blocked = probe_runnable(cfg)
    return ExternalAgentStatus(
        connected=client.connected,
        enabled=cfg.enabled,
        runnable=blocked is None,
        blocked_reason=blocked,
        session_id=client.session_id,
        command=cfg.command,
        cwd=cfg.cwd,
        permission_tier=cfg.permission_tier,
        model=m.get("model"),
        provider=m.get("provider"),
        error=None,
    )


@router.post("/activate")
async def activate_external_agent(db=Depends(_db)) -> dict:
    """THE USER'S DECISION (2026-11-18): turn Exa on.

    Enabling is allowed even when nothing here can run it — activation is the
    user's call, not a capability test — but the answer CARRIES the probe, so
    the page can say "'hermes' is not on PATH" instead of showing a switch that
    does nothing. `runnable: false` is a fact to report, not a refusal.

    THE HOME IS PROVISIONED FIRST (2026-11-20): the switch used to flip and
    spawn against whatever already sat in Exa's home, and on a fresh install
    that was one skill and no model section — measured: the agent answered as
    plain Hermes. `activation.apply` is the sequence's ONE implementation (the
    CLI and the docs read the same one), it provisions IDEMPOTENTLY (an edited
    skill or an existing config is kept), and it takes the decision LAST — so a
    home that could not be provisioned is never left switched on.
    """
    from app.domain.external_agent import activation

    try:
        report, provisioned = await activation.apply(db)
    except Exception as e:
        logger.error("external-agent: provisioning Exa's home failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Exa's home could not be provisioned ({e}) — it was not activated.",
        ) from e
    current = _read_exa_model_config()
    blocked = probe_runnable(await get_config(db))
    return {
        "enabled": True,
        "runnable": blocked is None,
        "blocked_reason": blocked,
        # WHAT IT SEEDED, line by line — the page says what activation did
        # instead of promising a brain that still has no model.
        "provisioned": provisioned,
        # THE MODEL IS THE ONE THING ACTIVATION CANNOT DECIDE (2026-11-20): a home with
        # no model answers as plain Hermes, so the answer says whether it has one and
        # hands over THIS INSTALL'S chat model as an offer. Accepting it is the page's
        # one press — nothing is written here on the user's behalf.
        "model": current.get("model"),
        "provider": current.get("provider"),
        "needs_model": not current.get("model"),
        "offer": report.offer.to_dict() if report.offer is not None else None,
    }


@router.post("/deactivate")
async def deactivate_external_agent(db=Depends(_db)) -> dict:
    """Turn Exa off and END any live session — a switched-off agent must not
    keep a subprocess (or a conversation) running behind the switch."""
    cfg = await get_config(db)
    deactivated = cfg.model_copy(update={"enabled": False})
    await save_config(db, deactivated)
    client = get_acp_client(enabled=False)
    if client.connected:
        try:
            await client.close()
        except Exception as e:
            logger.warning("external-agent: close after deactivation: %s", e)
    blocked = probe_runnable(deactivated)
    return {
        "enabled": False,
        "runnable": blocked is None,
        "blocked_reason": blocked,
    }


# THE EXA MODEL CARD (2026-08-22, user): the model/provider live in
# Exa's OWN config file (.hermes/config.yaml — the Phase-1 isolated
# home, the single source of truth). The API is a VIEW/EDITOR of that
# file (no DB migration): GET reads the model section, PUT writes it
# + closes the client so the next spawn uses the new brain.
# THE VISION MODEL (2026-08-22, user): the screenshot-analysis model —
# Hermes routes browser_vision to AUXILIARY_VISION_MODEL. It lives in
# Exa's .env (a separate store from config.yaml's model section).
def _read_exa_vision_env() -> str:
    """Read AUXILIARY_VISION_MODEL from Exa's .env ('' if unset)."""
    try:
        from app.core.config import Paths
        env_path = Paths.exa_home / ".env"
        if not env_path.exists():
            return ""
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("AUXILIARY_VISION_MODEL="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception as e:
        logger.warning("external-agent: reading the vision env failed: %s", e)
    return ""


def _write_exa_vision_env(value: str) -> None:
    """Set AUXILIARY_VISION_MODEL in Exa's .env (file-backed)."""
    try:
        from app.core.config import Paths
        env_path = Paths.exa_home / ".env"
        # THE BARE-NAME FIX (2026-08-22, user): browser_vision reads THIS
        # env var and passes it straight to the provider. deepseek's API
        # rejects the 'deepseek/' prefix ('you passed deepseek/deepseek-
        # ...'), so store the BARE name for deepseek ids — same rule as
        # the config.yaml auxiliary block.
        env_value = value[len("deepseek/"):] if value.startswith("deepseek/") else value
        lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
        out = []
        found = False
        for line in lines:
            if line.strip().startswith("AUXILIARY_VISION_MODEL="):
                out.append(f"AUXILIARY_VISION_MODEL={env_value}" if env_value else "# AUXILIARY_VISION_MODEL=")
                found = True
            else:
                out.append(line)
        if not found and env_value:
            out.append(f"AUXILIARY_VISION_MODEL={env_value}")
        env_path.write_text("\n".join(out) + "\n", encoding="utf-8")
        # THE TWO-STORE FIX (2026-08-22, user): browser_vision resolves
        # the vision brain from config.yaml's auxiliary.vision block, NOT
        # the .env var. The UI dropdown updated only .env — config.yaml
        # kept the old brain, so the selection never activated. Update
        # BOTH stores here (provider: openrouter for the catalog ids).
        import yaml as _yaml  # type: ignore[import-untyped]
        cfg_path = Paths.exa_home / "config.yaml"
        cfg: dict = {}
        if cfg_path.exists():
            with open(cfg_path, encoding="utf-8") as _f:
                cfg = _yaml.safe_load(_f) or {}
        cfg.setdefault("auxiliary", {})
        if value:
            # THE NATIVE-PROVIDER ROUTE (2026-08-22, user): the first
            # version hardcoded openrouter — but deepseek-vision via
            # OpenRouter 404'd ('No endpoints available matching your
            # guardrail restrictions'). Route each vision model through
            # its NATIVE provider: deepseek ids -> api.deepseek.com,
            # everything else (the openrouter catalog) -> openrouter.
            native_provider = "deepseek" if value.startswith("deepseek/") else "openrouter"
            native_base = {
                "deepseek": "https://api.deepseek.com",
                "openrouter": "https://openrouter.ai/api/v1",
            }[native_provider]
            native_key = "DEEPSEEK_API_KEY" if native_provider == "deepseek" else "OPENROUTER_API_KEY"
            # deepseek's API wants the BARE model name (it rejects
            # 'deepseek/deepseek-...' — verified 2026-08-22); OpenRouter
            # wants the full catalog id. Strip only for deepseek.
            aux_model = value[len("deepseek/"):] if native_provider == "deepseek" else value
            cfg["auxiliary"]["vision"] = {
                "provider": native_provider,
                "model": aux_model,
                "base_url": native_base,
                "key_env": native_key,
            }
        else:
            cfg["auxiliary"].pop("vision", None)
        with open(cfg_path, "w", encoding="utf-8") as _f:
            _yaml.safe_dump(cfg, _f, sort_keys=False, allow_unicode=True)
    except Exception as e:
        logger.warning("external-agent: writing the vision env failed: %s", e)


def _read_exa_model_config() -> dict:
    """Read Exa's model + reasoning sections from its private config file.

    The model section has ONE reader and ONE writer, both in
    `domain/external_agent/activation.py` — the activation path needs the same
    view. This wrapper adds the vision model, which lives in the .env store
    rather than config.yaml.
    """
    from app.domain.external_agent import activation
    m = activation.read_model_config()
    m["vision_model"] = _read_exa_vision_env()
    return m


def _write_exa_model_config(
    model: str,
    provider: str,
    base_url: str | None = None,
    reasoning_effort: str | None = None,
    clear_base_url: bool = False,
) -> None:
    """Set Exa's model section — delegated to the domain's one writer."""
    from app.domain.external_agent import activation
    activation.write_model_config(
        model,
        provider,
        base_url=base_url,
        reasoning_effort=reasoning_effort,
        clear_base_url=clear_base_url,
    )


@router.get("/model")
async def external_agent_model(db=Depends(_db)):
    """Exa's model/provider (from its private config) PLUS this install's offer.

    The offer is what makes one configuration do the work twice: a stranger has already
    chosen a chat model by the time they reach the Exa page, so the card can prefill it and
    ask for one accept instead of a second decision. Nothing here writes it.
    """
    from app.domain.external_agent import activation

    model_config = _read_exa_model_config()
    offer = await activation.chat_offer(db)
    model_config["offer"] = offer.to_dict() if offer is not None else None
    return model_config


@router.put("/model")
async def update_external_agent_model(body: dict, db=Depends(_db)):
    """Set Exa's model/provider/reasoning-effort (writes the private
    config + closes the client so the next spawn uses the new brain)."""
    model = (body.get("model") or "").strip()
    provider = (body.get("provider") or "").strip()
    # THE 4xx CONTRACT (2026-10-12): these rejections used to answer
    # 200 {"error": ...} — and the model card's only caller never reads that
    # field, so it toasted SUCCESS over a save that wrote nothing. A refusal has
    # to be a real failure for the caller.
    if not model or not provider:
        raise HTTPException(status_code=400, detail="model and provider are required.")
    base_url = (body.get("base_url") or "").strip() or None
    effort = (body.get("reasoning_effort") or "").strip() or None
    if effort not in (None, "none", "low", "medium", "high", "max"):
        raise HTTPException(status_code=400, detail=f"invalid reasoning_effort: {effort}")
    vision_model = (body.get("vision_model") or "").strip()

    # THE ACCEPTANCE RULE (2026-10-12, the user's option A — the page:
    # wiki/issues/resolved/embedded-service-literals/exa-model-save-undialable-provider.md). THE BASE-URL GUARD
    # (2026-08-22) still stands — the config can never pair a model with the wrong
    # pipe — but it used to decide the address from a three-entry literal map, so
    # every other provider kept the PREVIOUS one's address, and a name nothing
    # could dial was written and reported as a success. Now the registry's rule
    # decides (address_for_client: explicit → the type's canonical → the row's own
    # → clear when the client knows it → REFUSE).
    clear_base_url = False
    if not base_url:
        from sqlalchemy import select

        from app.domain.providers.provider_endpoints import address_for_client, client_can_dial
        from app.infrastructure.database.models import Provider as ProviderRow

        row = (
            await db.execute(select(ProviderRow).where(ProviderRow.name == provider))
        ).scalar_one_or_none()
        decision = address_for_client(
            provider,
            row_type=row.provider_type if row else None,
            row_base_url=row.base_url if row else None,
            client_knows=client_can_dial(provider),
        )
        if decision.refusal:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{decision.refusal}. Dialable here: {await _dialable_providers(db)}. "
                    f"Pass an explicit base_url to set the address yourself."
                ),
            )
        if decision.note:
            logger.info("external-agent: %s", decision.note)
        base_url = decision.base_url
        clear_base_url = decision.clear
    _write_exa_model_config(model, provider, base_url, effort, clear_base_url=clear_base_url)
    _write_exa_vision_env(vision_model)
    try:
        client = get_acp_client()
        if client.connected:
            await client.close()
    except Exception as e:
        logger.warning("external-agent: closing client after model change: %s", e)
    return {
        "status": "updated",
        "model": model,
        "provider": provider,
        "reasoning_effort": effort,
        "vision_model": vision_model,
    }


@router.post("/fix-mode")
async def set_fix_mode(body: dict, db=Depends(_db)):
    """The YOLO button (Phase D, study 14): immediate, deliberate,
    session-scoped fix-mode grant.

    One click flips the config flag (the view) AND syncs the grant
    rows (the record) — no Save round-trip. Returns the new state
    for the badge. The ACP strictTools gate is the enforcement;
    the rows are the inspectable mirror.
    """
    on = bool(body.get("on", False))
    tier = body.get("permission_tier")
    if tier not in ("chat", "fix", "yolo"):
        tier = "fix" if on else "chat"
    cfg = await get_config(db)
    new = ExternalAgentConfig(
        command=cfg.command, cwd=cfg.cwd,
        permission_tier=tier, max_turn_seconds=cfg.max_turn_seconds,
    )
    await save_config(db, new)
    # config changed → the running subprocess may need a fresh
    # start; close the current one so the next spawn honors the gate
    try:
        client = get_acp_client()
        if client.connected:
            await client.close()
            logger.info("External agent closed after fix-mode change")
    except Exception:
        pass
    from app.domain.external_agent.services import get_fix_grant_state
    return {"fix_mode": on, "granted": await get_fix_grant_state(db)}


@router.post("/restart")
async def restart_external_agent(db=Depends(_db)):
    """Close the current subprocess; next connection spawns fresh."""
    cfg = await get_config(db)
    client = get_acp_client()
    if client.connected:
        try:
            await client.close()
        except Exception as e:
            raise HTTPException(500, f"close failed: {e}")
    return {"status": "restarted", "command": cfg.command, "cwd": cfg.cwd}


@router.post("/report")
async def save_exa_report(payload: dict):
    """Persist an Exa conversation report into the product flow.

    Option B (2026-08-13): Exa reports now PERSIST instead of living
    only in the ephemeral panel chat. The report is wrapped in the
    same ``WorkflowProduct`` and delivered through the standard
    distributors (file + display + toast) — so it appears on the
    Workflow Products page with the existing report-viewer modal,
    survives page reloads, and is cleared by the same Clear action.

    Body: ``{title, body}`` — title is a short human label, body is
    the markdown report (typically the panel's last assistant reply).
    """
    from datetime import datetime, timezone
    from app.workflows.distribution.models import WorkflowProduct
    from app.workflows.distribution import deliver_product

    title = str(payload.get("title") or "Exa Report").strip()
    body = str(payload.get("body") or "").strip()
    if not body:
        raise HTTPException(400, "report body required")

    product = WorkflowProduct(
        product_type="exa_report",
        title=title,
        body=body,
        source_template="exa-panel",  # not a workflow template — panel origin
        created_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        meta={"origin": "exa-panel"},
    )
    results = deliver_product(product)
    return {
        "product": {
            "product_type": product.product_type,
            "title": product.title,
            "created_at": product.created_at,
            "path": product.path,
        },
        "delivery": [r.as_dict() for r in results],
    }


# THE EXA-TIMER (2026-08-28): the one-shot timers so Exa can launch
# a long process, finish the turn, and pick up when the timer fires.
# The expiry publishes the timer:{id}:fired bus-event (the panel
# surfaces the CONFIRMABLE pickup — NO auto-fire, the 08-13 doctrine).
@router.post("/timer")
async def set_exa_timer(payload: dict) -> dict:
    """Set a one-shot timer: {duration_seconds, context}."""
    from app.domain.external_agent.timer_service import set_timer

    duration = int(payload.get("duration_seconds") or 0)
    context = str(payload.get("context") or "")
    if duration <= 0:
        return {"error": "duration_seconds must be positive"}
    result = await set_timer(duration, context)
    result["ok"] = True
    return result


@router.get("/timers")
async def list_exa_timers() -> dict:
    """The in-flight timers (the debug/panel)."""
    from app.domain.external_agent.timer_service import list_timers

    return {"timers": await list_timers()}


@router.delete("/timer/{timer_id}")
async def cancel_exa_timer(timer_id: str) -> dict:
    """Cancel a pending timer."""
    from app.domain.external_agent.timer_service import cancel_timer

    return {"ok": await cancel_timer(timer_id), "timer_id": timer_id}


@router.websocket("/ws")
async def external_agent_ws(websocket: WebSocket) -> None:
    """One WebSocket per panel open.

    Client -> server:
      {"type": "prompt", "text": "..."}
      {"type": "cancel"}                          -- STOP (gentle: session/cancel, then kill)
      {"type": "nuke"}                            -- FORCE-KILL (process-group SIGKILL, no grace)
    Server -> client:
      {"type": "status", "status": "connecting" | "ready" | "error" | "cancelled", ...}
      {"type": "message", "text": "<chunk>"}
      {"type": "thought", "text": "<chunk>"}
      {"type": "done", "reply": "<full text>"}

    HALT PATH (2026-08-13 incident): an ACP prompt runs to completion —
    there is no protocol-level cancel. The only reliable stop is killing
    the subprocess, which AcpClient.close() does by PID (terminate, 3s
    grace, kill). "cancel" works both while idle (subprocess closed) and
    mid-prompt (subprocess killed; the running turn dies with it). After
    a cancel the next prompt respawns the agent fresh.
    """
    await websocket.accept()
    # THE CONFIG IS LOADED BEFORE ANYTHING SPAWNS, and a config we cannot read
    # counts as INACTIVE rather than "spawn it anyway" (2026-11-18). The gate
    # fails closed on purpose: guessing here means an agent the user never
    # activated, running with its tools.
    fix_granted = False
    exa_model = None
    cfg = None
    try:
        async for session in _db():
            cfg = await get_config(session)
            break
    except Exception as e:
        logger.warning(
            "external-agent: config unavailable (%s) — treating Exa as inactive", e
        )

    # THE GATE (2026-11-18, the user's ruling): a de-activated Exa answers with
    # its STATE, not with a failed spawn. Sent as a status event the panel
    # already knows how to render — "not active" is not an error.
    if cfg is None or not cfg.enabled:
        await websocket.send_json({
            "type": "status",
            "status": "inactive",
            "message": "Exa is not active.",
        })
        await websocket.close()
        return

    fix_granted = cfg.permission_tier in ("fix", "yolo")
    # THE EXA BUBBLE INSTRUMENTATION (2026-08-22): the model name for
    # the done event — read from Exa's own config file (the Phase-1
    # isolated home) so the bubble shows the ACTUAL brain, even
    # after a config swap.
    try:
        import yaml as _yaml
        from app.core.config import Paths
        with open(Paths.exa_home / "config.yaml", encoding="utf-8") as _f:
            _cfg = _yaml.safe_load(_f) or {}
        exa_model = (_cfg.get("model") or {}).get("default")
    except Exception:
        exa_model = None
    # Whole-turn duration cap (2026-08-14): 0 = unlimited. Any
    # positive value auto-halts a turn that exceeds it via the
    # same two-stage path as Stop, reporting 'time_limit'.
    max_turn_seconds = int(getattr(cfg, "max_turn_seconds", 0) or 0)
    # THE TOOL-CALL BUDGET (2026-09-08, ruled): the
    # per-turn tool-call cap + the check-in cadence (0 = off).
    max_tool_calls_per_turn = int(getattr(cfg, "max_tool_calls_per_turn", 0) or 0)
    tool_call_checkin_every = int(getattr(cfg, "tool_call_checkin_every", 0) or 0)
    client = get_acp_client(
        command=command_parts(cfg.command),
        cwd=cfg.cwd or None,
        permission_tier=cfg.permission_tier,
        enabled=cfg.enabled,
    )
    try:
        # ensure the subprocess + session exist
        if not client.connected:
            await websocket.send_json({"type": "status", "status": "connecting"})
            try:
                await client.start()
            except ExternalAgentInactive as e:
                # the decision can flip while the panel is open — say "not
                # active", never "error"
                await websocket.send_json({"type": "status", "status": "inactive", "message": str(e)})
                await websocket.close()
                return
            except Exception as e:
                await websocket.send_json({"type": "status", "status": "error", "message": str(e)})
                await websocket.close()
                return
        await websocket.send_json({"type": "status", "status": "ready", "sessionId": client.session_id})

        # One receiver task owns websocket.receive_text() so the handler
        # can stream a prompt AND still see a "cancel" arriving mid-turn.
        cancel_event = asyncio.Event()
        stream_ended = asyncio.Event()
        # set when the stream dies with an exception AFTER a cancel —
        # the subprocess is suspect and must be killed, not reused
        stream_crashed = False
        streaming = False
        # ONE 'cancelled' status per stop — shared by the stream loop,
        # _halt_agent, and _nuke_agent (the double '⏹ Stopped.' in
        # Exa_dialog_02 was two senders, 2026-08-13)
        cancelled_reported = False
        incoming: asyncio.Queue = asyncio.Queue()
        # THE PROMPT QUEUE (2026-08-30, the user's every-other finding):
        # a prompt arriving while a stream runs used to start a SECOND
        # concurrent stream_prompt — two interleaved ACP streams to the
        # same agent cross-wire the conversation state (the alternating
        # responses). The overlap now QUEUES the prompt; the stream's
        # end drains it as the next sequential turn.
        pending_prompts: list[tuple[str, dict]] = []

        async def _halt_agent() -> None:
            """Two-stage stop (2026-08-13, incident exa-runaway).

            STAGE 1: session/cancel — the ACP-standard gentle interrupt
            (acp/meta.py: AGENT_METHODS['session_cancel']). Any ACP
            agent (Hermes, OpenClaw, ...) implements it; Hermes maps it
            to agent.interrupt() — the same mechanism Ctrl+C uses in the
            CLI. The turn stops, the session stays alive, the next
            prompt continues normally.

            STAGE 2 (escalation): if the agent ignores the interrupt
            (stuck in a tool loop) and the stream doesn't end within the
            grace window, close() kills the subprocess — the only
            reliable halt. The next prompt respawns fresh.
            """
            if not client.connected:
                return
            if not streaming:
                # idle stop — nothing to interrupt; close immediately
                await client.close()
                await _report_cancelled()
                return
            await client.cancel()
            try:
                await asyncio.wait_for(stream_ended.wait(), timeout=CANCEL_GRACE_SECONDS)
                # stream ended (gentle interrupt worked) — the stream loop
                # already reported 'cancelled'
                if stream_crashed:
                    # THE CRASH-ON-CANCEL (2026-08-21): the stream ended
                    # with an exception, not a clean interrupt — the ACP
                    # supervisor's task loop died (RequestError: Internal
                    # error racing the cancel) and the subprocess is
                    # broken-but-alive. Kill it so the next prompt
                    # respawns fresh instead of reusing the frozen client.
                    logger.warning("external-agent: cancel raced a crashing turn — closing the broken subprocess")
                    await client.close()
                return
            except asyncio.TimeoutError:
                await client.close()
            # NOTE (2026-08-14): _report_cancelled() sends the
            # 'cancelled' status exactly once (dedup flag) — the old
            # UNCONDITIONAL send after it fired a SECOND 'cancelled'
            # after a time-limit auto-halt (the panel showed both
            # '⏱ Time limit reached' and '⏹ Stopped.'). Removed: the
            # status is already delivered by _report_cancelled or the
            # stream loop.
            await _report_cancelled()

        async def _nuke_agent() -> None:
            """Force-kill: process-group SIGKILL, immediate, no grace.

            Targeted by ownership (start_new_session spawn tag) — can
            never touch the backend / VS Code / CLI. Sets the
            cancel_event first so the stream loop suppresses the
            expected EOF error (killed pipe) and exits cleanly; the
            next prompt respawns fresh.
            """
            if client.connected:
                await client.nuke()
            await _report_cancelled()

        async def _report_cancelled() -> None:
            """Send the 'cancelled' status at most once per stop."""
            nonlocal cancelled_reported
            if cancelled_reported:
                return
            cancelled_reported = True
            try:
                await websocket.send_json({"type": "status", "status": "cancelled"})
            except Exception:
                pass

        async def _receiver() -> None:
            try:
                while True:
                    raw = await websocket.receive_text()
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        await incoming.put(("error", None))
                        continue
                    kind = data.get("type")
                    if kind == "cancel":
                        # THE STOP LOG (2026-08-22, user): pressing the
                        # Stop button must leave an UNAMBIGUOUS record —
                        # an interrupted turn was previously recorded as
                        # '*(Exa returned nothing)*' (silent ambiguity).
                        # The WS cancel is the user's Stop button: log it
                        # loudly BEFORE halting.
                        logger.info(
                            "external-agent: STOP pressed by the user (WS cancel) — "
                            "halting the turn mid-%s; the record will say "
                            "'stopped by user', not 'returned nothing'",
                            "stream" if streaming else "idle",
                        )
                        # set the event IMMEDIATELY (not just queue it) —
                        # the main loop is blocked in `async for
                        # stream_prompt` while streaming, so a queued
                        # cancel wouldn't be seen until the turn ends.
                        cancel_event.set()
                        # schedule the halt as its OWN task: the receiver
                        # is the only actor alive mid-stream, and if the
                        # agent is stuck in a long tool call NO events
                        # flow, so the stream loop never gets a chance to
                        # check the event — the halt task escalates by
                        # wall-clock grace instead.
                        asyncio.create_task(_halt_agent())
                        continue
                    elif kind == "nuke":
                        # NUKE: same pattern but immediate — no
                        # session/cancel, no grace. The task sets the
                        # cancel_event (so the stream loop suppresses the
                        # expected EOF error and exits cleanly) then
                        # SIGKILLs the whole process group.
                        cancel_event.set()
                        asyncio.create_task(_nuke_agent())
                        continue
                    await incoming.put((kind, data))
            except Exception:
                pass  # WS closed
            finally:
                # sentinel so the main loop can't hang on a dead socket
                await incoming.put(("_closed", None))

        recv_task = asyncio.create_task(_receiver())
        try:
            while True:
                # THE DRAIN (2026-08-30): a queued prompt becomes the
                # next turn the moment the in-flight stream's ended.
                if pending_prompts and not streaming:
                    kind, data = pending_prompts.pop(0)
                else:
                    kind, data = await incoming.get()
                if kind == "_stream_ended":
                    continue  # the top-of-loop drain picks up the queue
                if kind == "_closed":
                    break  # panel went away
                if kind == "cancel":
                    # IDLE cancel (main loop only runs here when NOT
                    # streaming — mid-stream cancels are handled by the
                    # receiver's _halt_agent + the stream loop's event
                    # check). Nothing is running: close the subprocess.
                    if client.connected and not streaming:
                        await client.close()
                    await websocket.send_json({"type": "status", "status": "cancelled"})
                    continue
                if kind == "nuke":
                    # NUKE (2026-08-13): force-kill the agent and its
                    # whole process tree — process-group SIGKILL, no
                    # session/cancel, no grace. For when the gentle halt
                    # failed. Targeted by process group (spawn tag), so
                    # it can never touch the backend / VS Code / CLI.
                    if client.connected:
                        await client.nuke()
                    await websocket.send_json({"type": "status", "status": "cancelled"})
                    continue
                if kind == "error":
                    await websocket.send_json({"type": "status", "status": "error", "message": "bad json"})
                    continue
                if kind == "approval_response":
                    # CHAT AUTHORIZATION (2026-08-21): the user's
                    # decision on a pending permission request. The
                    # response carries the request id + the chosen
                    # option; resolve_permission answers the ACP
                    # requester (the adapter's future). Unknown ids
                    # are dropped — the security property.
                    ok = await client.resolve_permission(
                        str(data.get("request_id", "")),
                        str(data.get("option_id", "deny")),
                    )
                    await websocket.send_json({
                        "type": "approval_result",
                        "request_id": data.get("request_id", ""),
                        "resolved": ok,
                    })
                    continue
                if kind != "prompt" or not data.get("text"):
                    await websocket.send_json({"type": "status", "status": "error", "message": "prompt with text required"})
                    continue

                # THE BUSY-GUARD (2026-08-30): a prompt DURING the
                # stream would start a concurrent stream_prompt (the
                # every-other corruption) — queue it; the stream's
                # finally drains it as the next turn.
                if streaming:
                    pending_prompts.append((kind, data))
                    continue

                # a prior cancel closed the subprocess — respawn before use
                if not client.connected:
                    await websocket.send_json({"type": "status", "status": "connecting"})
                    try:
                        await client.start()
                    except ExternalAgentInactive as e:
                        await websocket.send_json({"type": "status", "status": "inactive", "message": str(e)})
                        continue
                    except Exception as e:
                        await websocket.send_json({"type": "status", "status": "error", "message": str(e)})
                        continue
                    await websocket.send_json({"type": "status", "status": "ready", "sessionId": client.session_id})

                parts: list[str] = []
                # SERVER-SIDE MODE DIRECTIVE (fix-mode grant, 2026-08-12):
                # the grant lives in the persisted config; the directive is
                # injected here so the client can't spoof it. Defense in
                # depth with the strictTools spawn gate + the watchable
                # tool stream.
                # THE THREE MODE DIRECTIVES (2026-08-21): chat (the
                # card), fix (cwd-scoped auto-approve), yolo (everything).
                # Yolo's runaway risk is bounded by the chat Stop (the
                # break button — the user can halt instantly).
                tier = getattr(cfg, "permission_tier", "chat")
                if tier == "yolo":
                    mode_directive = (
                        "\n\n[MODE: YOLO — the user granted UNRESTRICTED write "
                        "access for this session. You MAY write files, apply "
                        "patches, and run modifying commands anywhere — no "
                        "per-edit approval. The secret-file guard still "
                        "protects .env/.ssh/.git (those still prompt). The "
                        "user can STOP you at any moment (the break button) "
                        "— so work in tight, verifiable steps, report every "
                        "change, verify your fixes, and NEVER hide a "
                        "mistake. Unrestricted is not unsupervised: every "
                        "action is still recorded and audited.]"
                    )
                elif fix_granted:
                    mode_directive = (
                        "\n\n[MODE: FIX GRANTED — the user has explicitly enabled "
                        "fix mode for this session. You MAY write files, apply "
                        "patches, and run modifying commands (restarts, tests) to "
                        "resolve the issue. Keep the user informed of every "
                        "change; verify your fixes; report what you changed.]"
                    )
                else:
                    mode_directive = (
                        "\n\n[MODE: CHAT AUTHORIZATION — you MAY write files, "
                        "apply patches, and run modifying commands, but EVERY "
                        "edit is presented to the user for approval (an "
                        "Allow edit / Deny card with the diff appears in the "
                        "chat). Propose your edits normally; the system "
                        "intercepts them and waits for the user's decision. "
                        "Do NOT bypass the approval gate (no terminal "
                        "workarounds); a denied edit stays denied. The "
                        "user decides granularly — that granularity is the "
                        "feature.]"
                    )
                cancel_event.clear()
                streaming = True
                stream_ended.clear()
                turn_started = time.monotonic()
                time_limit_hit = False

                # THE STREAM RUNS AS A TASK (2026-08-21): while it
                # consumes the ACP events, the main loop below keeps
                # processing INCOMING messages — critically the
                # approval_response (chat authorization). Before this
                # change the async-for blocked the main loop, so a
                # permission request deadlocked: the card appeared,
                # the user's Allow response queued behind the stream,
                # and the adapter timed out (60s) -> denied.
                async def _stream_run(prompt_data: dict = data) -> None:
                    nonlocal streaming, time_limit_hit, stream_crashed
                    tool_calls_this_turn = 0
                    last_checkin_count = 0
                    try:
                        async for ev in client.stream_prompt(prompt_data["text"] + mode_directive):
                            # WHOLE-TURN CAP (2026-08-14): if the turn has run
                            # longer than max_turn_seconds, halt it via the
                            # same two-stage path as Stop (gentle cancel →
                            # grace → kill) and report 'time_limit'. 0 =
                            # unlimited. Checked per-event so a busy agent
                            # (thoughts/tool_calls) can't evade it.
                            if (
                                max_turn_seconds > 0
                                and not cancel_event.is_set()
                                and time.monotonic() - turn_started >= max_turn_seconds
                            ):
                                # THE TIMEOUT LOG (2026-08-22, user): any
                                # Exa timeout is a clear error condition —
                                # ERROR level + the model + session + the
                                # elapsed so the record says WHY (the
                                # user's ask: don't leave the user hanging
                                # without a clue).
                                logger.error(
                                    "EXA TIMEOUT: turn exceeded the %ss whole-turn cap — "
                                    "halting (model=%s session=%s elapsed=%.1fs)",
                                    max_turn_seconds,
                                    exa_model,  # the outer WS handler's local (closure)
                                    client.session_id,
                                    time.monotonic() - turn_started,
                                )
                                time_limit_hit = True
                                cancel_event.set()
                                # report the reason FIRST (and set the dedup
                                # flag) so the halt's own 'cancelled' report
                                # is suppressed — the panel must see WHY
                                try:
                                    await websocket.send_json({
                                        "type": "status",
                                        "status": "time_limit",
                                        "message": f"Reached the {max_turn_seconds}s "
                                        "time limit — the run was stopped. You can "
                                        "re-ask with more detail, or raise the limit "
                                        "on the Exa Agent page.",
                                    })
                                    cancelled_reported = True
                                except Exception:
                                    pass
                                asyncio.create_task(_halt_agent())
                            # THE TOOL-CALL BUDGET (2026-09-08,
                            # the layer-3 teeth): the runaway-turn class
                            # (silent 50+-call turns crash + hang). Count the
                            # tool calls per turn; at the check-in cadence
                            # send a 'working' beacon (the user SEES the
                            # runaway building); at the hard cap halt via the
                            # same two-stage path as Stop + report
                            # 'tool_call_limit' (0 = off).
                            if ev.kind == "tool_call":
                                tool_calls_this_turn += 1
                                calls = tool_calls_this_turn
                                if (
                                    max_tool_calls_per_turn > 0
                                    and not cancel_event.is_set()
                                    and calls >= max_tool_calls_per_turn
                                ):
                                    logger.warning(
                                        "EXA TOOL-CALL LIMIT: turn reached %s tool calls — "
                                        "halting (model=%s session=%s)",
                                        calls,
                                        exa_model,
                                        client.session_id,
                                    )
                                    cancel_event.set()
                                    try:
                                        await websocket.send_json({
                                            "type": "status",
                                            "status": "tool_call_limit",
                                            "message": (
                                                f"Reached the {max_tool_calls_per_turn} tool-call limit — "
                                                "the run was stopped. You can re-ask with more "
                                                "detail, or raise the limit on the Exa Agent page."
                                            ),
                                        })
                                        cancelled_reported = True
                                    except Exception:
                                        pass
                                    asyncio.create_task(_halt_agent())
                                elif (
                                    tool_call_checkin_every > 0
                                    and not cancel_event.is_set()
                                    and calls - last_checkin_count >= tool_call_checkin_every
                                ):
                                    last_checkin_count = calls
                                    try:
                                        await websocket.send_json({
                                            "type": "status",
                                            "status": "working",
                                            "message": (
                                                f"{calls} tool calls so far — still working. "
                                                "Say stop if you want to halt."
                                            ),
                                        })
                                    except Exception:
                                        pass
                            if cancel_event.is_set():
                                # user hit stop — _halt_agent (receiver side)
                                # sends session/cancel then escalates to the
                                # kill if the agent keeps running. We do NOT
                                # break here: the grace must measure the
                                # agent's NATURAL end (usage/completion). If
                                # we broke on our own, stream_ended would
                                # fire and _halt_agent would wrongly conclude
                                # the gentle interrupt worked. Keep consuming;
                                # if the agent honors the interrupt the stream
                                # ends on its own, and if it doesn't,
                                # _halt_agent's wall-clock grace kills the
                                # subprocess (which ends this stream via EOF).
                                await _report_cancelled()
                            if ev.kind == "closed":
                                # sentinel from a nuke/close kill — the
                                # subprocess is gone; exit the stream cleanly
                                break
                            if ev.kind == "message":
                                parts.append(ev.text)
                                await websocket.send_json({"type": "message", "text": ev.text})
                            elif ev.kind == "thought":
                                await websocket.send_json({"type": "thought", "text": ev.text})
                            elif ev.kind == "tool_call":
                                # forward the raw tool_call update so the panel can
                                # show what the consultant is doing (watchable
                                # keyboard-takeover workspace)
                                await websocket.send_json({"type": "tool_call", "update": json.loads(ev.text)})
                            elif ev.kind == "approval":
                                # CHAT AUTHORIZATION (2026-08-21): forward
                                # the permission request (the diff + the
                                # options) — the chat renders the
                                # Approve/Deny card
                                await websocket.send_json({
                                    "type": "approval_request",
                                    "request": json.loads(ev.text),
                                })
                            elif ev.kind == "usage":
                                # THE EXA BUBBLE INSTRUMENTATION (2026-08-22):
                                # the done event now carries the usage
                                # payload (context size/used) + the elapsed
                                # seconds + the model — the frontend renders
                                # them on the bubble so model swaps and
                                # response times are observable (the user's
                                # ask: we're swapping LLMs + troubleshooting
                                # response time).
                                usage_payload = {}
                                try:
                                    up = json.loads(ev.text) if ev.text else {}
                                    usage_payload = {
                                        "size": up.get("size"),
                                        "used": up.get("used"),
                                    }
                                except Exception:
                                    pass
                                await websocket.send_json({
                                    "type": "done",
                                    "reply": "".join(parts),
                                    "usage": usage_payload,
                                    # monotonic clock (matches turn_started's
                                    # time.monotonic() — a time.time() mix would
                                    # produce epoch-vs-monotonic garbage like
                                    # '1786906591.5s'; fixed 2026-08-22)
                                    "elapsed_ms": int((time.monotonic() - turn_started) * 1000) if 'turn_started' in dir() else 0,
                                    "model": exa_model,
                                })
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        # after a cancel, an EOF/connection error is the
                        # expected outcome of the escalation kill — not a
                        # user-facing error
                        if not cancel_event.is_set():
                            try:
                                await websocket.send_json({"type": "status", "status": "error", "message": str(e)})
                            except Exception:
                                pass
                        else:
                            # THE CRASH-ON-CANCEL (2026-08-21, live finding):
                            # when the ACP supervisor's background task dies
                            # mid-interrupt (RequestError: Internal error —
                            # a cancel racing a naturally-ending turn), the
                            # stream ends with an EXCEPTION, not a clean
                            # usage/closed sentinel. _halt_agent would see
                            # 'stream ended' and wrongly conclude the gentle
                            # interrupt worked — leaving a broken-but-alive
                            # subprocess for the next prompt (the freeze).
                            # Flag it so _halt_agent closes (kills) the
                            # subprocess and the next prompt respawns fresh.
                            stream_crashed = True
                    finally:
                        streaming = False
                        # (time_limit is reported inline when the cap fires —
                        # the dedup flag keeps the halt from re-reporting)
                        # signal _halt_agent: the stream ended. NOTE: this
                        # fires on the natural end (gentle interrupt worked)
                        # OR on the escalation kill (subprocess EOF) — either
                        # way the agent is no longer executing.
                        stream_ended.set()
                        # THE DRAIN WAKE-UP (2026-08-30): the queued prompt
                        # must fire the moment the stream ends — the main
                        # loop's incoming.get() would otherwise block until
                        # the NEXT ws message (the queued prompt stuck).
                        await incoming.put(("_stream_ended", None))

                asyncio.create_task(_stream_run())
                # the main loop continues — approval_response, cancel,
                # and nuke are processed WHILE the stream runs.
                continue
        finally:
            recv_task.cancel()
            # DISCONNECT HALT (2026-08-13 incident): the WS going away
            # mid-turn used to only DETACH the stream — the Hermes
            # subprocess kept running the prompt to completion (with no
            # user attached to stop it, a runaway was the result).
            # With no receiver on the socket, halt the agent: gentle
            # session/cancel first, escalate to the kill if the stream
            # doesn't end within the grace window. The next panel open
            # respawns fresh.
            if streaming:
                # THE FRESH-TURN GRACE (2026-08-30, the user's /usage
                # cancel): the page's ws can blip mid-reconnect — a
                # JUST-started turn is the reconnect's victim, not a
                # runaway. The disconnect-halt's cancel was killing
                # the fresh turns (the log: 'Prompt on session:
                # /usage' + 'session/cancel sent' the same second,
                # 'interrupted_during_api_call'). A turn under
                # FRESH_TURN_GRACE_SECONDS is left to the reconnect's
                # re-attached ws; older turns still halt (the
                # runaway-protection stands).
                if time.monotonic() - turn_started < FRESH_TURN_GRACE_SECONDS:
                    logger.warning(
                        "external-agent: ws dropped %.1fs into the turn — within the fresh-turn grace, "
                        "leaving the turn to the reconnect",
                        time.monotonic() - turn_started,
                    )
                else:
                    try:
                        await client.cancel()
                        try:
                            await asyncio.wait_for(stream_ended.wait(), timeout=CANCEL_GRACE_SECONDS)
                        except asyncio.TimeoutError:
                            await client.close()
                    except Exception:
                        pass
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "status", "status": "error", "message": str(e)})
        except Exception:
            pass
