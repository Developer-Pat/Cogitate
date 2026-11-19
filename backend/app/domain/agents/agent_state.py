"""The per-agent personal state store (2026-09-02).

THE SHALLOW-AGENT STATE (the user's ask): Bob — and any agent with a
workspace — keeps a PERSONAL state file INSIDE his own folder
(state.json): facts (location, timezone, …) + a sources list. Per-agent
files, NOT central cogitate.db tables (the minimal-DB shipping
direction; the tag-layer-sweeper cognitive_memory.db precedent for
per-agent stores, one serializable unit per agent folder).

THE WRITE PATH: the keyed tools (Update Sources / Update State) write
through this store — the execution service injects the agent's own
workspace as base_path (needs_workspace), the tool resolves the
workspace key, and every write returns the VERIFIED read-back (the
Set-Trigger-Schedule + Verify-Trigger-Config pattern).

THE ONE-HOME RULE: state.json is the only copy. The prompt reflects
it (prepare_chat_context's YOUR-STATE block); nothing is duplicated
in the persona or code.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.path_lock import path_lock, write_atomic

# The store file inside each agent's workspace.
STATE_FILENAME = "state.json"


class AgentStateUnreadable(RuntimeError):
    """The store file exists but cannot be parsed.

    THE SILENT-ERASURE FIX (2026-09-11): this used to return an empty
    store with a reassuring log line ("the next write repairs it"). That
    was backwards — the empty read ARMS the next write, which stores only
    its own key and thereby ERASES every other fact in the document. A
    file that cannot be read is now a loud refusal: callers surface it
    and no write happens on top of a broken read. The missing-file case
    is still "empty" and still correct — that is not this.
    """


# THE WRITE COORDINATION (2026-09-11): the per-path lock and the atomic
# write live in app.core.path_lock, shared with the beat store — the
# defects were the same class in both, so the fix is one implementation
# (see that module for the scope and its limits).


def workspace_path(workspace_key: str) -> Path:
    """The agent's workspace folder (project-anchored).

    THE CALL-TIME IMPORT (the testability pattern): the tests
    monkeypatch workspace.AGENTS_ROOT to a tmp dir; importing at
    call time honors the patch (a module-level bind would not).
    """
    from app.domain.agents.workspace import AGENTS_ROOT
    return AGENTS_ROOT / workspace_key


def _urlish(value: str) -> bool:
    """A loose URL check: scheme://host — enough to keep the sources
    list from becoming prose (the validation, not the gate)."""
    return bool(re.match(r"^[a-z][a-z0-9+.-]*://[^\s]+$", value.strip()))


def build_state_block(workspace_key: str | None) -> str | None:
    """The compact YOUR-STATE block for the system prompt.

    The ONE-HOME rule: the state store is written by the tools and
    read HERE — the prompt reflects the store, never a second copy.
    Returns None when the agent has no workspace/state (nothing is
    injected — the block appears only once facts or sources exist).
    """
    if not workspace_key:
        return None
    try:
        store = AgentStateStore(workspace_key)
        data = store.read()
    except Exception:
        return None  # unreadable store -> no block (the read warns)
    facts = data.get("facts") or {}
    sources = data.get("sources") or []
    if not facts and not sources:
        return None

    lines = [
        "YOUR STORED STATE (the ONE copy — kept in your workspace):",
    ]
    for key, rec in facts.items():
        if isinstance(rec, dict):
            value = rec.get("value", "")
            source = rec.get("source", "user")
        else:
            value = rec
            source = "user"
        lines.append(f"- {key}: {value} (source: {source})")
    if sources:
        lines.append("- my curated sources: " + ", ".join(sources))
    lines.append(
        "Keep this state current: store what you learn with the "
        "update-state / update-sources tools (never claim a stored "
        "fact you did not write)."
    )
    return "\n".join(lines)


class AgentStateStore:
    """File-backed key-value state for ONE agent workspace.

    Shape: {"facts": {key: {"value": str, "source": str, "updated_at": str}},
            "sources": [str, ...]}

    Write-coordinated per FILE (2026-09-11): the lock is shared by
    every instance touching the same path, so a fresh store per tool
    call no longer means a fresh lock that serializes nothing. Scope is
    threads WITHIN ONE PROCESS — see _path_lock.

    Construction: from the workspace_key (resolved against
    AGENTS_ROOT) OR an explicit directory path — the tools receive
    the agent's own folder as config["base_path"] (the execution
    service's needs_workspace grant) and pass THAT path (authoritative
    — never re-resolved, never a different folder).
    """

    def __init__(self, workspace_key: str | None = None, base_dir: str | Path | None = None) -> None:
        if base_dir is not None:
            self.workspace_key = Path(base_dir).name
            self.path = Path(base_dir) / STATE_FILENAME
        elif workspace_key:
            self.workspace_key = workspace_key
            self.path = workspace_path(workspace_key) / STATE_FILENAME
        else:
            raise ValueError("AgentStateStore needs a workspace_key or base_dir")
        self._lock = path_lock(self.path)

    # ---- read ---------------------------------------------------------

    def read(self) -> dict:
        if not self.path.exists():
            return {"facts": {}, "sources": []}
        try:
            with self.path.open(encoding="utf-8") as f:
                data = json.load(f)
            return {
                "facts": data.get("facts") or {},
                "sources": list(data.get("sources") or []),
            }
        except (json.JSONDecodeError, OSError) as e:
            # THE SILENT-ERASURE FIX (2026-09-11): returning empty here
            # did not "repair" anything — it armed the next write, which
            # then stored only its own key and erased every other fact.
            # Refuse loudly instead; callers surface it (build_state_block
            # already catches, so the prompt still builds).
            raise AgentStateUnreadable(
                f"agent state unreadable at {self.path}: {e} — refusing to "
                "treat it as empty (an empty read would let the next write "
                "erase the document). Fix or remove the file."
            ) from e

    def _write(self, data: dict) -> None:
        """Write the whole document atomically.

        Delegates to app.core.path_lock.write_atomic — a unique temp per
        writer (a FIXED temp name made two writers collide and one die
        with FileNotFoundError, 2026-09-11) and a cleanup on failure.
        """
        write_atomic(self.path, json.dumps(data, indent=2), suffix=".tmp")

    # ---- facts ---------------------------------------------------------

    def set_fact(self, key: str, value: str, source: str = "user") -> dict:
        """Store one fact (e.g. location). Returns the verified read-back."""
        key = key.strip().lower()
        if not key or not re.match(r"^[a-z0-9_.-]+$", key):
            raise ValueError(f"Invalid fact key: {key!r} — lowercase letters, digits, . _ -")
        if not value or not value.strip():
            raise ValueError("Fact value cannot be empty")
        import datetime as _dt
        now = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            data = self.read()
            facts = data["facts"]
            prev = facts.get(key)
            facts[key] = {
                "value": value.strip(),
                "source": source.strip() or "user",
                "updated_at": now,
                **({"previous": prev["value"]} if prev else {}),
            }
            self._write(data)
            return {key: facts[key]}

    def get_fact(self, key: str) -> dict | None:
        facts: dict = self.read().get("facts", {})
        return facts.get(key.strip().lower())

    def remove_fact(self, key: str) -> dict:
        """Delete a fact key ENTIRELY (Bob's finding, 2026-09-02: the
        store had no delete — facts could only be overwritten, never
        removed). A TRUE delete, not a tombstone: the key is gone from
        the file. Unknown keys are a harmless no-op (the remaining
        state returns untouched). Returns the remaining facts."""
        key = key.strip().lower()
        with self._lock:
            data = self.read()
            facts = data["facts"]
            if key in facts:
                del facts[key]
                self._write(data)
            return {"facts": facts}

    # ---- sources --------------------------------------------------------

    def update_sources(self, sources: list[str]) -> dict:
        """Add sources (URL-ish, validated). Returns the verified list."""
        cleaned = []
        for s in sources or []:
            s = s.strip()
            if not s:
                continue
            if not _urlish(s):
                raise ValueError(f"Invalid source: {s!r} — sources must be URLs (scheme://host)")
            cleaned.append(s)
        if not cleaned:
            raise ValueError("No valid sources to add")
        with self._lock:
            data = self.read()
            existing = list(data["sources"])
            for s in cleaned:
                if s not in existing:
                    existing.append(s)
            data["sources"] = existing
            self._write(data)
            return {"sources": existing}

    def remove_sources(self, sources: list[str]) -> dict:
        """Remove sources. Returns the verified remaining list."""
        drop = {s.strip() for s in (sources or []) if s.strip()}
        with self._lock:
            data = self.read()
            data["sources"] = [s for s in data["sources"] if s not in drop]
            self._write(data)
            return {"sources": data["sources"]}
