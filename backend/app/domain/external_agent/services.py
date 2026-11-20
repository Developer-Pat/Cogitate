"""
External agent (Hermes/OpenClaw) ACP client — the agent side panel's
backend.

Thin ACP client: spawns `hermes acp` as a local subprocess and
speaks JSON-RPC 2.0 over stdio (initialize -> session/new ->
session/prompt -> session/close). The agent runtime, tools, memory,
and streaming are all Hermes' — this service only manages the
subprocess and relays messages. This is the thin-ACP-client pattern:
we do NOT reimplement an agent; we drive an external one.

Protocol notes (discovered by scripts/spikes/acp_spike.py):
- session/new requires cwd; mcpServers must be a LIST []
- session/prompt takes CONTENT BLOCKS directly in the prompt list
  (wrapping in {role, content} is pydantic-rejected)
- completion = the id:N session/prompt RESULT (stopReason), NOT a
  status=completed session/update event
- reply streams as session/update events with
  update.sessionUpdate = agent_message_chunk / agent_thought_chunk
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import signal
import json
import logging
import os
import shutil
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# The reserved consultant identity for the session-grant bridge
# (Phase D): fix_mode ON issues session-scoped grants for the
# keyed Cogitate tools under this identity (granted_by=user).
# The ACP strictTools gate remains the enforcement for Exa's own
# write tools; these grants make the user's fix-mode grant a
# first-class, inspectable object (study 11).
EXTERNAL_AGENT_ID = "external"

# THE PERMISSION REPLY (2026-08-21, corrected 2026-11-20): an ACP
# RequestPermissionResponse's `outcome` is a discriminated UNION, so the reply is
# NESTED — `{"outcome": {"outcome": "selected", "optionId": ...}}`. Verified live
# 2026-08-21: the FLAT form died with "Input should be a valid dictionary or object
# to extract fields from". The cancelled branch kept answering the flat form after
# that fix and killed the session on a ValidationError (measured 2026-11-20), so
# BOTH replies now come from these two functions — one shape, one home.
def selected_outcome(option_id: str) -> dict:
    return {"outcome": {"outcome": "selected", "optionId": option_id}}


def cancelled_outcome() -> dict:
    return {"outcome": {"outcome": "cancelled"}}


# How long the client waits for the user before answering `cancelled` — the
# adapter's own requester timeout (60s default), so the reply never lands after
# the agent gave up. A module constant so a test can shorten it.
PERMISSION_TIMEOUT_SECONDS = 60


class ExternalAgentInactive(RuntimeError):
    """Exa has not been activated — refuse instead of spawning anything.

    A MISSING FEATURE IS NOT A FAILURE (2026-11-18, the user's ruling): Exa
    ships included but de-activated, with no runtime and no key on a fresh
    install. Reaching it must say that plainly, so every spawn raises this
    rather than letting `hermes` fail with FileNotFoundError — the difference
    between "you haven't turned this on" and "the app is broken".
    """

    code = "external_agent_inactive"


@dataclass
class AcpEvent:
    """One streamed event from the ACP subprocess."""

    kind: str  # "message" | "thought" | "usage" | "tool_call" | "approval" | "status"
    text: str = ""
    session_update: str = ""


class AcpClient:
    """Owns one `hermes acp` subprocess; relaying messages."""

    # The permission-tier vocabulary (2026-08-21): chat = per-edit
    # approval (the card), fix = cwd-scoped auto-approve, yolo =
    # auto-approve everything. Maps to the ACP edit_approval_policy:
    #   chat -> "ask"                (every edit prompts)
    #   fix  -> "workspace_session"  (auto-approve inside cwd)
    #   yolo -> "session"            (auto-approve ALL — the secret
    #                                path guard still asks)
    PERMISSION_TIERS = ("chat", "fix", "yolo")
    POLICY_BY_TIER = {
        "chat": "ask",
        "fix": "workspace_session",
        "yolo": "session",
    }

    def __init__(self, command: list[str] | None = None, cwd: str | None = None, fix_mode: bool = False, permission_tier: str | None = None, enabled: bool = True) -> None:
        self.command = command or ["hermes", "acp"]
        # THE ACTIVATION (2026-11-18). Defaults True so a caller that has no
        # config in hand (the consult tool, the tests' fake scripts) keeps the
        # pre-activation behaviour; every user-facing path resolves the
        # persisted `enabled` and passes it, so the gate is the CONFIG's.
        self.enabled = enabled
        self.cwd = cwd or os.getcwd()
        # the tier is the field of truth; fix_mode is the compat bool
        # (True == the fix tier) for the pre-2026-08-21 callers
        if permission_tier is not None:
            self.permission_tier = permission_tier
        else:
            self.permission_tier = "fix" if fix_mode else "chat"
        assert self.permission_tier in self.PERMISSION_TIERS, (
            f"unknown permission tier: {self.permission_tier!r}"
        )
        self._proc: asyncio.subprocess.Process | None = None
        self._session_id: str | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._stderr_task: asyncio.Task | None = None
        self._msg_id = 0
        self._lock = asyncio.Lock()
        # Phase-1 queue rework (2026-08-12): ACP allows ONE active
        # prompt per session. Prompts serialize on _prompt_lock; each
        # gets its OWN consumer queue (_active_queue) so events never
        # interleave or get stolen by a concurrent consumer. Events
        # with no active prompt (startup, background) go to the
        # shared _event_queue.
        self._event_queue: asyncio.Queue[AcpEvent] = asyncio.Queue()
        self._active_queue: asyncio.Queue[AcpEvent] | None = None
        self._prompt_lock = asyncio.Lock()
        # CHAT AUTHORIZATION (2026-08-21): incoming
        # session/request_permission futures keyed by their ACP
        # request id. resolve_permission() completes the matching
        # future with the user's option; the ACP read loop replies
        # with the result (the adapter's requester blocks on it).
        self._pending_permissions: dict[str, asyncio.Future] = {}
        self._perm_lock = asyncio.Lock()

    @property
    def session_id(self) -> str | None:
        return self._session_id

    @property
    def connected(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    async def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

    async def _stderr_loop(self) -> None:
        """Drain the subprocess's stderr into the backend log.

        INCIDENT 2026-08-13: the agent's stderr was DEVNULL — when the
        agent died (or was killed), the diagnostic trail vanished. The
        pipe MUST be drained or the buffer fills and the subprocess
        blocks on write.
        """
        proc = self._proc  # the local capture: close() may null self._proc
        assert proc and proc.stderr
        try:
            while True:
                try:
                    line = await proc.stderr.readline()
                except ValueError:
                    # THE BIG-LINE GUARD (2026-09-08, the LIVE false
                    # alarm): the StreamReader's default 64KB limit —
                    # an oversized line raises ValueError instead of
                    # returning. The drainer used to crash, and the
                    # finally raised the process-EXIT alarm while the
                    # process was ALIVE. Skip the line, keep draining.
                    logger.warning(
                        "external-agent: a stderr line exceeded the stream "
                        "limit — skipping it (the process stays up)"
                    )
                    continue
                if not line:
                    break
                logger.info(
                    "external-agent stderr: %s",
                    line.decode("utf-8", errors="replace").rstrip(),
                )
        finally:
            # EOF on the stderr pipe = the subprocess died (or is
            # dying). THE PROCESS-EXIT ALARM (2026-09-08, ruled):
            # the drainer used to break SILENTLY — the backend
            # learned of Exa's death only on the next prompt.
            await self._on_pipe_eof()

    async def _send(self, payload: dict) -> asyncio.Future:
        """Write a request; return a future resolved by the matching
        id:N response."""
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        req_id = payload["id"]
        self._pending[req_id] = fut
        line = json.dumps(payload) + "\n"
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(line.encode("utf-8"))
        await self._proc.stdin.drain()
        return fut

    async def _read_loop(self) -> None:
        """Consume stdout; resolve pending request futures and route
        streamed events to the event queue."""
        proc = self._proc  # the local capture: close() may null self._proc
        assert proc and proc.stdout
        clean_session_end = False
        try:
            while True:
                try:
                    line = await proc.stdout.readline()
                except ValueError:
                    # THE BIG-LINE GUARD (2026-09-08, the LIVE false
                    # alarm): same as the stderr loop — an oversized
                    # JSON-RPC line crashed the drainer and the
                    # finally raised the EXIT alarm while the process
                    # was alive (the 17:39 incident: the turn dropped
                    # mid-run, the user saw silence). Skip + continue.
                    logger.warning(
                        "external-agent: a stdout line exceeded the stream "
                        "limit — skipping it (the process stays up)"
                    )
                    continue
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "id" in msg and msg.get("id") in self._pending:
                    fut = self._pending.pop(msg["id"])
                    if not fut.done():
                        fut.set_result(msg)
                elif msg.get("method") == "session/update":
                    up = msg.get("params", {}).get("update", {})
                    content = up.get("content", {})
                    sw = up.get("sessionUpdate", "")
                    if sw in ("agent_message_chunk", "agent_thought_chunk", "usage_update", "tool_call"):
                        ev = AcpEvent(
                            kind="message" if sw == "agent_message_chunk"
                            else "thought" if sw == "agent_thought_chunk"
                            else "tool_call" if sw == "tool_call"
                            else "usage",
                            # the usage event carries the FULL update payload
                            # (size/used context pressure — 2026-08-22: the
                            # frontend renders it on the bubble so model
                            # swaps + response times are observable)
                            text=json.dumps(up) if sw in ("tool_call", "usage_update") else (content.get("text", "") if isinstance(content, dict) else ""),
                            session_update=sw,
                        )
                        # route to the active prompt's queue when one is
                        # in flight, else the shared queue (startup etc.)
                        target = self._active_queue or self._event_queue
                        await target.put(ev)
                elif msg.get("method") == "session/request_permission":
                    # CHAT AUTHORIZATION (2026-08-21): the adapter asks
                    # for permission (an edit proposal with the diff).
                    # Store the request so resolve_permission can answer;
                    # forward the request as an approval event (the
                    # frontend renders the Approve/Deny card).
                    await self._handle_permission_request(msg)
                elif msg.get("method") == "session/closed":
                    clean_session_end = True
                    break
        finally:
            # stdout EOF = the process DIED — raise the alarm. The
            # CLEAN session/closed break is NOT a death (the agent may
            # keep the process for the next session; its actual exit
            # EOFs the stderr pipe, which alarms). The once-guard in
            # _on_pipe_eof keeps double-EOF and the intentional
            # close() quiet.
            if not clean_session_end:
                await self._on_pipe_eof()

    async def _on_pipe_eof(self) -> None:
        """THE PROCESS-EXIT ALARM (2026-09-08).

        Called when a drain pipe hits EOF — the subprocess died. The
        silent-break class: when Exa died (or hung itself into a kill),
        the drainers broke on EOF with NO log and the backend didn't
        know until the next prompt — while an in-flight stream hung on
        the dead process. Now the EOF:
        1. logs the exit (the returncode) — 'Exa died' is never a
           mystery again;
        2. wakes the in-flight stream (the 'closed' sentinel) so the
           turn ENDS instead of hanging;
        3. fails the pending request futures (initialize/session-new)
           so no caller waits on a dead process;
        4. nulls self._proc — the once-guard. The intentional close()
           nulls _proc FIRST, so a killed-on-purpose Exa stays quiet
           here, and whichever pipe EOFs second sees the null and
           stays silent too.
        """
        if self._proc is None:
            return  # intentional close (or already handled)
        proc = self._proc
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except (asyncio.TimeoutError, ProcessLookupError):
            pass
        rc = proc.returncode
        logger.warning(
            "External agent subprocess EXITED unexpectedly "
            "(returncode=%s session=%s) — the next prompt will respawn it",
            rc,
            self._session_id,
        )
        self._wake_stream()
        pending = list(self._pending.items())
        self._pending.clear()
        for _req_id, fut in pending:
            if not fut.done():
                fut.set_exception(
                    RuntimeError(
                        f"external agent subprocess exited (returncode={rc})"
                    )
                )
        self._proc = None

    async def _handle_permission_request(self, msg: dict) -> None:
        """Store the permission future + emit the approval event.

        The ACP protocol: session/request_permission with params
        {options, session_id, tool_call}. The client must reply
        with a RequestPermissionResponse (outcome selected with an
        option_id, or cancelled). The read loop replies when the
        user resolves the request via resolve_permission.
        """
        req_id = str(msg.get("id"))
        params = msg.get("params", {}) or {}
        options = params.get("options", []) or []
        tool_call = params.get("tool_call", {}) or {}
        # the future the read loop resolves with the user's answer —
        # REGISTERED FIRST so resolve_permission can never miss it
        # (the generator body may resolve as soon as the approval
        # event is yielded; the future must exist by then)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending_permissions[req_id] = fut

        ev = AcpEvent(
            kind="approval",
            text=json.dumps({
                "request_id": req_id,
                "session_id": params.get("session_id", ""),
                "title": tool_call.get("title", "Permission requested"),
                "tool_call_id": tool_call.get("tool_call_id", ""),
                "options": options,
                "content": tool_call.get("content", []),
            }),
        )
        target = self._active_queue or self._event_queue
        await target.put(ev)
        try:
            # match the adapter's requester timeout (60s default) so
            # the response never lands after the adapter gave up
            result = await asyncio.wait_for(fut, timeout=PERMISSION_TIMEOUT_SECONDS)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            # THE SAME SHAPE AS A DENY (2026-11-20): this branch used to answer
            # {"outcome": "cancelled"} — a bare string where the schema wants an
            # object — and the response died on a ValidationError, taking the
            # session with it. Every reply now goes through the one builder.
            result = cancelled_outcome()
        finally:
            self._pending_permissions.pop(req_id, None)
        # reply with the selected option (the adapter's requester
        # is blocked on this response)
        try:
            response = {
                "jsonrpc": "2.0",
                "id": msg.get("id"),
                "result": result,
            }
            assert self._proc and self._proc.stdin
            self._proc.stdin.write((json.dumps(response) + "\n").encode("utf-8"))
            await self._proc.stdin.drain()
        except Exception:
            pass

    async def resolve_permission(self, request_id: str, option_id: str) -> bool:
        """Resolve a pending permission request (the chat's response).

        Returns True when the request was found + resolved; False
        for an unknown/stale request id (dropped — the security
        property: only the matching future resolves).
        """
        fut = self._pending_permissions.get(request_id)
        if fut is None or fut.done():
            return False
        if option_id == "deny":
            # deny IS cancelled in ACP's vocabulary — the same builder the
            # timeout branch uses, so the two can never disagree on the shape.
            fut.set_result(cancelled_outcome())
        else:
            fut.set_result(selected_outcome(option_id))
        return True

    def _session_new_params(self) -> dict:
        """session/new params — the FIX-MODE GATE (2026-08-12).

        Read-only (default) spawns with capabilities.strictTools=True
        which blocks the dedicated write tools (write_file/patch) at
        the tool layer; fix mode (explicit user grant) omits it. NOTE:
        strictTools does NOT block shell-based writes via terminal —
        the server-side prompt directive + the watchable tool stream
        are the other two layers of the gate.
        """
        # CHAT AUTHORIZATION (2026-08-21): strictTools is NOT set in
        # ANY tier — the write tools must be AVAILABLE so an edit
        # proposal can reach the permission requester. The gate is
        # the tier: the per-edit card (chat), the cwd auto-approve
        # (fix), the everything auto-approve (yolo). Read-only-ness
        # for the consult surface is the directive + the 60s-denial
        # of an unapproved edit, not a tool-layer block.
        params: dict = {"cwd": self.cwd, "mcpServers": []}
        return params

    async def _set_edit_approval_policy(self, policy: str) -> None:
        """Set the session's edit-approval policy via ACP.

        Wire method: ``session/set_config_option`` with config_id
        ``edit_approval_policy``. Values: ``ask`` (every edit
        prompts → denied since we never approve), ``workspace_session``
        (auto-approve edits inside cwd), ``session`` (auto-approve all
        but sensitive paths). Best-effort: if Hermes rejects it, the
        prompt directive + strictTools still hold the line.
        """
        if not self._session_id:
            return
        fut = await self._send({
            "jsonrpc": "2.0",
            "id": await self._next_id(),
            "method": "session/set_config_option",
            "params": {
                "config_id": "edit_approval_policy",
                "session_id": self._session_id,
                "value": policy,
            },
        })
        try:
            await asyncio.wait_for(fut, timeout=10)
        except asyncio.TimeoutError:
            logger.warning("external-agent: edit-approval policy set timed out")

    async def start(self) -> None:
        """Spawn the subprocess + initialize + create a session."""
        if self.connected:
            return
        # THE GATE: checked before anything is created, so a de-activated Exa
        # costs no process, no failed spawn and no confusing traceback.
        if not self.enabled:
            raise ExternalAgentInactive(
                "Exa is not active. Activating it is your decision — turn it on "
                "on the Exa page when you want it to answer."
            )
        # THE STATE ISOLATION (Phase 1 2026-08-18, hardened 2026-09-08):
        # the external agent gets its OWN Hermes home inside the project
        # (Paths.exa_home) — per-install, shippable, isolated from the
        # operator's ~/.hermes. The guard fires on the command's
        # BASENAME so any hermes-shaped command (bare "hermes" or an
        # absolute path to a hermes binary) gets the isolated home — a
        # command-shape change can never silently fall through to the
        # operator's home. The fake ACP scripts in the tests (python3)
        # keep their env untouched.
        env = os.environ.copy()
        if self.command and os.path.basename(self.command[0]) in ("hermes", "hermes.exe"):
            from app.core.config import Paths
            env["HERMES_HOME"] = str(Paths.exa_home)
            logger.info(
                "External agent spawn: HERMES_HOME=%s (command=%s)",
                env["HERMES_HOME"],
                self.command[0],
            )
        self._proc = await asyncio.create_subprocess_exec(
            *self.command,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # THE STREAM LIMIT (2026-09-08, the live false alarm): the
            # asyncio default is 64KB — the hermes's larger payloads
            # (LSP diagnostics, big tool results) can exceed it, and
            # the readline then raises instead of returning. Raised to
            # 4MB; the loops also guard the ValueError either way.
            limit=4 * 1024 * 1024,
            # NUKE TAG (2026-08-13): start_new_session makes Exa its own
            # process-group leader. That group is the TARGET for a
            # nuke — killpg(self._proc.pid) kills Exa AND any tool
            # children it spawned (terminal commands), and can NEVER
            # touch the backend, the VS Code extension, or the CLI
            # (they're in different process groups). This replaces the
            # pkill -f 'hermes acp' suicide bomb: targeted by
            # ownership, not by process name.
            start_new_session=True,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        self._stderr_task = asyncio.create_task(self._stderr_loop())

        # initialize
        await self._send({
            "jsonrpc": "2.0",
            "id": await self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": 1,
                "clientCapabilities": {"streaming": True},
                "clientInfo": {"name": "cogitate-agent-panel", "version": "0.1.0"},
            },
        })

        # session/new — cwd + mcpServers LIST (spike discovery)
        fut = await self._send({
            "jsonrpc": "2.0",
            "id": await self._next_id(),
            "method": "session/new",
            "params": self._session_new_params(),
        })
        resp = await asyncio.wait_for(fut, timeout=30)
        result = resp.get("result", {})
        if isinstance(result, dict) and result.get("sessionId"):
            self._session_id = result["sessionId"]
            logger.info("External agent session created: %s", self._session_id)
        else:
            err = resp.get("error", {})
            raise RuntimeError(f"session/new failed: {err.get('message', resp)}")

        # RACE FIX (2026-08-12): hermes emits available_commands +
        # a startup usage_update AFTER the session/new result. Sending
        # a prompt before those finish gets the prompt silently lost.
        # Wait for the startup usage_update as the 'session ready'
        # signal before returning.
        deadline = asyncio.get_running_loop().time() + 30
        while asyncio.get_running_loop().time() < deadline:
            try:
                ev = await asyncio.wait_for(self._event_queue.get(), timeout=1)
            except asyncio.TimeoutError:
                continue
            if ev.kind == "usage":
                break

        # FIX-MODE GATE — tool-level (2026-08-12, verified live):
        # session/set_config_option(edit_approval_policy=...) is the
        # REAL enforcement point. 'workspace_session' auto-approves
        # edits inside cwd (fix granted); 'ask' means every edit
        # prompts and, since this app never answers approval prompts,
        # write_file/patch are DENIED (read-only). This is the true
        # 'boundary at the API' the design report called for — Hermes
        # itself enforces, not just our prompt directive. Sensitive
        # paths (.env, .ssh, .git) are always guarded by Hermes.
        # NOTE: must run AFTER the ready-wait — the session must be
        # fully initialized or the config call goes unanswered
        # (observed: 10s timeout when sent too early).
        await self._set_edit_approval_policy(
            self.POLICY_BY_TIER.get(self.permission_tier, "ask")
        )

    async def stream_prompt(self, text: str):
        """Send a prompt; yield THIS prompt's events as they arrive.

        Async generator: holds _prompt_lock for the whole turn (ACP
        allows one active prompt per session). The read loop routes
        this prompt's events to its own queue; concurrent callers
        wait on the lock and each receives only its own events (no
        interleaving, no stolen chunks). Ends at the usage event;
        the lock releases when the generator exhausts or is closed.
        """
        assert self._session_id, "call start() first"
        async with self._prompt_lock:
            queue: asyncio.Queue[AcpEvent] = asyncio.Queue()
            self._active_queue = queue
            try:
                await self._send({
                    "jsonrpc": "2.0",
                    "id": await self._next_id(),
                    "method": "session/prompt",
                    "params": {
                        "sessionId": self._session_id,
                        "prompt": [{"type": "text", "text": text}],
                    },
                })
                while True:
                    ev = await asyncio.wait_for(queue.get(), timeout=120)
                    yield ev
                    # "closed" = the subprocess was killed (nuke/close
                    # pushed the sentinel) — exit the generator so the
                    # lock releases and the router can respawn
                    if ev.kind in ("usage", "closed"):
                        break
            finally:
                self._active_queue = None

    async def cancel(self) -> None:
        """Gentle interrupt: send the ACP session/cancel notification.

        Standard ACP (acp/meta.py: AGENT_METHODS['session_cancel'] =
        'session/cancel') — any ACP-speaking agent (Hermes, OpenClaw, ...)
        implements it. It is a NOTIFICATION: no id, no response,
        fire-and-forget. Hermes maps it to agent.interrupt() — the same
        mechanism Ctrl+C uses in the CLI: the current turn stops, the
        session stays alive, the next prompt continues normally.

        If the agent does not honor the interrupt (stuck in a tool loop),
        the caller escalates to close() (kill) after a grace period.
        """
        if not self._session_id or not self._proc or self._proc.returncode is not None:
            return
        line = json.dumps({
            "jsonrpc": "2.0",
            "method": "session/cancel",
            "params": {"sessionId": self._session_id},
        }) + "\n"
        assert self._proc.stdin
        self._proc.stdin.write(line.encode("utf-8"))
        await self._proc.stdin.drain()
        logger.info("External agent session/cancel sent (%s)", self._session_id)

    async def prompt(self, text: str) -> str:
        """Send a prompt; wait for completion; return the reply text."""
        parts: list[str] = []
        async for ev in self.stream_prompt(text):
            if ev.kind == "message":
                parts.append(ev.text)
        return "".join(parts)

    async def close(self) -> None:
        # RACE FIX (2026-08-13): capture the proc in a local and null
        # self._proc IMMEDIATELY. A concurrent start() (e.g. the router
        # respawning after an idle stop) would otherwise overwrite
        # self._proc while this coroutine's tail (terminate/wait) still
        # references it — killing the NEW subprocess (the empty-error
        # respawn failure in test_ws_prompt_after_cancel_respawns).
        proc = self._proc
        session_id = self._session_id
        self._proc = None
        self._session_id = None
        if proc and proc.returncode is None:
            try:
                fut = await self._send({
                    "jsonrpc": "2.0",
                    "id": await self._next_id(),
                    "method": "session/close",
                    "params": {"sessionId": session_id},
                })
                # bounded: a busy agent (mid-prompt, not reading stdin)
                # never answers session/close — don't let the graceful
                # attempt block the kill (cancel path, 2026-08-13)
                await asyncio.wait_for(fut, timeout=2)
            except Exception:
                pass
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3)
            except asyncio.TimeoutError:
                proc.kill()
        # wake any blocked stream (the subprocess is gone)
        self._wake_stream()
        # reap the stdout/stderr drain tasks (they exit on EOF once the
        # subprocess is gone; cancel in case it died without closing pipes)
        for task in (self._reader_task, self._stderr_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            elif task is not None and task.done() and task.exception() is not None:
                # retrieve the exception — the teardown race (the task
                # raised between done() and the await) otherwise leaves
                # "Task exception was never retrieved" noise on close
                # (2026-08-17: seen in the Exa probe harness)
                try:
                    task.exception()
                except (asyncio.CancelledError, Exception):
                    pass


    def _wake_stream(self) -> None:
        """Push a 'closed' sentinel into the active prompt's queue so a
        stream generator blocked on queue.get() wakes and exits (the
        subprocess is gone — no more events will ever arrive)."""
        q = self._active_queue
        if q is not None:
            q.put_nowait(AcpEvent(kind="closed", text="", session_update=""))

    async def nuke(self) -> None:
        """Force-kill the agent subprocess AND its whole process tree.

        Targeted by the process group created at spawn
        (start_new_session=True): os.killpg(SIGKILL) hits Exa and any
        tool children it spawned (runaway terminal commands included),
        and nothing else — the backend, the VS Code extension, and the
        CLI are in different process groups. This is the 'nuke' option:
        no session/cancel, no grace, no PID-name matching (the pkill
        suicide bomb). Use when the gentle halt failed and the agent
        ignores everything.
        """
        proc = self._proc
        self._session_id = None
        self._proc = None
        if proc is None or proc.returncode is not None:
            return
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            logger.warning("External agent NUKE: killpg(%s) sent SIGKILL", proc.pid)
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except (asyncio.TimeoutError, ProcessLookupError):
            pass
        # wake any blocked stream so the router exits promptly
        self._wake_stream()
        # reap the drain tasks (subprocess is gone — pipes EOF)
        for task in (self._reader_task, self._stderr_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            elif task is not None and task.done() and task.exception() is not None:
                # retrieve the exception — the teardown race (the task
                # raised between done() and the await) otherwise leaves
                # "Task exception was never retrieved" noise on close
                # (2026-08-17: seen in the Exa probe harness)
                try:
                    task.exception()
                except (asyncio.CancelledError, Exception):
                    pass
        self._reader_task = None
        self._stderr_task = None


# singleton — the panel owns ONE subprocess for the app lifetime
_client: AcpClient | None = None


def get_acp_client(command: list[str] | None = None, cwd: str | None = None, fix_mode: bool | None = None, permission_tier: str | None = None, enabled: bool | None = None) -> AcpClient:
    """Return the singleton; created with the given command/cwd if
    not yet spawned (config-honoring first call). permission_tier
    (the 3-way grant: chat/fix/yolo, 2026-08-21) is applied when the
    client is created — a mid-session change requires a restart (the
    PUT /config endpoint closes the subprocess so the next spawn
    honors the new tier). fix_mode is the DEPRECATED compat bool.

    `enabled` (2026-11-18) is THE ACTIVATION: pass the persisted config's
    value. It is applied/rebuilt on EVERY call, not just at creation,
    because activation is exactly the kind of change that happens to a
    live singleton — activation must take effect on the next spawn
    without a backend restart.
    """
    global _client
    if _client is None:
        _client = AcpClient(command=command, cwd=cwd, fix_mode=bool(fix_mode), permission_tier=permission_tier, enabled=True if enabled is None else enabled)
    elif enabled is not None and _client.enabled != enabled:
        # THE DECISION, applied to the live singleton. Teardown of a running
        # session is the ROUTER's job (it can await close()); this function is
        # sync and must never block a request on it.
        logger.info(
            "external-agent: activation changed (%s -> %s)",
            _client.enabled, enabled,
        )
        _client.enabled = enabled
    if _client is not None and (
        (permission_tier is not None and _client.permission_tier != permission_tier)
        or (cwd is not None and _client.cwd != cwd)
    ):
        # THE CONFIG CHANGED (2026-08-21 tier; 2026-09-08 cwd — the
        # live catch): the config PUT closes the subprocess but the
        # singleton survives with the OLD params — the next spawn
        # would reuse them (e.g. cwd="" -> the os.getcwd() fallback =
        # backend/ even though the config now says the project root;
        # the session's workspace_session auto-approve stayed scoped
        # to backend/, so every project-root write asked + timed out
        # to denied). Rebuild the client so the new config is honored
        # on the next connection.
        logger.info(
            "external-agent: config changed (tier %s -> %s, cwd %s -> %s) — rebuilding the client",
            _client.permission_tier, permission_tier,
            _client.cwd, cwd,
        )
        _client = AcpClient(
            command=command or _client.command,
            cwd=cwd if cwd is not None else _client.cwd,
            permission_tier=permission_tier or _client.permission_tier,
            # the rebuild must not reset the activation decision
            enabled=_client.enabled,
        )
    return _client


# ────────────────────────────────────────────────────────────────
# Configuration (Agent Integration page)
# ────────────────────────────────────────────────────────────────

import shlex

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.domain.external_agent.schemas import ExternalAgentConfig
from app.domain.tools.models import Tool
from app.infrastructure.database.models import UserSettings

# UserSettings JSON key under which the external-agent config lives
CONFIG_KEY = "external_agent"

DEFAULT_CONFIG = ExternalAgentConfig()


async def get_config(db: AsyncSession) -> ExternalAgentConfig:
    """Load the persisted external-agent config (or defaults).

    Phase D: the persisted fix_mode flag is the source of truth for
    the toggle; the grants are its mirror. The status endpoint
    reads the grants for the badge.
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_key == "default")
    )
    row = result.scalars().first()
    if row is None:
        return DEFAULT_CONFIG
    blob = row.settings or {}
    saved = blob.get(CONFIG_KEY)
    if not isinstance(saved, dict):
        return DEFAULT_CONFIG
    # BACKWARD COMPAT (2026-08-21): the persisted JSON may still
    # hold the pre-yolo fix_mode bool (no permission_tier). Map it:
    # fix_mode True -> the fix tier; False -> chat. The tier wins
    # when both are present (new configs write the tier only).
    tier = saved.get("permission_tier")
    if tier is None and "fix_mode" in saved:
        tier = "fix" if saved.get("fix_mode") else "chat"
    return ExternalAgentConfig(**{
        k: v for k, v in saved.items()
        if k in {"enabled", "command", "cwd", "max_turn_seconds", "image",
                 "max_tool_calls_per_turn", "tool_call_checkin_every", "brains"}
    } | ({"permission_tier": tier} if tier is not None else {}))


def probe_runnable(cfg: ExternalAgentConfig) -> str | None:
    """None when the box can run the configured command; otherwise WHY NOT.

    `enabled` is the user's decision and `runnable` is whether the machine can
    honour it. Probing is the difference between advice and a guess: a fresh
    install enables Exa and then finds nothing to run, so the honest answer to
    "activate" includes whether the runtime is actually here.
    """
    parts = command_parts(cfg.command)
    if not parts:
        return "the configured command is empty"
    if shutil.which(parts[0]) is None:
        return (
            f"'{parts[0]}' is not on PATH — Exa runs on an external agent runtime "
            f"(the command is '{cfg.command}'), and nothing answers to it here"
        )
    return None


async def get_fix_grant_state(db: AsyncSession) -> bool:
    """The fix-mode badge state — reads the session grants.

    True when the consultant identity holds ANY live session
    grant (the flag is a view over the grants; the grants are the
    first-class object, study 11).
    """
    from app.domain.tools.grant_service import AgentToolGrantService
    grants = AgentToolGrantService(db)
    rows = await grants.grants_for_agent(EXTERNAL_AGENT_ID)
    now = datetime.now(timezone.utc)
    return any(
        g.scope == "session" and
        (g.expires_at is None or g.expires_at > now)
        for g in rows
    )


async def save_config(db: AsyncSession, cfg: ExternalAgentConfig) -> ExternalAgentConfig:
    """Persist config under the user_settings JSON blob.

    Phase D: the fix_mode toggle is bridged to the grants table —
    ON issues session grants (granted_by=user, scope=session) for
    the keyed tools under the consultant identity; OFF revokes
    them. The config flag is a VIEW over the grants, not a
    separate truth (the badge reads the grants).
    """
    result = await db.execute(
        select(UserSettings).where(UserSettings.user_key == "default")
    )
    row = result.scalars().first()
    prev = None
    if row is not None:
        blob = dict(row.settings or {})
        prev_blob = blob.get(CONFIG_KEY)
        if isinstance(prev_blob, dict):
            prev = prev_blob.get("fix_mode")
    if row is None:
        row = UserSettings(user_key="default", settings={})
        db.add(row)
    blob = dict(row.settings or {})
    blob[CONFIG_KEY] = cfg.model_dump()
    row.settings = blob
    await db.commit()
    await db.refresh(row)

    # the bridge: only act when the toggle CHANGED
    # the bridge: only act when the WRITE-ness CHANGED. The
    # write tiers are fix + yolo (2026-08-21): both issue the
    # session grants — the granularity (per-edit vs auto) is the
    # ACP policy, not the grants. prev is the persisted bool.
    granted_now = cfg.permission_tier in ("fix", "yolo")
    if prev != granted_now:
        from app.domain.tools.grant_service import AgentToolGrantService
        from app.domain.tools.capabilities import is_keyed
        grants = AgentToolGrantService(db)
        # keyed tools only — resolve via the capability tiers
        rows = (
            await db.execute(select(Tool.id, Tool.capability))
        ).all()
        keyed_ids = [tid for tid, cap in rows if is_keyed(cap)]
        if granted_now:
            for tid in keyed_ids:
                await grants.grant(
                    EXTERNAL_AGENT_ID, tid, granted_by="user", scope="session"
                )
        else:
            for tid in keyed_ids:
                await grants.revoke(EXTERNAL_AGENT_ID, tid, scope="session")
    return cfg


def command_parts(command: str) -> list[str]:
    """Split the configured command into argv (shlex)."""
    return shlex.split(command) if command else ["hermes", "acp"]


def make_client(cfg: ExternalAgentConfig) -> AcpClient:
    """Build an AcpClient honoring the persisted config."""
    parts = command_parts(cfg.command)
    return AcpClient(command=parts, cwd=cfg.cwd or None)
