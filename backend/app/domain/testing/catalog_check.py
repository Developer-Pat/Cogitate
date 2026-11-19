"""
The catalog CHECK — every rendered description must be a true, complete sentence.

WHY THIS EXISTS (2026-09-14). A sweep removed dates from 68 test docstrings and then
verified the wrong thing: that each rewrite matched, and that each file still parsed.
Both were true. The PAGE still rendered

    The reasoning-model support - the budget floor. The ox-alpha incident showed a

- truncated mid-sentence, because the catalog takes the docstring's FIRST LINE and the
edit had left two sentences on it. **A check that cannot see the RENDERED output is not
a check of the page.**

A second reason: the same sweep's detector matched ``Phase 2`` but NOT ``Phase B``, so
21 files survived a commit claiming "zero dates or phases". A claim about a SET must be
checked against the set, not against the pattern that was meant to find it.

This module is the LOGIC; ``scripts/testing/check_test_catalog.py`` is the CLI. It lives
here so the sweep and the tests can import it directly, with no path arithmetic - and
because the check is domain knowledge, not a script's business.
"""

from __future__ import annotations

import re
from typing import Any

#: The page renders one line; past this it truncates. Derived from the widest
#: description that still reads whole in the table, not from a round number.
MAX_DESCRIPTION_CHARS = 95

#: A date is project history. Git has it; the description does not need it.
RE_DATE = re.compile(r"\b20\d\d-\d\d-\d\d\b")

#: A phase or step, LETTER OR DIGIT. The letter form is the one that was missed --
#: ``Phase 2`` matches a naive digit pattern, ``ARM Phase B`` does not.
RE_PHASE = re.compile(r"\b(?:Phase|Step)\s*-?\s*[A-Z0-9]\b")

#: A session ordinal. "Session 46" means nothing outside the session logs.
RE_SESSION = re.compile(r"\bSession\s*\d+\b")

#: An incident reference -- real history, wrong surface. ``known-issues.md`` is the
#: one place allowed symptom/root-cause history.
RE_INCIDENT = re.compile(r"\bINCIDENT\b", re.IGNORECASE)

#: Arc codenames. **This list needs upkeep** -- it is why the first pass missed 25
#: files. Kept explicit rather than pattern-guessed: a loose regex would flag real
#: words (``ARM`` alone, ``the sort``), and a flag nobody trusts gets ignored, which
#: is worse than no check. Add to it when a new codename reaches a docstring.
CODENAMES: tuple[str, ...] = (
    "the akeys roadmap",
    "the agent-kits build",
    "the agent-lifecycle",
    "the yellow pages",
    "the white pages",
    "the yolo button",
    "the payoff",
    "the fork boundary",
    "exa-expertise program",
    "the ox-arc",
    "the ox arc",
    "option-a",
)

#: ``the _26 build``, ``the _35 build P2`` -- a build label keyed to a session number.
RE_BUILD_LABEL = re.compile(r"\b_\d{2}\b\s*(?:build|f\d)", re.IGNORECASE)

#: The ``Tests for X`` shape. It is TRUE and it says nothing ABOUT THE TESTS: the file
#: name already said X. Measured 2026-09-14: 41 of 173 descriptions opened this way,
#: and 31 of those named nothing specific - which is why the page read as
#: uninformative even after every date and codename had been removed.
RE_BOILERPLATE = re.compile(r"^(?:unit\s+|integration\s+)?tests?\s+for\s+(.+)$", re.IGNORECASE)

def restates_the_filename(description: str) -> bool:
    """True when a ``Tests for X`` description describes the MODULE, not the tests.

    THE RULE, and why it is this and not something cleverer. Measured across the
    catalog: 41 descriptions open ``Tests for X``. Ten of them NAME SOMETHING - a
    parenthetical, a symbol (``extract_facts``, ``check_agent_health.py``) - and a
    reader learns from those. The other 31 carry no such detail, so all they say is
    which module the file is, which the file name already said.

    An earlier version compared the description's words against the file name's,
    word by word, with crude stemming to make "compaction" match "compactor". It
    worked and it was the wrong instrument: it flagged 6, because most of the 31 do
    add SOME word ("agent", "reset", "generic"). They add words and still say nothing
    useful, which is the actual defect. The test that matches the intent is whether
    the description names anything SPECIFIC.
    """
    text = description.strip()
    m = RE_BOILERPLATE.match(text)
    if not m:
        return False
    return not ("(" in text or "`" in text or "_" in m.group(1))


def _first_line(description: str) -> str:
    """The one line the page renders. The catalog already trims to it; keeping the
    helper makes that contract explicit at the point of use."""
    return description.strip()


def _match(pattern: "re.Pattern[str]", text: str) -> str | None:
    """The first match's text, or None. Searched ONCE - re-calling .search() to
    fetch .group() after a truthiness check is the same work twice and reads as
    a bug even when it is not."""
    found = pattern.search(text)
    return found.group(0) if found else None


def check_description(path: str, description: str) -> list[dict[str, str]]:
    """Every defect in ONE rendered description. Pure - no I/O, so it is testable."""
    findings: list[dict[str, str]] = []
    text = _first_line(description)

    def flag(cls: str, detail: str) -> None:
        findings.append({"path": path, "class": cls, "detail": detail, "text": text[:120]})

    if not text:
        flag("MISSING", "no docstring - the page renders a blank description")
        return findings

    for cls, pattern in (
        ("DATE", RE_DATE), ("PHASE", RE_PHASE), ("SESSION", RE_SESSION),
        ("INCIDENT", RE_INCIDENT), ("CODENAME", RE_BUILD_LABEL),
    ):
        hit = _match(pattern, text)
        if hit:
            flag(cls, hit)
    lowered = text.lower()
    for code in CODENAMES:
        if code in lowered:
            flag("CODENAME", code)

    # A sentence boundary followed by a capital INSIDE the rendered line: the page
    # shows the first line only, so the second sentence is cut off mid-thought.
    if re.search(r"\.\s+[A-Z]", text):
        flag("TWO_SENTENCES", "the rendered line holds two sentences")

    # A description that does not end a sentence is truncated, whatever the cause.
    if not text.rstrip().endswith((".", "!", "?", "`", ")")):
        flag("NO_TERMINATOR", "the description ends mid-thought")

    if len(text) > MAX_DESCRIPTION_CHARS:
        flag("TOO_LONG", f"{len(text)} chars > {MAX_DESCRIPTION_CHARS}")

    # Vagueness, not falsity: the description is true and says nothing. Measured at
    # 22% of the catalog, so it is reported - but it is a QUALITY finding, not a
    # defect, and the CLI keeps it out of the exit code (see --strict).
    if restates_the_filename(text):
        flag("BOILERPLATE", "restates the file name and adds nothing")

    return findings


def check_catalog(catalog: dict[str, Any]) -> list[dict[str, str]]:
    """Every defect across a built catalog. Pure on the catalog dict."""
    findings: list[dict[str, str]] = []
    for entry in catalog.get("tests", []):
        findings.extend(
            check_description(entry.get("path", "?"), entry.get("description", ""))
        )
    return findings
