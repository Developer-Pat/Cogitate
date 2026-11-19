"""The agent's notebooks — one ASSIGNMENT per file (2026-10-13, the research-run arc).

THE PROBLEM THIS SOLVES (measured, not assumed). The task-set census over ~7 weeks of logs
counted **989 fetches / 26.9 M characters** — **91 URLs fetched more than once** (one weather
page 18×), one payload of **463,980 characters** — while **nothing survived the turn**: a tool
result lives in the in-memory message list and dies with the turn. A run that cannot remember
what it gathered pays for it again, every round and every turn. The public tool for keeping
notes (`update-state`) was called **6 times in 120 turns**, so a notebook that depends on the
model remembering to write it is a notebook that stays empty.

THE SHAPE: an **assignment the agent opens** — the reporter's notebook, not a second agent
state. `agents/<key>/assignments/<id>.json` holds the goal, its status, and the notes the run
gathered: prose the agent wrote (`add-note`) plus what it fetched (`note_fetch` — the URL, its
size and a short excerpt, never the payload). It spans turns, so the next turn re-opens the
assignment instead of re-gathering it.

THE ONE-HOME RULE (copied from `agent_state`, which copied the beat store): the file is the only
copy. The prompt reflects it (`build_assignments_block`), the tools write it with a VERIFIED
read-back, and nothing is duplicated into the persona, the state file or the database.

THE DISCIPLINE — all of it by copy, because each of these defects was already paid for once:
- the per-path lock and the atomic write live in `app.core.path_lock`;
- a file that cannot be parsed is a **loud refusal** (`AssignmentUnreadable`), never an empty
  read — an empty read ARMS the next write, which would erase every note in the document;
- **ids are validated** against a strict pattern, so an id can never walk out of the agent's
  folder (the path-traversal class this codebase has been bitten by before);
- the CURRENT assignment is **derived** (the most recently updated open one) rather than a
  stored pointer that could drift from the folder.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.core.path_lock import path_lock, write_atomic

logger = logging.getLogger(__name__)

# The notebook folder inside each agent's workspace.
ASSIGNMENTS_DIRNAME = "assignments"

# What an id may look like. Strict on purpose: these arrive from a model, and they become
# FILENAMES inside the agent's folder — a traversal here would write outside the workspace.
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
_STATUSES = (STATUS_OPEN, STATUS_CLOSED)

# A note is the agent's own prose. Capped so the notebook cannot be used as a payload dump —
# the whole point is that a note is CHEAPER than the page it was read from.
NOTE_TEXT_LIMIT = 8000
# The goal names the assignment, and it is rendered in the prompt digest every turn — so a
# user message that IS a document (pasted prose, a log) must not become a 10K-character goal
# sitting in the system prompt. The capture takes the goal from the turn's request, so this
# cap is what keeps the automatic path honest.
GOAL_LIMIT = 300
# What `note_fetch` keeps: proof that a source was read (and a glimpse of it), never the body.
FETCH_EXCERPT_LIMIT = 500
# How many sources the prompt digest names before it says "and N more".
DIGEST_SOURCE_LIMIT = 12
# How recent a fetch must be for the notebook to ANSWER a re-fetch from its own record instead
# of letting the page be pulled again (2026-10-13, the freshness dedupe).
#
# Measured reason: three live runs of the same request re-fetched the same three URLs every
# time — 117,352 characters, the whole turn's cost — and the third run did it 11 minutes after
# the second, from a run whose own note said "fetched FRESH headlines". The prompt could not
# have stopped it: it named the sources and never said WHEN they were taken, so for a news beat
# re-fetching was a defensible judgement. 30 minutes is the default window — inside it a page is
# the same page — and a caller who disagrees says `refresh=true`. It is a DEFAULT, not a
# refusal: the tool still fetches whenever the caller asks for a new copy.
FRESH_FETCH_MINUTES = 30


class AssignmentUnreadable(RuntimeError):
    """The notebook file exists but cannot be parsed.

    The same ruling as `AgentStateUnreadable`: treating it as empty would arm the next write,
    which stores only its own entry and erases every note already in the document.
    """


class AssignmentNotFound(LookupError):
    """No assignment by that id (and none is current)."""


def _now() -> str:
    """Microsecond precision on purpose: `updated_at` decides which assignment is CURRENT, and
    two assignments opened in the same second must not tie (they would, at seconds)."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="microseconds")


def _parse_when(value: str) -> _dt.datetime | None:
    """A stored timestamp as an aware datetime, or None when it cannot be read."""
    try:
        parsed = _dt.datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_dt.timezone.utc)
    return parsed


def age_label(when: str, now: _dt.datetime | None = None) -> str:
    """How long ago a source was fetched, in words — "just now", "11 min ago", "3 h ago".

    The digest carries these so a caller can JUDGE freshness: "already gathered" and "still
    current" are different claims, and only the age tells them apart. An unreadable timestamp
    says so rather than guessing.
    """
    when_dt = _parse_when(when)
    if when_dt is None:
        return "at an unknown time"
    seconds = ((now or _dt.datetime.now(_dt.timezone.utc)) - when_dt).total_seconds()
    if seconds < 0:
        return "just now"
    if seconds < 90:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min ago"
    hours = int(minutes // 60)
    if hours < 48:
        return f"{hours} h ago"
    return f"{int(hours // 24)} days ago"


def _normalise_url(url: str) -> str:
    """The key two fetches of the same page share (a trailing slash is not a different page)."""
    return str(url or "").strip().rstrip("/")


def _sources_of(data: dict) -> list[dict]:
    """The distinct sources ONE document has gathered, most recent first, with ages.

    A URL fetched twice appears ONCE, carrying its LATEST fetch — which is the reading the
    caller acts on ("is what I have current?"), and it is what keeps a re-fetch from looking
    like a second source.
    """
    latest: dict[str, dict] = {}
    for entry in data.get("notes") or []:
        if entry.get("kind") != "fetch":
            continue
        url = _normalise_url(entry.get("source", ""))
        if not url:
            continue
        current = latest.get(url)
        if current is None or str(entry.get("at") or "") > str(current.get("at") or ""):
            latest[url] = {
                "url": url,
                "at": entry.get("at") or "",
                "age": age_label(entry.get("at") or ""),
                "chars": entry.get("chars") or 0,
                "title": entry.get("title") or "",
                "excerpt": entry.get("excerpt") or "",
            }
    return sorted(latest.values(), key=lambda s: str(s["at"]), reverse=True)


def _prose_of(data: dict, limit: int = 3, text_limit: int = 400) -> list[dict]:
    """The FINDINGS a document holds — its own prose notes, newest first, capped.

    What a caller would have needed the page to learn: the fetch record is provenance, the note
    is the finding. Returning the notes beside a served-from-the-notebook answer is what makes
    the answer usable instead of a promise.
    """
    prose = [n for n in (data.get("notes") or []) if n.get("kind") == "note"]
    return [
        {
            "at": n.get("at") or "",
            "source": n.get("source") or "",
            "title": n.get("title") or "",
            "text": str(n.get("text") or "")[:text_limit],
        }
        for n in prose[-limit:][::-1]
    ]


def _slug(goal: str) -> str:
    """A stable id from the goal.

    Non-Latin goals are a real case here (the news agents read Persian and Arabic sources), so a
    goal whose slug collapses to nothing gets a short digest of the goal instead of a shared
    catch-all id — two different assignments must never land in one file.
    """
    cleaned = re.sub(r"[^a-z0-9]+", "-", (goal or "").lower()).strip("-")[:48].strip("-")
    if len(cleaned) >= 3:
        return cleaned
    digest = hashlib.sha256((goal or "").encode("utf-8")).hexdigest()[:8]
    return f"assignment-{digest}"


def _validate_id(assignment_id: str) -> str:
    candidate = (assignment_id or "").strip().lower()
    if not _ID_RE.match(candidate):
        raise ValueError(
            f"Invalid assignment id {assignment_id!r} — lowercase letters, digits and hyphens, "
            "starting with a letter or digit (max 64). Use open-assignment to create one."
        )
    return candidate


def assignments_path(workspace_key: str) -> Path:
    """The agent's notebook folder (project-anchored).

    The call-time import is deliberate: the tests monkeypatch `workspace.AGENTS_ROOT`, and a
    module-level bind would ignore the patch.
    """
    from app.domain.agents.workspace import AGENTS_ROOT
    return AGENTS_ROOT / workspace_key / ASSIGNMENTS_DIRNAME


def build_assignments_block(workspace_key: str | None) -> str | None:
    """The compact OPEN-ASSIGNMENTS block for the system prompt.

    The one-home rule: the notebook is written by the tools and read HERE — the prompt reflects
    the store, never a second copy. `None` when the agent has no workspace or no open
    assignment (nothing is injected until there is something to inject).
    """
    if not workspace_key:
        return None
    try:
        store = AssignmentStore(workspace_key=workspace_key)
        return store.digest()
    except Exception:
        return None  # an unreadable notebook injects nothing (the read itself warned)


# ── THE AUTOMATIC HALF ────────────────────────────────────────────────────────────────
# The tools let an agent keep a notebook; these two make the notebook fill ITSELF. Measured
# reason: the manual store `update-state` drew 6 calls in 120 turns, and the notebook's own
# first live run used none of its four tools — the model fetched four pages (127,854 chars)
# and wrote nothing. So the fetch records itself, at the boundary where the turn's request is
# known, and the notebook is in the next prompt without anyone remembering to write it.


def fetch_facts(result: Any) -> dict | None:
    """The fetch facts inside a tool-result payload — `None` when it is not a fetch.

    Pure and module-level so the caller's hook stays thin and this is testable on its own. A
    FETCH is a payload that names a URL and carries a body (the web readers, and anything
    shaped like them). A SEARCH is deliberately not recorded here: a search is not a source
    read, and what a search contributes to the notebook is the tool contract's business.
    """
    if not isinstance(result, Mapping):
        return None
    url = str(result.get("url") or "").strip()
    if not url:
        return None

    body = result.get("content")
    if body is None:
        body = result.get("text")

    def _number(value: Any) -> int | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        return int(value)

    # THE BODY DECIDES WHETHER THIS IS A SOURCE, AND WHICH LENGTH IS THE SIZE.
    #
    # With a body: the TRUE size wins. A capped fetch returns head+tail under `content` and the
    # real size under `content_length`, and recording the shown length would make the notebook
    # claim a 60,950-character page was 24,000.
    #
    # Without a body: only a handler that DECLARES a size in `chars` is recording a source (the
    # dedupe fact). `content_length` alone means something else — a notebook answer being served
    # back (`cached`), or a page the verdict refused — and neither is a fetch to record.
    declared = _number(result.get("chars"))
    length_field = _number(result.get("content_length"))
    body_text = str(body or "")

    if body_text.strip():
        chars = declared if declared is not None else (length_field or len(body_text))
    elif declared is not None:
        chars = declared
    else:
        return None

    title = ""
    for line in body_text[:300].splitlines():
        if line.strip().lower().startswith("title:"):
            title = line.split(":", 1)[1].strip()
            break

    return {
        "url": url,
        "chars": chars,
        "title": title,
        "excerpt": body_text[:FETCH_EXCERPT_LIMIT],
    }


def capture_fetch(
    workspace_key: str | None,
    goal: str,
    url: str,
    chars: int = 0,
    title: str = "",
    excerpt: str = "",
) -> bool:
    """Record one fetched source in the run's notebook — no agent discipline required.

    The assignment RESUMES per goal, so the same request lands in the same notebook however
    many calls and turns it takes, and a different request opens its own.

    NEVER raises. A capture is bookkeeping: a broken notebook must not be able to turn a fetch
    that worked into a turn that died. It logs and returns False instead.
    """
    if not workspace_key or not str(url or "").strip():
        return False
    try:
        store = AssignmentStore(workspace_key=workspace_key)
        if (goal or "").strip():
            data, _ = store.open(goal)
            assignment_id = data["id"]
        else:
            current = store.current()
            if current is None:
                return False
            assignment_id = current["id"]
        store.note_fetch(
            url, chars=chars, title=title, excerpt=excerpt, assignment_id=assignment_id
        )
        return True
    except Exception:
        logger.warning("notebook: capture failed for %s (the turn carries on)", url, exc_info=True)
        return False


class AssignmentStore:
    """File-backed notebooks for ONE agent workspace.

    Document shape::

        {
          "id": "europe-economic-headline",
          "goal": "Find the leading economic headline for Europe",
          "status": "open",                     # open | closed
          "created_at": "2026-10-13T05:41:00+00:00",
          "updated_at": "2026-10-13T05:52:00+00:00",
          "result": "",                         # the closing line, when closed
          "notes": [
            {"at": "...", "kind": "note",  "source": "reuters.com/...", "title": "...",
             "text": "what was learned"},
            {"at": "...", "kind": "fetch", "source": "https://...", "chars": 15062,
             "excerpt": "the first 500 characters"}
          ]
        }

    Construction: from the `workspace_key` (resolved against `AGENTS_ROOT`) OR an explicit
    directory — the tools receive the agent's own folder as `config["base_path"]` (the execution
    service's `needs_workspace` grant) and pass THAT path, authoritative and never re-resolved.
    """

    def __init__(self, workspace_key: str | None = None, base_dir: str | Path | None = None) -> None:
        if base_dir is not None:
            self.workspace_key = Path(base_dir).name
            self.dir = Path(base_dir) / ASSIGNMENTS_DIRNAME
        elif workspace_key:
            self.workspace_key = workspace_key
            self.dir = assignments_path(workspace_key)
        else:
            raise ValueError("AssignmentStore needs a workspace_key or base_dir")

    # ---- reading ---------------------------------------------------------

    def _path(self, assignment_id: str) -> Path:
        return self.dir / f"{_validate_id(assignment_id)}.json"

    def read(self, assignment_id: str) -> dict:
        path = self._path(assignment_id)
        if not path.exists():
            raise AssignmentNotFound(f"no assignment {assignment_id!r} in {self.dir}")
        try:
            with path.open(encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as e:
            raise AssignmentUnreadable(
                f"assignment {assignment_id!r} is unreadable at {path}: {e} — refusing to treat "
                "it as empty (an empty read would let the next write erase its notes). "
                "Fix or remove the file."
            ) from e
        if not isinstance(data, dict):
            raise AssignmentUnreadable(
                f"assignment {assignment_id!r} at {path} is not a notebook document "
                f"({type(data).__name__}) — refusing to treat it as empty."
            )
        data.setdefault("id", assignment_id)
        data.setdefault("notes", [])
        return data

    def all_assignments(self) -> list[dict]:
        """Every assignment, newest activity first — the folder IS the index.

        A file that cannot be parsed is SKIPPED here (so one broken notebook cannot blank the
        prompt or the listing) and it WARNs, so the breakage is never silent. A write still
        refuses loudly: see `resolve`.
        """
        if not self.dir.exists():
            return []
        found: list[dict] = []
        for path in sorted(self.dir.glob("*.json")):
            try:
                found.append(self.read(path.stem))
            except (AssignmentUnreadable, ValueError) as e:
                logger.warning("assignment %s unreadable — skipped in the listing: %s", path.stem, e)
        found.sort(key=lambda d: (d.get("updated_at") or "", d.get("id") or ""), reverse=True)
        return found

    def unreadable(self) -> list[str]:
        """Ids whose file exists but cannot be parsed (the silent-erasure class)."""
        if not self.dir.exists():
            return []
        broken: list[str] = []
        for path in sorted(self.dir.glob("*.json")):
            try:
                with path.open(encoding="utf-8") as fh:
                    json.load(fh)
            except (json.JSONDecodeError, OSError):
                broken.append(path.stem)
        return broken

    def current(self) -> dict | None:
        """The assignment a bare write goes to — the most recently updated OPEN one.

        Derived, never stored: a pointer file beside the notebooks is one more thing that can
        disagree with them.
        """
        for data in self.all_assignments():
            if data.get("status") == STATUS_OPEN:
                return data
        return None

    def resolve(self, assignment_id: str | None = None) -> dict:
        """The named assignment, else the current one, else a loud refusal.

        A bare write with nothing open does NOT get to report "no assignment" when a notebook
        exists and cannot be read: that would hide a broken file behind a message the agent would
        simply act on (and the write would land somewhere else). The breakage is named instead.
        """
        if assignment_id:
            return self.read(assignment_id)
        current = self.current()
        if current is None:
            broken = self.unreadable()
            if broken:
                raise AssignmentUnreadable(
                    f"your notebook cannot be read ({', '.join(broken)}) — refusing to write "
                    "beside a document that cannot be parsed. Fix or remove the file."
                )
            raise AssignmentNotFound(
                "no open assignment — call open-assignment first (one per piece of work), then "
                "add-note as you gather."
            )
        return current

    # ---- writing ---------------------------------------------------------

    def _write(self, data: dict) -> None:
        data["updated_at"] = _now()
        write_atomic(self._path(data["id"]), json.dumps(data, indent=2), suffix=".tmp")

    def open(self, goal: str, assignment_id: str | None = None) -> tuple[dict, bool]:
        """Open an assignment — or RESUME the one this goal already names.

        Idempotent on purpose: an agent that opens the same piece of work twice must find its
        notebook, not an empty replacement for it. Returns `(document, resumed)`.
        """
        goal = (goal or "").strip()
        if not goal:
            raise ValueError("open-assignment needs a goal — what are you trying to find out?")
        if len(goal) > GOAL_LIMIT:
            # the goal rides the prompt every turn; a pasted document must not
            goal = goal[:GOAL_LIMIT].rstrip() + "…"
        target = _validate_id(assignment_id) if assignment_id else _slug(goal)
        path = self.dir / f"{target}.json"
        with path_lock(path):
            if path.exists():
                return self.read(target), True
            now = _now()
            data = {
                "id": target,
                "goal": goal,
                "status": STATUS_OPEN,
                "created_at": now,
                "updated_at": now,
                "result": "",
                "notes": [],
            }
            # the lock for the write is the same path lock the other writers take
            self._write(data)
            return data, False

    def add_note(
        self,
        text: str,
        assignment_id: str | None = None,
        source: str | None = None,
        title: str | None = None,
    ) -> dict:
        """Append one note. Returns `{entry, count, assignment}` — the VERIFIED read-back."""
        text = (text or "").strip()
        if not text:
            raise ValueError("add-note needs text — what did you learn?")
        truncated = len(text) > NOTE_TEXT_LIMIT
        if truncated:
            text = text[:NOTE_TEXT_LIMIT]
        data = self.resolve(assignment_id)
        path = self._path(data["id"])
        with path_lock(path):
            data = self.read(data["id"])
            entry: dict = {
                "at": _now(),
                "kind": "note",
                "source": (source or "").strip(),
                "title": (title or "").strip(),
                "text": text,
            }
            if truncated:
                entry["truncated_at"] = NOTE_TEXT_LIMIT
            data["notes"].append(entry)
            self._write(data)
            return {"entry": entry, "count": len(data["notes"]), "assignment": data["id"]}

    def note_fetch(
        self,
        url: str,
        chars: int = 0,
        title: str | None = None,
        excerpt: str | None = None,
        assignment_id: str | None = None,
    ) -> dict:
        """Record that a source WAS READ — url, size, a glimpse. Never the payload.

        This is the dedupe record (`sources_seen` reads it) and it is what makes the notebook
        cost a few tokens instead of the page's tens of thousands.
        """
        url = (url or "").strip()
        if not url:
            raise ValueError("note_fetch needs a url")
        data = self.resolve(assignment_id)
        path = self._path(data["id"])
        with path_lock(path):
            data = self.read(data["id"])
            entry = {
                "at": _now(),
                "kind": "fetch",
                "source": url,
                "chars": int(chars or 0),
                "title": (title or "").strip(),
                "excerpt": (excerpt or "").strip()[:FETCH_EXCERPT_LIMIT],
            }
            data["notes"].append(entry)
            self._write(data)
            return {"entry": entry, "count": len(data["notes"]), "assignment": data["id"]}

    def close(self, assignment_id: str | None = None, result: str = "") -> dict:
        """Close the assignment — the piece is written, and `result` is its one-line outcome."""
        data = self.resolve(assignment_id)
        path = self._path(data["id"])
        with path_lock(path):
            data = self.read(data["id"])
            data["status"] = STATUS_CLOSED
            data["result"] = (result or "").strip()
            self._write(data)
            return data

    def reopen(self, assignment_id: str) -> dict:
        path = self._path(assignment_id)
        with path_lock(path):
            data = self.read(assignment_id)
            data["status"] = STATUS_OPEN
            self._write(data)
            return data

    # ---- what the caller reads back --------------------------------------

    def sources_seen(self, assignment_id: str | None = None) -> list[str]:
        """Every URL already fetched under this assignment, de-duplicated, in order."""
        data = self.resolve(assignment_id)
        seen: list[str] = []
        for entry in data.get("notes") or []:
            if entry.get("kind") == "fetch" and entry.get("source") not in seen:
                seen.append(entry["source"])
        return seen

    def fetched_sources(self, assignment_id: str | None = None) -> list[dict]:
        """This assignment's sources, most recently fetched first, each carrying its AGE."""
        return _sources_of(self.resolve(assignment_id))

    def recent_fetch(self, url: str, within_minutes: int = FRESH_FETCH_MINUTES) -> dict | None:
        """The most recent fetch of `url` in this agent's notebooks — if it is inside the window.

        This is the freshness dedupe's lookup: what the tool asks before it pulls a page. It is
        AGENT-scoped rather than assignment-scoped on purpose (the same URL gathered under a
        different piece of work is still a page this agent already has), it returns the notes
        that hold what was learned from it, and it returns None for an OLD fetch — an stale
        record is not a reason to withhold a fresh page.

        The window is a DEFAULT, never a refusal: a caller who needs a new copy says
        `refresh=true` and gets one.
        """
        key = _normalise_url(url)
        if not key:
            return None
        best: dict | None = None
        best_doc: dict | None = None
        for data in self.all_assignments():
            for source in _sources_of(data):
                if source["url"] != key:
                    continue
                if best is None or str(source["at"]) > str(best["at"]):
                    best, best_doc = source, data
        if best is None or best_doc is None:
            return None

        when = _parse_when(best["at"])
        if when is None:
            return None
        minutes = (_dt.datetime.now(_dt.timezone.utc) - when).total_seconds() / 60
        if minutes > max(0, int(within_minutes)):
            return None
        return {
            **best,
            "minutes": int(minutes),
            "assignment": best_doc.get("id", ""),
            "goal": best_doc.get("goal", ""),
            "notes": _prose_of(best_doc),
        }

    def digest(self, assignment_limit: int = 3, note_preview: int = 3) -> str | None:
        """The prompt block: the open notebooks, cheap enough to carry every turn.

        It names the goal, how much is in the notebook, and WHICH sources are already gathered —
        that last line is the whole point: it is what stops a run re-fetching what it has.
        """
        open_ones = [d for d in self.all_assignments() if d.get("status") == STATUS_OPEN]
        if not open_ones:
            return None
        lines = [
            "YOUR ASSIGNMENTS (your notebook — kept in your workspace; the ONE copy):",
        ]
        for data in open_ones[:assignment_limit]:
            notes = data.get("notes") or []
            prose = [n for n in notes if n.get("kind") == "note"]
            gathered = _sources_of(data)
            lines.append(
                f'- [{data["id"]}] "{data.get("goal", "")}" — {len(prose)} note(s), '
                f'{len(gathered)} source(s) fetched'
            )
            for note in prose[-note_preview:]:
                head = (note.get("text") or "").replace("\n", " ")[:120]
                where = note.get("source") or "no source"
                lines.append(f"    · {head} ({where})")
            if gathered:
                # THE AGE IS THE POINT: "already gathered" and "still current" are different
                # claims, and three live runs re-fetched the same three URLs 11 minutes apart
                # because nothing here said when they were taken.
                shown = ", ".join(
                    f'{s["url"]} ({s["age"]})' for s in gathered[:DIGEST_SOURCE_LIMIT]
                )
                more = f" (+{len(gathered) - DIGEST_SOURCE_LIMIT} more)" if len(gathered) > DIGEST_SOURCE_LIMIT else ""
                lines.append(f"    already gathered from: {shown}{more}")
        if len(open_ones) > assignment_limit:
            lines.append(f"  (+{len(open_ones) - assignment_limit} more open assignments)")
        lines.append(
            f"Work from this notebook. A source listed above was fetched when it says it was: "
            f"inside {FRESH_FETCH_MINUTES} minutes a re-fetch is served from the notebook itself "
            "(pass refresh=true only when you need a genuinely new copy), and an older one is "
            "worth re-fetching only if the page changes — say why when you do. Record as you go "
            "with add-note (what you learned + where it came from, so the next turn can write "
            "from the finding rather than from the page); open-assignment names a new piece of "
            "work, read-assignment re-reads the notes before you write, and close-assignment "
            "ends the piece."
        )
        return "\n".join(lines)
