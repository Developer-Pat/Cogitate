"""The agent's own beat sheets — the co-authored news beats.

A beat sheet is a markdown file in the agent's workspace
(`agents/<key>/news-beats/<name>.md`). It carries the purpose, the
interests (the Subjects / People / Places lists), and the sources with
`name (description, language)`.

The sheets are the WORKING MODEL the user and the agent build together:
the user says "add so-and-so to the people list" or "drop economics from
the subjects" and the agent edits the sheet on the spot. This store is
what the `update-beat` tool writes through — the sheets stay markdown
(hand-authored, git-visible, readable by a human), so the editing is
surgical rather than a serialization round-trip.

Shape of a sheet:

    # Beat Sheet — Middle East, Vox Populi

    lens: Vox Populi
    languages: ar, fa, he, tr
    updated: 2026-09-09

    ## Purpose
    ...prose...

    ## Interests

    Priorities, not limits — the reporter's judgment decides what goes in.

    - Subjects: the war (Iran/Israel, both sides' press), regional politics
    - People: the region's leaders as they surface in the news
    - Places: the Middle East — Iran, Israel/Palestine, the Gulf

    ## Sources

    - Al Jazeera (pan-Arab, Arabic) — https://www.aljazeera.net

Two details matter for a correct edit:

- Items are comma-separated at the TOP level only. Parenthesised
  commentary carries its own commas ("the war (Iran/Israel, both
  sides' press)") and must not be split, so the splitter tracks
  paren depth. Long entries wrap across lines; a continuation is
  joined back before parsing.
- A remove is an EXACT match on the item text (case/whitespace
  normalised). No fuzzy matching: silently removing the wrong item
  from the user's beat is worse than saying "no such item".
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from app.core.path_lock import path_lock, write_atomic

BEATS_DIRNAME = "news-beats"
INTERESTS_SECTION = "Interests"
SOURCES_SECTION = "Sources"

#: The interest lists a beat can carry (case-insensitive on match).
INTEREST_LISTS = ("subjects", "people", "places")

_WRAP_COLS = 72


def _split_items(text: str) -> list[str]:
    """Split a comma-separated item string, respecting parentheses."""
    items: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            items.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        items.append(tail)
    return [i for i in items if i]


def _parse_interest_entries(section_lines: list[str]) -> dict[str, list[str]]:
    """Parse the `- Label: a, b, c` entries of an ## Interests section.

    Wrapped entries are joined back BEFORE splitting (a long item runs
    onto continuation lines), and the split itself respects
    parenthesised commas. Both the read and the edit go through here —
    one parser, so a round-trip cannot drift.
    """
    out: dict[str, list[str]] = {}
    label: str | None = None
    buf: list[str] = []

    def flush() -> None:
        if label is not None:
            out[label.lower()] = _split_items(" ".join(buf))

    for line in section_lines:
        m = re.match(r"^-\s*([A-Za-z ]+?):\s*(.*)$", line)
        if m and m.group(1).strip().lower() in INTEREST_LISTS:
            flush()
            label, buf = m.group(1).strip(), [m.group(2).strip()]
            continue
        if label is not None:
            stripped = line.strip()
            if not stripped or line.startswith("- ") or line.startswith("## ") or stripped.startswith("Notes"):
                flush()
                label, buf = None, []
            else:
                buf.append(stripped)
    flush()
    return out


def _join_items(items: list[str], prefix: str) -> list[str]:
    """Render `- prefix: a, b, c` wrapped to a readable width."""
    out: list[str] = []
    cur = f"- {prefix}: " if prefix else "- "
    for n, item in enumerate(items):
        piece = item if n == 0 else f", {item}"
        if len(cur) + len(piece) > _WRAP_COLS and cur.strip() not in ("-", "- "):
            # the comma stays with the line it separates, so joining the
            # continuation back reproduces the exact item list
            out.append(cur.rstrip() + ",")
            cur = "  " + item
        else:
            cur += piece
    out.append(cur.rstrip())
    return out


class AgentBeatStore:
    """File-backed beat sheets for ONE agent workspace.

    Construction mirrors AgentStateStore: from the workspace_key OR an
    explicit base_dir (the tools get the agent's own folder injected as
    config["base_path"] and pass THAT path — authoritative, never
    re-resolved).

    Thread-safe per instance: the read-modify-write is lock-guarded and
    the file is replaced atomically (temp + rename), so a concurrent
    call can never see a half-written sheet.
    """

    def __init__(self, workspace_key: str | None = None, base_dir: str | Path | None = None) -> None:
        # the sibling's helper (call-time import: the tests monkeypatch
        # workspace.AGENTS_ROOT, so a module-level bind would miss it)
        from app.domain.agents.agent_state import workspace_path

        if base_dir is not None:
            self.workspace_key = Path(base_dir).name
            self.root = Path(base_dir) / BEATS_DIRNAME
        elif workspace_key:
            self.workspace_key = workspace_key
            self.root = workspace_path(workspace_key) / BEATS_DIRNAME
        else:
            raise ValueError("AgentBeatStore needs a workspace_key or base_dir")
        self._lock = path_lock(self.root)

    # ---- reading ------------------------------------------------------

    def list_beats(self) -> list[str]:
        """The beat sheet stems available in this workspace."""
        if not self.root.is_dir():
            return []
        return sorted(p.stem for p in self.root.glob("*.md"))

    def resolve(self, beat: str | None) -> Path:
        """Find the sheet named by `beat` (stem or filename).

        With no name: the only sheet, or a loud error naming the
        choices — never a silent pick when several exist.
        """
        beats = self.list_beats()
        if not beats:
            raise ValueError(
                "This agent has no beat sheet yet (no files in "
                "news-beats/). Create one before editing it."
            )
        if not beat:
            if len(beats) == 1:
                return self.root / f"{beats[0]}.md"
            raise ValueError(
                f"Several beat sheets exist ({', '.join(beats)}) — say which one."
            )
        wanted = Path(str(beat)).stem.lower()
        for stem in beats:
            if stem.lower() == wanted:
                return self.root / f"{stem}.md"
        raise ValueError(f"No beat sheet named {beat!r}. Available: {', '.join(beats)}")

    def read(self, beat: str | None = None) -> dict:
        """Parse a sheet into {name, path, meta, purpose, lists, sources}."""
        path = self.resolve(beat)
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        meta: dict[str, str] = {}
        for line in lines[:12]:
            m = re.match(r"^([a-z_]+):\s*(.+)$", line.strip(), re.IGNORECASE)
            if m:
                meta[m.group(1).lower()] = m.group(2).strip()

        sections: dict[str, list[str]] = {}
        current: str | None = None
        for line in lines:
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                name = heading.group(1).strip()
                current = name
                sections.setdefault(name, [])
                continue
            if current is not None:
                sections[current].append(line)

        lists = _parse_interest_entries(sections.get(INTERESTS_SECTION, []))

        sources: list[str] = []
        for line in sections.get(SOURCES_SECTION, []):
            s = line.strip()
            if s.startswith("- "):
                sources.append(s[2:].strip())

        purpose = "\n".join(sections.get("Purpose", [])).strip()
        return {
            "name": path.stem,
            "path": str(path),
            "meta": meta,
            "purpose": purpose,
            "lists": lists,
            "sources": sources,
        }

    # ---- writing ------------------------------------------------------

    def add_items(self, beat: str | None, list_name: str, items: list[str]) -> dict:
        return self._edit(beat, list_name, items, remove=False)

    def remove_items(self, beat: str | None, list_name: str, items: list[str]) -> dict:
        return self._edit(beat, list_name, items, remove=True)

    def _edit(self, beat: str | None, list_name: str, items: list[str], remove: bool) -> dict:
        key = (list_name or "").strip().lower()
        if key not in INTEREST_LISTS and key != "sources":
            raise ValueError(
                f"Unknown list {list_name!r}. Choose one of: "
                f"{', '.join(INTEREST_LISTS + ('sources',))}."
            )
        clean = [str(i).strip() for i in items if str(i).strip()]
        if not clean:
            raise ValueError("No items given.")

        with self._lock:
            path = self.resolve(beat)
            original = path.read_text(encoding="utf-8")
            lines = original.splitlines()

            if key == "sources":
                new_lines, result = self._edit_sources(lines, clean, remove)
            else:
                new_lines, result = self._edit_interest(lines, key, clean, remove)

            # the updated: stamp (the sheet says when it last changed)
            today = date.today().isoformat()
            for i, line in enumerate(new_lines[:12]):
                if re.match(r"^updated:\s*", line.strip(), re.IGNORECASE):
                    new_lines[i] = f"updated: {today}"
                    break

            body = "\n".join(new_lines)
            if not body.endswith("\n"):
                body += "\n"
            # the same shared-temp defect the state store had: a FIXED
            # temp name meant two writers collided on it (2026-09-11)
            write_atomic(path, body, suffix=".tmp")

        return {
            "beat": path.stem,
            "list": key,
            "action": "remove" if remove else "add",
            **result,
        }

    # -- the two edits --------------------------------------------------

    def _edit_interest(self, lines: list[str], key: str, items: list[str], remove: bool) -> tuple[list[str], dict]:
        """Edit a `- Subjects: a, b, c` line under ## Interests."""
        in_interests = False
        for i, line in enumerate(lines):
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                in_interests = heading.group(1).strip() == INTERESTS_SECTION
                continue
            if not in_interests:
                continue
            m = re.match(r"^-\s*([A-Za-z ]+?):\s*(.*)$", line)
            if not m or m.group(1).strip().lower() != key:
                continue

            # gather the wrapped continuation lines that belong to this entry
            start = i
            end = i + 1
            while end < len(lines):
                nxt = lines[end]
                if not nxt.strip() or nxt.startswith("- ") or nxt.startswith("## ") or nxt.startswith("Notes"):
                    break
                end += 1
            current = _parse_interest_entries(lines[start:end]).get(key, [])

            if remove:
                lowered = {c.lower() for c in current}
                missing = [it for it in items if it.lower() not in lowered]
                if missing:
                    raise ValueError(
                        f"Not in the {key} list: {', '.join(missing)}. "
                        f"Current: {', '.join(current) or '(empty)'}"
                    )
                want = {it.lower() for it in items}
                updated = [c for c in current if c.lower() not in want]
            else:
                updated = current + [it for it in items if it.lower() not in {c.lower() for c in current}]

            label = m.group(1).strip()
            rendered = _join_items(updated, label) if updated else [f"- {label}:"]
            return lines[:start] + rendered + lines[end:], {
                "items": updated,
                "verified": updated,
            }

        # no such line: on add, create it at the end of the Interests section
        if remove:
            raise ValueError(
                f"The {key} list does not exist in this sheet "
                f"(no '- {key.title()}:' line) — nothing to remove."
            )
        return self._append_interest(lines, key, items)

    def _append_interest(self, lines: list[str], key: str, items: list[str]) -> tuple[list[str], dict]:
        """Create a missing interest line at the end of ## Interests."""
        in_interests = False
        insert_at: int | None = None
        for i, line in enumerate(lines):
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                if in_interests:
                    insert_at = i
                    break
                in_interests = heading.group(1).strip() == INTERESTS_SECTION
                continue
            if in_interests and line.strip():
                insert_at = i + 1
        if insert_at is None:
            raise ValueError(
                "This sheet has no ## Interests section — add one before "
                "listing subjects, people or places."
            )
        label = key.title()
        rendered = _join_items(items, label)
        return lines[:insert_at] + [""] + rendered + lines[insert_at:], {
            "items": items,
            "verified": items,
        }

    def _edit_sources(self, lines: list[str], items: list[str], remove: bool) -> tuple[list[str], dict]:
        """Edit the `- <source>` bullets under ## Sources."""
        in_sources = False
        start: int | None = None
        end: int | None = None
        for i, line in enumerate(lines):
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                if in_sources:
                    end = i
                    break
                in_sources = heading.group(1).strip().startswith(SOURCES_SECTION)
                continue
            if in_sources and start is None and line.strip().startswith("- "):
                start = i
        if start is None:
            raise ValueError(
                "This sheet has no ## Sources bullets — add a section first."
            )
        if end is None:
            end = len(lines)

        block = [l for l in lines[start:end] if l.strip().startswith("- ")]
        current = [l.strip()[2:].strip() for l in block]

        if remove:
            lowered = {c.lower() for c in current}
            missing = [it for it in items if it.lower() not in lowered]
            if missing:
                raise ValueError(
                    f"Not in the sources list: {', '.join(missing)}. "
                    f"Current: {len(current)} sources."
                )
            want = {it.lower() for it in items}
            updated = [c for c in current if c.lower() not in want]
        else:
            updated = current + [it for it in items if it.lower() not in {c.lower() for c in current}]

        rendered = [f"- {s}" for s in updated]
        return lines[:start] + rendered + lines[end:], {
            "sources": updated,
            "count": len(updated),
            "verified": updated,
        }
