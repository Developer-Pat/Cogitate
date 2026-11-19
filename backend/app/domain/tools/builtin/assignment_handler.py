"""The agent's notebook tools (2026-10-13, the research-run arc).

Four tools over `app.domain.agents.assignments` — the per-assignment notebook an agent keeps
while it works:

- **open-assignment**  — open the piece of work (or resume it; same goal, same notebook);
- **add-note**         — record what you learned and where from, as you go;
- **read-assignment**  — read the notebook back (the digest, or every note);
- **close-assignment** — the piece is written; record its one-line outcome.

WHY THESE EXIST (measured): the census over ~7 weeks of logs counted 989 fetches / 26.9 M chars,
**91 URLs fetched more than once** and nothing surviving the turn — while the one public tool for
keeping notes (`update-state`) was called **6 times in 120 turns**. The notebook is the thing that
makes "what I already gathered" survive a turn, so it is written by TOOLS the agent calls: the
prompt block (`build_assignments_block`) shows the notebook, and these tools change it.

THE SANDBOX: every tool declares `needs_workspace=True` — the execution service injects the AGENT'S
OWN folder as `config["base_path"]` (the 2026-08-24 grant mechanism), and the store writes
`assignments/<id>.json` inside it. A missing `base_path` means the agent has no workspace yet, and
the tool says so rather than falling back to some other folder.

Every write returns the VERIFIED read-back: what the disk holds after the call, never what the
call intended.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

_WRITE_TAGS = ["op:write", "purpose:notebook", "source:workspace", "sandboxed", "stateful"]
_READ_TAGS = ["op:read", "purpose:notebook", "source:workspace", "sandboxed", "stateful"]


def _store(config: Dict[str, Any]):
    from app.domain.agents.assignments import AssignmentStore

    base = config.get("base_path") or ""
    if not base:
        raise ValueError(
            "This agent has no workspace yet — provision it first (the notebook lives in the "
            "agent's own folder)."
        )
    # the injected base_path IS the agent's folder — pass it directly (authoritative)
    return AssignmentStore(base_dir=base)


def _failure(exc: Exception) -> Dict[str, Any]:
    """A tool-call failure, classified the way the taxonomy expects."""
    from app.domain.agents.assignments import AssignmentNotFound, AssignmentUnreadable

    if isinstance(exc, AssignmentNotFound):
        kind = "not_found"
    elif isinstance(exc, AssignmentUnreadable):
        kind = "unreadable"
    else:
        kind = "validation"
    return {"success": False, "error": str(exc), "error_type": kind}


def _digest_of(config: Dict[str, Any]) -> Optional[str]:
    """The refreshed prompt block, so the model sees the notebook it just changed."""
    try:
        block = _store(config).digest()
    except Exception:
        return None
    return block if isinstance(block, str) else None


class OpenAssignmentTool:
    """open-assignment — open (or resume) the notebook for one piece of work."""

    name = "Open Assignment"
    slug = "open-assignment"
    capability = "file-write"
    needs_workspace = True
    description = (
        "Open your notebook for ONE piece of work — the assignment you are gathering for "
        "(e.g. \"the leading economic headline for Europe\"), kept in your workspace. Call this "
        "FIRST, before you search or fetch anything. Calling it again with the same goal RESUMES "
        "the same notebook (it never wipes one), so a follow-up turn keeps what you gathered. "
        "Returns the assignment id and what the notebook already holds."
    )
    icon = "edit"
    color = "#0EA5E9"
    tags = _WRITE_TAGS
    config_schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": (
                    "What you are trying to find out, in one line — it names the notebook "
                    "(e.g. 'the leading economic headline for Europe')"
                ),
            },
            "assignment_id": {
                "type": "string",
                "description": (
                    "Optional explicit id (lowercase letters/digits/hyphens). Omit it and the id "
                    "is derived from the goal."
                ),
            },
        },
        "required": ["goal"],
    }

    async def execute(self, config: Optional[dict] = None, **kwargs: Any) -> dict[str, Any]:
        config = config or {}
        goal = str(kwargs.get("goal") or "").strip()
        explicit = kwargs.get("assignment_id")
        try:
            store = _store(config)
            data, resumed = store.open(goal, str(explicit) if explicit else None)
        except (ValueError, LookupError, RuntimeError) as e:
            return _failure(e)
        return {
            "success": True,
            "assignment": data["id"],
            "goal": data["goal"],
            "status": data["status"],
            "resumed": resumed,
            "notes": len(data.get("notes") or []),
            "sources_seen": store.sources_seen(data["id"]),
            "digest": _digest_of(config),
        }


class AddNoteTool:
    """add-note — record what you learned, and where from."""

    name = "Add Note"
    slug = "add-note"
    capability = "file-write"
    needs_workspace = True
    description = (
        "Write ONE note into your open assignment: what you learned, in your own words, plus "
        "where it came from. Do this as you gather — after a fetch or a search that told you "
        "something — so the next turn (and your final write-up) works from your notes instead of "
        "re-reading the whole page. Keep it to what matters: the note is cheaper than the source, "
        "and a source you noted is a source you do not fetch twice. Omit assignment_id to write to "
        "your most recent open assignment. Returns the stored note (the verified read-back)."
    )
    icon = "edit-3"
    color = "#22C55E"
    tags = _WRITE_TAGS
    config_schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "What you learned — a fact, a figure, a quote, a lead worth following.",
            },
            "source": {
                "type": "string",
                "description": "Where it came from: the URL you fetched, or the outlet/page name.",
            },
            "title": {
                "type": "string",
                "description": "Optional short label for the note (e.g. the headline it came from).",
            },
            "assignment_id": {
                "type": "string",
                "description": "Optional — defaults to your most recent open assignment.",
            },
        },
        "required": ["text"],
    }

    async def execute(self, config: Optional[dict] = None, **kwargs: Any) -> dict[str, Any]:
        config = config or {}
        try:
            store = _store(config)
            result = store.add_note(
                text=str(kwargs.get("text") or ""),
                assignment_id=(str(kwargs["assignment_id"]) if kwargs.get("assignment_id") else None),
                source=str(kwargs.get("source") or ""),
                title=str(kwargs.get("title") or ""),
            )
        except (ValueError, LookupError, RuntimeError) as e:
            return _failure(e)
        return {
            "success": True,
            "assignment": result["assignment"],
            "note": result["entry"],
            "count": result["count"],
            "verified": result["entry"].get("text"),
            "digest": _digest_of(config),
        }


class ReadAssignmentTool:
    """read-assignment — read your notebook back before you write."""

    name = "Read Assignment"
    slug = "read-assignment"
    capability = "file-read"
    needs_workspace = True
    description = (
        "Read your notebook back: the open assignments, what each holds, and which sources you "
        "have ALREADY gathered from (read this before fetching anything — a URL listed there is "
        "one you would otherwise pay for twice). Set full=true for every note verbatim, which is "
        "what to do before writing the final piece. Omit assignment_id to read the current "
        "assignment."
    )
    icon = "book-open"
    color = "#64748B"
    tags = _READ_TAGS
    config_schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "assignment_id": {
                "type": "string",
                "description": "Optional — defaults to your most recent open assignment.",
            },
            "full": {
                "type": "boolean",
                "description": "true = every note verbatim; false (default) = the summary digest.",
            },
        },
        "required": [],
    }

    async def execute(self, config: Optional[dict] = None, **kwargs: Any) -> dict[str, Any]:
        config = config or {}
        want_full = bool(kwargs.get("full"))
        explicit = str(kwargs["assignment_id"]) if kwargs.get("assignment_id") else None
        try:
            store = _store(config)
            if want_full:
                data = store.resolve(explicit)
                return {
                    "success": True,
                    "assignment": data["id"],
                    "goal": data.get("goal", ""),
                    "status": data.get("status"),
                    "result": data.get("result", ""),
                    "notes": data.get("notes") or [],
                    "count": len(data.get("notes") or []),
                    "sources_seen": store.sources_seen(data["id"]),
                }
            digest = store.digest() if not explicit else _one(store, explicit)
        except (ValueError, LookupError, RuntimeError) as e:
            return _failure(e)
        if not digest:
            digest = (
                "No open assignment — call open-assignment first (one per piece of work). "
                "A closed assignment stays on disk: name its goal again to reopen it."
            )
        return {
            "success": True,
            "assignment": explicit or "(current)",
            "digest": digest,
            "assignments": [
                {"id": d["id"], "goal": d.get("goal", ""), "status": d.get("status"),
                 "notes": len(d.get("notes") or [])}
                for d in store.all_assignments()
            ],
        }


def _one(store: Any, assignment_id: str) -> str:
    """The digest for ONE named assignment (the store's digest covers the open ones)."""
    data = store.read(assignment_id)
    notes = data.get("notes") or []
    seen = store.sources_seen(assignment_id)
    lines = [
        f'ASSIGNMENT [{data["id"]}] "{data.get("goal", "")}" — {data.get("status")}, '
        f"{len([n for n in notes if n.get('kind') == 'note'])} note(s), "
        f"{len(seen)} source(s) fetched"
    ]
    for note in notes:
        if note.get("kind") == "fetch":
            lines.append(
                f"    · fetched {note.get('source')} ({note.get('chars', 0):,} chars)"
            )
        else:
            where = note.get("source") or "no source"
            text = (note.get("text") or "").replace("\n", " ")[:200]
            lines.append(f"    · {text} ({where})")
    return "\n".join(lines)


class CloseAssignmentTool:
    """close-assignment — the piece is written; one line says what came of it."""

    name = "Close Assignment"
    slug = "close-assignment"
    capability = "file-write"
    needs_workspace = True
    description = (
        "Close an assignment when its piece is written (or abandoned), with the one-line outcome "
        "in `result`. A closed assignment stops appearing in your prompt block and stops being "
        "the default for add-note; reopen it by opening the same goal again only if there is more "
        "to gather. Returns the closed assignment."
    )
    icon = "check-circle"
    color = "#F59E0B"
    tags = _WRITE_TAGS
    config_schema: Dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    arguments_schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "assignment_id": {
                "type": "string",
                "description": "Optional — defaults to your most recent open assignment.",
            },
            "result": {
                "type": "string",
                "description": "One line: what the piece came to (the headline, the finding, or why it was dropped).",
            },
        },
        "required": [],
    }

    async def execute(self, config: Optional[dict] = None, **kwargs: Any) -> dict[str, Any]:
        config = config or {}
        explicit = str(kwargs["assignment_id"]) if kwargs.get("assignment_id") else None
        try:
            store = _store(config)
            data = store.close(explicit, result=str(kwargs.get("result") or ""))
        except (ValueError, LookupError, RuntimeError) as e:
            return _failure(e)
        return {
            "success": True,
            "assignment": data["id"],
            "status": data["status"],
            "result": data.get("result", ""),
            "notes": len(data.get("notes") or []),
            "remaining_open": [
            d["id"] for d in store.all_assignments() if d.get("status") == "open"
        ],
        }
