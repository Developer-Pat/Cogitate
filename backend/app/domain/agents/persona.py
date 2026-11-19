"""The persona home (2026-09-02, the workspace-first partition).

THE MOVE: the agent's persona text lives in the WORKSPACE
(agents/<key>/persona.md — the agent's own folder, git-excluded).
The DB row keeps the same text as the synced fallback (registry
fields + the folder-less path + the export/import round-trip read
the row). The read path prefers the FILE; the write path syncs
BOTH — no drift, nothing dropped.

THE ONE-HOME RULE applies to the BEAT: outlet names live in the
sources store (state.json), NOT in the persona prose. The persona
points at the store ("your beat = the sources list in YOUR STORED
STATE") — prose naming outlets would drift from the store.
"""

from __future__ import annotations

from pathlib import Path

PERSONA_FILENAME = "persona.md"


def _workspace_dir(agent) -> Path | None:
    """The agent's workspace dir when it has a key (the call-time
    import — the tests monkeypatch workspace.AGENTS_ROOT)."""
    # `agent` arrives untyped, so getattr yields Any and `path / Any` is Any —
    # the return annotation then can't be honoured. Coerce at the boundary.
    # `agent` arrives untyped, so getattr yields Any and `AGENTS_ROOT / Any` is
    # Any — the declared return type can't be honoured. Coerce at the boundary;
    # AGENTS_ROOT itself is correctly typed (it comes from Paths).
    key = str(getattr(agent, "workspace_key", "") or "")
    if not key:
        return None
    key = str(key)
    from app.domain.agents.workspace import AGENTS_ROOT

    return AGENTS_ROOT / key


def persona_path(agent) -> Path | None:
    ws = _workspace_dir(agent)
    return (ws / PERSONA_FILENAME) if ws else None


def read_persona(agent) -> str | None:
    """The persona for the prompt: the workspace persona.md when it
    exists (folder-first), else the row's system_prompt fallback."""
    path = persona_path(agent)
    if path is not None and path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            import logging
            logging.getLogger(__name__).warning(
                "persona.md unreadable at %s — falling back to the row", path
            )
    return getattr(agent, "system_prompt", None) or None


def write_persona(agent, text: str) -> None:
    """Sync the persona to the workspace file when the agent has one.
    The row keeps the same text (the caller sets it); the file is the
    workspace home. Best-effort on the file — a write failure logs
    and keeps the row (no silent fallback: the warning is visible)."""
    path = persona_path(agent)
    if path is None:
        return  # no workspace — the row is the only home
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError:
        import logging
        logging.getLogger(__name__).warning(
            "persona.md write failed at %s — the row stays authoritative", path
        )
