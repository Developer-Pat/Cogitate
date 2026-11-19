#!/usr/bin/env python3
"""THE BENCH — the driver: issue each job through the app's own endpoint, collect, judge.

Run it from the PROJECT ROOT (the paths below are cwd-relative: the app's `.env`, its log and
its database are all resolved from where the app runs, and the app runs from here).

    python3 scripts/bench/run_bench.py --list                 # the jobs, budgets and checks
    python3 scripts/bench/run_bench.py --check-fixtures       # do the needles still exist at the sources?
    python3 scripts/bench/run_bench.py --run                  # says what it WOULD spend, and stops
    python3 scripts/bench/run_bench.py --run --go             # spends it: ~2-3 paid calls per job
    python3 scripts/bench/run_bench.py --run --go --diff data/bench/baseline.json

**This is not a pytest test.** It is neither deterministic nor free. It never runs as part of
the suite; it is opt-in, it announces its cost, and `--go` is the user's consent to spend.

**The job fixture** (`scripts/bench/jobs/*.json`) — the charter's five things:

    id · why                                the job and what it prices
    axis                                    the census dimension it covers (size, kind, ...)
    agent                                   which real agent runs it (resolved by name)
    state.assignment                        "fresh": the notebook this job's own goal maps to
                                            is moved aside first (matched by the goal the app
                                            derived from the same message, so the agent's real
                                            work is never touched) — and if the run resumes a
                                            filled one anyway, the row says so rather than
                                            passing a contaminated state off as a fresh one
    message                                 the turn as the user would send it
    budget                                  the ceilings: tokens_in, provider_calls,
                                            fetched_chars, capped_chars — set generously above
                                            the first baseline run, because they are ALARMS
                                            (the job's shape changed), not fine gates (the
                                            per-job delta against the baseline reads drift)
    check                                   the mechanical pass: type, needles, min_answer_chars

**What the checks are, and are not.** A needle is a fact only the job's own sources carry (a
county, a founding year), so an answer built from the model's memory instead of reading fails;
a five-needle check reads as coverage. There is no answer key and no judge — no second model's
opinion anywhere. `min_answer_chars` is a SHAPE gate, not a judge: without it a run that
answered a report's prompt like a scan would pass the facts and make depth look free.

**Where each number comes from — the grounding this driver is built on.** Read off a real turn
(session 224) rather than assumed:

  per TURN   `🧮 TURN ACCOUNT`  — provider_calls, tools_offered, tool_calls, tool_calls_blocked,
                                 tool_failures, tokens_in (provider-reported, summed),
                                 tokens_out, elapsed_s, tokens=reported|estimated
  per CALL   `📐 PROMPT ACCOUNT` — the prompt's composition by contributor, the ceiling in force
                                 and the soft: the app's OWN ESTIMATE, deliberately kept beside
                                 the reported number rather than instead of it
             `📊 STREAM COMPLETED` — the usage THIS call reported (prompt_tokens,
                                 completion_tokens), chunks, chars, stream ms, finish_reason
             `📡 LLM REQUEST START` — messages_count, tools_count
             `💰 EFFECTIVE OUTPUT BUDGET` — max_tokens_sent, reason, declared
  tools      `🔧 TOOL CALL START` · `✅ TOOL EXECUTION SUCCESS` (execution_time_ms)
  fetches    `Jina Reader: fetched '<url>' (N chars`
  the answer the SSE stream itself

**Two sources the driver refuses, with the measurements that condemn them:**

* **`usage_logs`** — one row per turn, but carrying ONE call's prompt tokens: session 224's row
  says 3,371 against the turn's real 86,568, and session 213's single-call turns match exactly
  while its multi-call turns are off by up to 40x (4,998 against 380,561). Off by an order of
  magnitude with nothing to say so.
* **`data/pipeline_traces.db`** — per STAGE, not per call, and its `input_tokens` reads 0.

**One caveat this driver enforces rather than assumes:** a provider that reports no usage leaves
the per-call numbers at `None`. `None` is not zero, and a job whose calls all read `None` is
reported as an unmeasured prompt rather than a cheap one.

**The log is a moving target.** The app rotates `app.log` at ~10 MB, so the driver records the
file's size before a job and refuses to read a block that shrank (a rotation mid-run): a turn
whose lines are split across a rotated file is reported as uncollectable, never guessed at.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_LOG = "backend/logs/app.log"
DEFAULT_JOBS = "scripts/bench/jobs"
DEFAULT_RUNS = "data/bench"

# ---------------------------------------------------------------------------
# The log's own grammar. ONE regex per line the app writes, copied from the
# app's format strings — and every one of them is a contract: a line whose
# shape changes makes its field read None, which the row says out loud.
# ---------------------------------------------------------------------------

TURN_ACCOUNT = re.compile(
    r"TURN ACCOUNT session=(\d+) model=(\S+) provider=(\S+) provider_calls=(\d+) paths=(\S+) "
    r"tools_offered=(\d+) tool_calls=(\d+) tool_calls_blocked=(\d+) tool_failures=(\d+) "
    r"tokens_in=(\d+) tokens_out=(\d+) tokens=(\S+) elapsed_s=([\d.]+)"
)
PROMPT_ACCOUNT = re.compile(
    r"PROMPT ACCOUNT ([\d,]+) measured · system ([\d,]+) · history ([\d,]+) · tool results ([\d,]+) "
    r"· tool schemas ([\d,]+) · replayed reasoning ([\d,]+) · the trim counts ([\d,]+) of it "
    r"\(content alone\) · ceiling ([\d,]+)(?: · soft ([\d,]+))?"
)
REQUEST_START = re.compile(
    r"LLM REQUEST START .*session_id=(\d+) .*messages_count=(\d+) .*tools_count=(\d+)"
)
STREAM_OPENED = re.compile(r"STREAM OPENED .*session_id=(\d+)")
FIRST_CHUNK = re.compile(r"FIRST CHUNK RECEIVED .*session_id=(\d+) time_to_first_chunk_ms=([\d.]+)")
STREAM_COMPLETED = re.compile(
    r"STREAM COMPLETED .*chunk_count=(\d+) accumulated_chars=(\d+) has_tool_calls=(\w+) "
    r"tool_calls_count=(\d+) invalid_chunks=(\d+) total_stream_time_ms=([\d.]+) "
    r".*finish_reason=(\S+) truncated=(\w+)"
    # The usage suffix is OPTIONAL on purpose: it landed after this log's older lines were
    # written, so a block from before it reads `None` — "not reported" — rather than failing to
    # parse at all. Absent and unreported are the same thing here, and both mean "not zero".
    r"(?: prompt_tokens=(\S+) completion_tokens=(\S+))?"
)
OUTPUT_BUDGET = re.compile(
    r"EFFECTIVE OUTPUT BUDGET max_tokens_sent=(\d+) reason=(\S+) declared=(\d+) path=(\S+)"
)
FETCH = re.compile(r"Jina Reader: fetched '([^']*)' \((\d+) chars")
CAPPED = re.compile(r"Jina Reader: capped '([^']*)' to (\d+) of (\d+) characters")
# The TOOL RESULT is the fetch that always shows: a url served from the fresh-fetch window logs no
# `fetched` line at all (measured: a run whose five Jina calls all succeeded and recorded none), so
# counting from the handler's line alone under-reports — by five fetches in that run.
FETCH_RESULT = re.compile(
    r"tool_name=Jina Reader .*result_preview=\{'success': (True|False), 'url': '([^']*)'"
)
TOOL_FAILURE = re.compile(r"TOOL EXECUTION FAILED .*tool_name=(\S+) .*error=(.*?) error_type=(\S+)")
TOOL_CALL = re.compile(r"TOOL CALL START .*tool_name=(\S+)")
SESSION_LINE = re.compile(r"session_id=(\d+)")
TIMESTAMP = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")


def _int(text: str) -> int:
    return int(text.replace(",", ""))


def _usage(text: Optional[str]) -> Optional[int]:
    """A reported token count, or None when nobody reported one. `None` is not zero."""
    if text is None or text in ("None", "-", ""):
        return None
    return _int(text)


def _parse_stamp(value: Any) -> Optional[_dt.datetime]:
    """A stored ISO timestamp as an aware datetime, or None when it cannot be read."""
    text = str(value or "")
    if not text:
        return None
    try:
        stamp = _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return stamp if stamp.tzinfo else stamp.replace(tzinfo=_dt.timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class Job:
    path: Path
    data: Dict[str, Any]

    @property
    def job_id(self) -> str:
        return str(self.data["id"])

    @property
    def agent(self) -> str:
        return str(self.data["agent"])

    def summary(self) -> str:
        axis = self.data.get("axis", {})
        budget = self.data.get("budget", {})
        check = self.data.get("check", {})
        return (
            f"{self.job_id:<20} size={axis.get('size', '?'):<3} kind={axis.get('kind', '?'):<7} "
            f"rounds<={budget.get('rounds', '?'):<3} schemas<={budget.get('schemas_max', '?'):<6} "
            f"cap/fetch<={budget.get('capped_chars_per_fetch', '?'):<6} "
            f"needles={len(check.get('needles', []))}"
        )


def load_jobs(jobs_dir: str) -> List[Job]:
    directory = Path(jobs_dir)
    if not directory.is_dir():
        raise SystemExit(f"no jobs directory at {directory} (run from the project root)")
    jobs = [Job(path=p, data=json.loads(p.read_text())) for p in sorted(directory.glob("*.json"))]
    if not jobs:
        raise SystemExit(f"no job fixtures in {directory}")
    seen = set()
    for job in jobs:
        if job.job_id in seen:
            raise SystemExit(f"duplicate job id: {job.job_id}")
        seen.add(job.job_id)
        for key in ("id", "why", "axis", "agent", "state", "message", "budget", "check"):
            if key not in job.data:
                raise SystemExit(f"{job.path.name}: missing '{key}'")
        if job.data["check"].get("type") != "contains_all":
            raise SystemExit(f"{job.path.name}: unknown check type {job.data['check'].get('type')!r}")
    return jobs


def sources_of(job: Job) -> List[str]:
    """The job's own sources — the URLs its message names."""
    return re.findall(r"https?://\S+", job.data["message"])


# ---------------------------------------------------------------------------
# The app: the agent, the endpoint, the state the job starts from
# ---------------------------------------------------------------------------


def resolve_agent(base_url: str, name: str) -> Dict[str, Any]:
    with urllib.request.urlopen(f"{base_url}/api/v1/agents", timeout=20) as response:
        agents = json.load(response).get("agents", [])
    for agent in agents:
        if str(agent.get("name", "")).lower() == name.lower():
            return agent
    raise SystemExit(f"no live agent named {name!r} (the app has: {[a.get('name') for a in agents]})")


def notebooks_dir(project_root: Path, workspace_key: str) -> Path:
    return project_root / "agents" / workspace_key / "assignments"


def read_notebook(path: Path) -> Dict[str, Any]:
    """A notebook's own record: the goal it was opened for, its status, and what it captured."""
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    notes = data.get("notes") or []
    return {
        "slug": path.stem,
        "goal": str(data.get("goal") or ""),
        "status": data.get("status"),
        "created_at": str(data.get("created_at") or ""),
        "notes": len(notes),
        "fetches_recorded": sum(
            1 for note in notes if isinstance(note, dict) and note.get("kind") == "fetch"
        ),
    }


MATCH_PREFIX = 60
"""How many characters of the goal and the message must agree when the goal is not a clean prefix.

The app keeps a turn's goal as the message TRUNCATED — and, measured on the bench's own fixtures,
NOT always a literal prefix: at ~300 characters a long URL is abbreviated inside the goal
(`…ebraska http…` against the message's full `https://en.wikipedia.org/…`), so a startswith test
fails for exactly the jobs with all their sources spelled out. The opening of both strings is
immune to that: still job-specific, well inside any truncation.
"""


def _same_job(goal: str, message: str) -> Tuple[bool, str]:
    """Is this notebook THIS job's? Returns (matched, which rule decided).

    Two rules, in order: a clean prefix either way (a short message, or a goal the app kept whole),
    then the opening 60 characters of both. A goal too short to compare under either rule matches
    nothing — silence is the safe answer when the only alternative is clearing somebody's work.
    """
    goal_n = " ".join(str(goal or "").split())
    message_n = " ".join(str(message or "").split())
    if not goal_n or not message_n:
        return False, "no goal to compare"
    if message_n.startswith(goal_n) or goal_n.startswith(message_n):
        return True, "the goal is a clean prefix of the message"
    window = min(len(goal_n), len(message_n), MATCH_PREFIX)
    if window >= 30 and goal_n[:window] == message_n[:window]:
        return True, f"the first {window} characters agree"
    return False, "neither rule matched"


def previous_run_notebooks(runs_dir: Path, job_id: str) -> List[str]:
    """The notebooks a PREVIOUS bench run of this same job touched — the bench's own residue.

    An agent that opens its own notebook chooses its own goal (`scan-five-nebraska-cities-county-
    and-founding-year`), which the message cannot attribute — so that notebook is matched the only
    honest way available: it is one the bench's own earlier row recorded touching. Nothing else is
    ever a candidate, and no notebook the bench never wrote is touched.
    """
    directory = Path(runs_dir)
    if not directory.is_dir():
        return []
    runs = sorted(
        (p for p in directory.glob("*") if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for run in runs:
        rows_file = run / "rows.json"
        if not rows_file.exists():
            continue
        try:
            rows = json.loads(rows_file.read_text()).get("rows") or []
        except (OSError, ValueError):
            continue
        for row in rows:
            if row.get("job") != job_id:
                continue
            slugs = [
                str(t.get("slug"))
                for t in ((row.get("notebooks") or {}).get("touched") or [])
                if t.get("slug")
            ]
            return slugs
    return []


def clear_job_notebooks(project_root: Path, workspace_key: str, message: str, run_dir: Path,
                        also_slugs: Sequence[str] = ()) -> List[Dict[str, str]]:
    """A fresh notebook: move THIS job's own notebooks aside — never the agent's real work.

    Two doors, because the app writes notebooks through two of them: its AUTOMATIC fetch capture
    opens one for the turn's goal whether or not any tool was called, and an agent that calls
    `open-assignment` names its OWN goal. The first is matched by the goal the app derived from
    the same message; the second by what a previous bench run of this same job recorded touching.

    Everything moved goes to the run's own `pre-state/` (move, never delete), and each entry says
    which rule matched it.
    """
    moved: List[Dict[str, str]] = []
    kept = run_dir / "pre-state"
    directory = notebooks_dir(project_root, workspace_key)
    for path in sorted(directory.glob("*.json")):
        state = read_notebook(path)
        matched, basis = _same_job(state.get("goal", ""), message)
        if not matched and path.stem in set(also_slugs):
            matched, basis = True, "a previous bench run of this job touched it"
        if not matched:
            continue
        kept.mkdir(parents=True, exist_ok=True)
        path.replace(kept / path.name)
        moved.append({"slug": path.stem, "matched_by": basis})
    return moved


def issue_turn(base_url: str, agent_id: int, message: str, timeout: int = 600) -> Dict[str, Any]:
    """POST one turn to the app's own chat endpoint and read its SSE stream."""
    payload = json.dumps({"agent_id": agent_id, "message": message}).encode()
    request = urllib.request.Request(
        f"{base_url}/api/v1/chat/stream",
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    answer_parts: List[str] = []
    done: Optional[Dict[str, Any]] = None
    session_id: Optional[int] = None
    tool_results = 0
    errors: List[str] = []
    started = time.time()

    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            line = raw.decode("utf-8", "ignore").rstrip("\n")
            if not line.startswith("data: "):
                continue
            body = line[6:]
            if body.strip() == "[DONE]":
                continue
            try:
                frame = json.loads(body)
            except ValueError:
                continue
            if "session_id" in frame and "done" not in frame:
                session_id = frame.get("session_id") or session_id
            if frame.get("done"):
                done = frame
                continue
            if frame.get("error"):
                errors.append(str(frame["error"]))
            if frame.get("tool_result"):
                tool_results += 1
            choices = frame.get("choices") or []
            for choice in choices:
                piece = (choice.get("delta") or {}).get("content")
                if piece:
                    answer_parts.append(piece)
            if frame.get("content"):
                answer_parts.append(str(frame["content"]))

    if done and done.get("session_id"):
        session_id = done["session_id"]
    return {
        "answer": "".join(answer_parts),
        "session_id": session_id,
        "done": done,
        "tool_results": tool_results,
        "errors": errors,
        "wall_clock_s": round(time.time() - started, 1),
    }


# ---------------------------------------------------------------------------
# The log: the per-turn and per-call record
# ---------------------------------------------------------------------------


@dataclass
class LogBlock:
    """The lines a turn left in the log, and what they say."""

    lines: List[str] = field(default_factory=list)
    turn: Optional[Dict[str, Any]] = None
    calls: List[Dict[str, Any]] = field(default_factory=list)
    fetches: List[Dict[str, Any]] = field(default_factory=list)
    fetch_results: List[Dict[str, Any]] = field(default_factory=list)
    tool_names: List[str] = field(default_factory=list)
    tool_failures: List[Dict[str, Any]] = field(default_factory=list)
    capped: Dict[str, int] = field(default_factory=dict)
    foreign_sessions: List[int] = field(default_factory=list)


def read_block(log_path: Path, offset: int, session_id: int, timeout_s: float = 30.0) -> LogBlock:
    """Read the turn's block out of the log, waiting for the turn account to be written.

    The account line is written when the turn ENDS — after the last frame the client sees — so a
    driver that read the file the moment the stream closed would find the block half-written.
    """
    deadline = time.time() + timeout_s
    block = LogBlock()
    while True:
        size = log_path.stat().st_size
        if size < offset:
            raise SystemExit(
                f"the log rotated under this run ({log_path} is now smaller than the offset "
                f"taken before it) — the turn's lines are split, so they cannot be collected"
            )
        with log_path.open(errors="ignore") as handle:
            handle.seek(offset)
            block.lines = handle.read().splitlines()
        for line in block.lines:
            if (m := TURN_ACCOUNT.search(line)) and int(m.group(1)) == session_id:
                block.turn = {
                    "session_id": int(m.group(1)), "model": m.group(2), "provider": m.group(3),
                    "provider_calls": int(m.group(4)), "paths": m.group(5),
                    "tools_offered": int(m.group(6)), "tool_calls": int(m.group(7)),
                    "tool_calls_blocked": int(m.group(8)), "tool_failures": int(m.group(9)),
                    "tokens_in": int(m.group(10)), "tokens_out": int(m.group(11)),
                    "tokens_source": m.group(12), "elapsed_s": float(m.group(13)),
                }
                break
        if block.turn or time.time() >= deadline:
            break
        time.sleep(1.0)
    return block


def parse_block(block: LogBlock, session_id: int) -> LogBlock:
    """The per-call record inside a turn's block, in the order the calls were made.

    **The spine is the STREAM, not the request.** `LLM REQUEST START` is logged ONCE per turn
    (measured on session 224: one request line, four streams), so grouping by it would collapse
    four calls into one. `LLM STREAM OPENED` / `LLM FIRST CHUNK` / `LLM STREAM COMPLETED` are the
    lines that repeat per call, and the prompt account precedes its stream — so a record opens on
    either the account or the stream and closes on the completed line.
    """
    current: Optional[Dict[str, Any]] = None

    def open_call() -> Dict[str, Any]:
        nonlocal current
        current = {
            "messages_count": None, "tools_count": None, "account": None,
            "output_budget": None, "stream": None, "time_to_first_chunk_ms": None,
        }
        block.calls.append(current)
        return current

    def ensure() -> Dict[str, Any]:
        return current if current is not None else open_call()

    for line in block.lines:
        if (m := REQUEST_START.search(line)):
            if int(m.group(1)) != session_id:
                block.foreign_sessions.append(int(m.group(1)))
                continue
            # ONE per turn, and it describes the FIRST call.
            first = ensure()
            first["messages_count"] = int(m.group(2))
            first["tools_count"] = int(m.group(3))
            continue
        if (m := PROMPT_ACCOUNT.search(line)):
            # A second account on the same record means a new call: the account is written before
            # its own stream, so it cannot belong to the call that just finished.
            if current is None or current["account"] is not None or current["stream"] is not None:
                open_call()
            ensure()["account"] = {
                "total": _int(m.group(1)), "system": _int(m.group(2)), "history": _int(m.group(3)),
                "tool_results": _int(m.group(4)), "tool_schemas": _int(m.group(5)),
                "replayed_reasoning": _int(m.group(6)), "counted_by_trim": _int(m.group(7)),
                "ceiling": _int(m.group(8)),
                "soft": _int(m.group(9)) if m.group(9) else None,
            }
            continue
        if (m := STREAM_OPENED.search(line)):
            if int(m.group(1)) != session_id:
                block.foreign_sessions.append(int(m.group(1)))
                continue
            if current is None or current["stream"] is not None:
                open_call()
            continue
        if (m := FIRST_CHUNK.search(line)):
            if int(m.group(1)) != session_id:
                block.foreign_sessions.append(int(m.group(1)))
                continue
            call = ensure()
            if call["time_to_first_chunk_ms"] is None:
                call["time_to_first_chunk_ms"] = float(m.group(2))
            continue
        if (m := OUTPUT_BUDGET.search(line)):
            ensure()["output_budget"] = {
                "max_tokens_sent": int(m.group(1)), "reason": m.group(2), "declared": int(m.group(3)),
            }
            continue
        if (m := STREAM_COMPLETED.search(line)):
            ensure()["stream"] = {
                "prompt_tokens": _usage(m.group(9)), "completion_tokens": _usage(m.group(10)),
                "chunk_count": int(m.group(1)), "accumulated_chars": int(m.group(2)),
                "tool_calls_count": int(m.group(4)), "invalid_chunks": int(m.group(5)),
                "total_stream_time_ms": float(m.group(6)), "finish_reason": m.group(7),
                "truncated": m.group(8) == "True",
            }
            continue
        if (m := FETCH.search(line)):
            block.fetches.append({"url": m.group(1), "chars": int(m.group(2))})
            continue
        if (m := FETCH_RESULT.search(line)):
            block.fetch_results.append({"url": m.group(2), "success": m.group(1) == "True"})
            continue
        if (m := CAPPED.search(line)):
            # What actually went INTO the prompt. The fetched size is the page; the cap is the
            # passage, and the difference is 12x on a Wikipedia article (24,302 of 288,172).
            block.capped[m.group(1)] = int(m.group(2))
            continue
        if (m := TOOL_FAILURE.search(line)):
            block.tool_failures.append({"tool": m.group(1), "error": m.group(2)[:80], "type": m.group(3)})
            continue
        if (m := TOOL_CALL.search(line)):
            block.tool_names.append(m.group(1))
            continue
        for other in SESSION_LINE.finditer(line):
            if int(other.group(1)) != session_id:
                block.foreign_sessions.append(int(other.group(1)))
    return block


# ---------------------------------------------------------------------------
# The check — mechanical, no judge
# ---------------------------------------------------------------------------


def _url_key(url: Any) -> str:
    """A url as a comparable key: no trailing slash, no case, no surrounding space."""
    return str(url or "").strip().rstrip("/").lower()


def check_answer(answer: str, check: Dict[str, Any], sources: Sequence[str] = (),
                 fetched_urls: Sequence[str] = ()) -> Dict[str, Any]:
    """The mechanical pass: the facts the answer must carry, its shape, and — where the job pins
    its own sources — that the run actually FETCHED them.

    The coverage half is what makes "five sources" mean five sources: an answer can carry the right
    facts out of the model's own knowledge, and the fresh-fetch window can serve a page the run
    never re-read, so counting what the run's own fetch results name is the only honest gate.
    """
    haystack = answer if check.get("case_sensitive") else answer.lower()
    needles = [str(n) for n in check.get("needles", [])]
    missing = [n for n in needles if (n if check.get("case_sensitive") else n.lower()) not in haystack]
    minimum = int(check.get("min_answer_chars", 0) or 0)
    short = len(answer) < minimum
    fetched_keys = {_url_key(url) for url in fetched_urls}
    missing_fetches = (
        [url for url in sources if _url_key(url) not in fetched_keys]
        if check.get("require_fetched") else []
    )
    return {
        "passed": not missing and not short and not missing_fetches,
        "needles": len(needles),
        "missing": missing,
        "answer_chars": len(answer),
        "min_answer_chars": minimum,
        "short": short,
        "coverage_required": bool(check.get("require_fetched")),
        "sources_expected": len(sources),
        "fetched": len(fetched_urls),
        "missing_fetches": missing_fetches,
    }


# ---------------------------------------------------------------------------
# One job, end to end
# ---------------------------------------------------------------------------


def fingerprint_assignments(project_root: Path, workspace_key: str) -> Dict[str, List[int]]:
    """The agent's notebooks, by name, size and mtime — taken BEFORE a run and after it.

    The bench never clears a notebook it did not create: an agent's assignments are its work
    product. What the driver does instead is show the state the job ran against — read from the
    FILES, because the app's automatic fetch capture writes one without any tool call.
    """
    directory = notebooks_dir(project_root, workspace_key)
    if not directory.is_dir():
        return {}
    fingerprints: Dict[str, List[int]] = {}
    for path in sorted(directory.glob("*.json")):
        stat = path.stat()
        fingerprints[path.name] = [stat.st_size, stat.st_mtime_ns]
    return fingerprints


def _cleared_slugs(cleared: Sequence[Any]) -> set:
    """The slugs a pre-run clear moved, whatever shape the caller holds them in."""
    slugs = set()
    for entry in cleared or ():
        if isinstance(entry, dict):
            if entry.get("slug"):
                slugs.add(str(entry["slug"]))
        else:
            slugs.add(str(entry))
    return slugs


def notebooks_touched(project_root: Path, workspace_key: str, before: Dict[str, List[int]],
                      started_at: Optional[_dt.datetime] = None,
                      cleared: Sequence[str] = ()) -> List[Dict[str, Any]]:
    """The notebooks this run created or changed, read off the files themselves.

    **`resumed` is the file's own account, not our bookkeeping.** A notebook we moved aside
    pre-run and the app then re-created has the SAME NAME, so a name-in-`before` test calls a
    genuinely fresh notebook "resumed" — the run's start time against the notebook's own
    `created_at` is what settles it. (Falling back to the fingerprint only when the file carries
    no timestamp, and reporting which rule decided, so a wrong verdict names its own basis.)
    """
    touched: List[Dict[str, Any]] = []
    directory = notebooks_dir(project_root, workspace_key)
    for path in sorted(directory.glob("*.json")):
        stat = path.stat()
        if before.get(path.name) == [stat.st_size, stat.st_mtime_ns]:
            continue
        state = read_notebook(path)
        created = _parse_stamp(state.get("created_at", ""))
        if created is not None and started_at is not None:
            state["resumed"] = created < started_at
            state["resumed_basis"] = "the notebook's own created_at"
        else:
            state["resumed"] = path.name in before and path.stem not in _cleared_slugs(cleared)
            state["resumed_basis"] = "the pre-run fingerprint (no readable created_at)"
        touched.append(state)
    return touched


def notebook_verdict(required: Optional[str], touched: List[Dict[str, Any]],
                     cleared: Sequence[Any]) -> Dict[str, Any]:
    """Did the job run against the state its fixture asked for?"""
    if not touched:
        return {
            "required": required,
            "ok": required == "fresh",
            "cleared_pre_run": cleared,
            "note": "no notebook touched (nothing to resume)",
        }
    if len(touched) > 1:
        return {
            "required": required,
            "ok": False,
            "cleared_pre_run": cleared,
            "note": f"the run touched {len(touched)} notebooks — the state is ambiguous: "
                    f"{[t.get('slug') for t in touched]}",
        }
    used = dict(touched[0])
    used["required"] = required
    used["cleared_pre_run"] = cleared
    resumed = bool(used.get("resumed"))
    used["ok"] = not (required == "fresh" and resumed)
    if required == "fresh" and resumed:
        where = (
            "the notebook we cleared was replaced underneath us"
            if used.get("slug") in _cleared_slugs(cleared)
            else "the pre-run clear did not match it"
        )
        used["note"] = (
            f"asked for a FRESH notebook and the run used one written BEFORE it started "
            f"({used.get('notes')} note(s) in it) — {where}, so this row is not comparable with a "
            f"fresh one"
        )
    elif required == "fresh":
        used["note"] = (
            f"opened {used.get('slug')!r} for this turn's goal "
            f"({used.get('notes')} note(s), {used.get('fetches_recorded')} fetch(es) recorded)"
        )
    elif not resumed:
        used["note"] = f"asked for a filled notebook and the run opened a NEW one ({used.get('slug')!r})"
    else:
        used["note"] = f"resumed {used.get('slug')!r} — as the fixture asked"
    return used


def call_metrics(calls: Sequence[Dict[str, Any]], fetches: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """The per-CALL composition, reduced to the quantities that do not move when the agent's route does.

    Measured over six runs: `tool_schemas` came back 3,560 on every accounted call of every job, each
    fresh fetch's cap landed at 24,301–24,302 chars exactly, and `system` held inside ±11% — while the
    per-round `tool_results` and the peak prompt swung by 2–4× because a fetch served from the
    fresh-fetch WINDOW carries almost nothing into the prompt. So the priced quantities are the fixed
    ones (schemas, system) and the cap's realized size per fresh fetch; the totals are context.
    """
    accounts = [c["account"] for c in calls if c.get("account")]
    fresh = [f for f in fetches if f.get("capped") is not None]
    tool_max = max((a.get("tool_results", 0) for a in accounts), default=0)
    return {
        "calls": len(accounts),
        "peak_call_total": max((a.get("total", 0) for a in accounts), default=0),
        "schemas_max": max((a.get("tool_schemas", 0) for a in accounts), default=0),
        "system_max": max((a.get("system", 0) for a in accounts), default=0),
        "history_max": max((a.get("history", 0) for a in accounts), default=0),
        "replayed_max": max((a.get("replayed_reasoning", 0) for a in accounts), default=0),
        "tool_results_max": tool_max,
        "fresh_fetches": len(fresh),
        "capped_per_fetch": (
            max(f["capped"] for f in fresh) if fresh else None
        ),
        "ceiling": accounts[0].get("ceiling") if accounts else None,
    }


def budget_verdict(budget: Dict[str, Any], turn: Dict[str, Any], fetched: int, capped: int,
                   call: Optional[Dict[str, Any]] = None) -> List[str]:
    """Which declared ceilings this run broke — one home for the comparison.

    Two kinds of ceiling, and the difference is the whole point: the ones on the PER-CALL composition
    (schemas, system, the cap's realized size) sit on quantities that held still across six runs, and
    are therefore gates; `tokens_in` is an ALARM, because its swing on an unchanged job is up to 3x and
    a ceiling on it can only catch an order-of-magnitude regression.
    """
    over: List[str] = []
    call = call or {}
    if turn.get("provider_calls") and budget.get("rounds") and turn["provider_calls"] > int(budget["rounds"]):
        over.append(f"rounds {turn['provider_calls']} > {int(budget['rounds'])}")
    if call.get("schemas_max") and budget.get("schemas_max") and call["schemas_max"] > int(budget["schemas_max"]):
        over.append(f"tool schemas {call['schemas_max']:,}/call > {int(budget['schemas_max']):,}")
    if call.get("system_max") and budget.get("system_max") and call["system_max"] > int(budget["system_max"]):
        over.append(f"system {call['system_max']:,}/call > {int(budget['system_max']):,}")
    if (
        call.get("capped_per_fetch")
        and budget.get("capped_chars_per_fetch")
        and call["capped_per_fetch"] > int(budget["capped_chars_per_fetch"])
    ):
        over.append(
            f"capped {call['capped_per_fetch']:,} chars/fetch > {int(budget['capped_chars_per_fetch']):,}"
        )
    if budget.get("capped_chars") and capped > int(budget["capped_chars"]):
        over.append(f"capped_chars {capped:,} total > {int(budget['capped_chars']):,}")
    if budget.get("tokens_in_alarm") and turn.get("tokens_in") and turn["tokens_in"] > int(budget["tokens_in_alarm"]):
        over.append(
            f"ALARM tokens_in {turn['tokens_in']:,} > {int(budget['tokens_in_alarm']):,} "
            f"(not a gate: the band on an unchanged job reaches 3x)"
        )
    return over


def run_job(job: Job, *, base_url: str, project_root: Path, run_dir: Path, log_path: Path,
            agent: Dict[str, Any], runs_dir: Path) -> Dict[str, Any]:
    workspace_key = str(agent.get("workspace_key") or "")
    notebooks_before = fingerprint_assignments(project_root, workspace_key)
    cleared = clear_job_notebooks(
        project_root, workspace_key, job.data["message"], run_dir,
        also_slugs=previous_run_notebooks(runs_dir, job.job_id),
    )
    started_at = _dt.datetime.now(_dt.timezone.utc)
    offset = log_path.stat().st_size

    print(f"  → {job.job_id}: issuing", flush=True)
    issued = issue_turn(base_url, int(agent["id"]), job.data["message"])
    session_id = issued["session_id"]
    if session_id is None:
        return {
            "job": job.job_id, "error": "no session_id in the stream",
            "answer": issued["answer"], "errors": issued["errors"],
        }

    block = parse_block(
        read_block(log_path, offset, session_id), session_id
    )
    per_call = block.calls
    reported_prompts = [c["stream"]["prompt_tokens"] for c in per_call if c.get("stream")]
    reported_prompts = [p for p in reported_prompts if p is not None]

    turn = block.turn or {}
    budget = job.data.get("budget", {})
    # The fetch LIST is every fetch the tool RESULT reports; the SIZES ride the handler's own lines,
    # and a fresh-window hit carries none — so the ones without a size are counted and named, never
    # silently dropped.
    sized = {f["url"]: f for f in block.fetches}
    fetches: List[Dict[str, Any]] = []
    for result in block.fetch_results:
        entry: Dict[str, Any] = {"url": result["url"], "success": result["success"]}
        if result["url"] in sized:
            entry["chars"] = sized[result["url"]]["chars"]
            entry["capped"] = block.capped.get(result["url"])
        else:
            entry["chars"] = None
            entry["capped"] = None
            entry["size_source"] = "no handler line (a fresh-window hit, or a fetch that never reported)"
        fetches.append(entry)
    fetched = sum(f["chars"] for f in fetches if f.get("chars"))
    capped = sum(f["capped"] for f in fetches if f.get("capped"))
    call = call_metrics(per_call, fetches)
    over = budget_verdict(budget, turn, fetched, capped, call)

    check = check_answer(
        issued["answer"], job.data["check"], sources_of(job),
        [f["url"] for f in fetches if f.get("success")],
    )
    reached = sum(1 for f in fetches if f.get("success"))

    touched = notebooks_touched(
        project_root, workspace_key, notebooks_before, started_at=started_at, cleared=cleared
    )
    return {
        "job": job.job_id,
        "axis": job.data.get("axis", {}),
        "session_id": session_id,
        "notebooks": {
            "cleared_pre_run": cleared,
            "before": sorted(notebooks_before),
            "touched": touched,
        },
        "state": notebook_verdict(
            (job.data.get("state") or {}).get("assignment"), touched, cleared
        ),
        "tokens_in": turn.get("tokens_in"),
        "tokens_out": turn.get("tokens_out"),
        "tokens_source": turn.get("tokens_source"),
        "peak_prompt_tokens": max(reported_prompts) if reported_prompts else None,
        "provider_calls": turn.get("provider_calls"),
        "tool_calls": turn.get("tool_calls"),
        "tools_offered": turn.get("tools_offered"),
        "tool_calls_blocked": turn.get("tool_calls_blocked"),
        "tool_failures": turn.get("tool_failures"),
        "elapsed_s": turn.get("elapsed_s"),
        "wall_clock_s": issued["wall_clock_s"],
        "fetched_chars": fetched,
        "capped_chars": capped,
        "fetches": fetches,
        "tool_names": block.tool_names,
        "tool_failures_detail": block.tool_failures,
        "per_call": per_call,
        "call_metrics": call,
        "answer": issued["answer"],
        "answer_chars": len(issued["answer"]),
        "stream_errors": issued["errors"],
        "foreign_sessions_in_block": sorted(set(block.foreign_sessions)),
        "check": check,
        "budget": {"declared": budget, "over": over},
        "done_meta": (issued["done"] or {}).get("metadata"),
    }


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


BAND_METRICS = (
    "tokens_in", "provider_calls", "peak_prompt_tokens", "tok_per_round", "answer_chars",
    "capped_chars", "fetches",
    # The per-call composition — the quantities that held still across six runs.
    "schemas_max", "system_max", "capped_per_fetch", "peak_call_total", "tool_results_max",
)

NESTED_METRICS = ("schemas_max", "system_max", "capped_per_fetch", "peak_call_total", "tool_results_max")


def metric_of(row: Dict[str, Any], name: str) -> Optional[float]:
    """One metric off a row, derived where it is a ratio or lives in the per-call block."""
    if name == "tok_per_round":
        if row.get("provider_calls") and row.get("tokens_in"):
            return row["tokens_in"] / row["provider_calls"]
        return None
    if name == "fetches":
        return len(row.get("fetches") or [])
    if name in NESTED_METRICS:
        nested = row.get("call_metrics")
        # A row written before the per-call summary existed still carries its own accounts, so the
        # band reads them through the SAME function rather than a second copy of the reduction.
        if not nested and row.get("per_call"):
            nested = call_metrics(row.get("per_call") or [], row.get("fetches") or [])
        value = (nested or {}).get(name)
        return value if isinstance(value, (int, float)) else None
    value = row.get(name)
    return value if isinstance(value, (int, float)) else None


def measure_band(runs_dir: Path, jobs: List[Job]) -> Dict[str, Any]:
    """Every run of the same job already on disk is one sample of the instrument's own error bar.

    This is the number that makes a per-job delta readable: a run inside the band says nothing, a
    run outside it is a candidate finding — and the band's WIDTH is the honest answer to "can this
    job judge a change at all?".
    """
    directory = Path(runs_dir)
    runs = sorted(p for p in directory.glob("*") if p.is_dir() and (p / "rows.json").exists())
    band: Dict[str, Any] = {}
    for job in jobs:
        samples: Dict[str, List[float]] = {}
        for run in runs:
            try:
                rows = json.loads((run / "rows.json").read_text()).get("rows") or []
            except (OSError, ValueError):
                continue
            row = next(
                (r for r in rows if r.get("job") == job.job_id and not r.get("error")), None
            )
            if row is None:
                continue
            for metric in BAND_METRICS:
                value = metric_of(row, metric)
                if value is not None:
                    samples.setdefault(metric, []).append(value)
        band[job.job_id] = {
            "metric": {
                name: {
                    "min": min(values), "median": statistics.median(values), "max": max(values),
                    "spread": (max(values) / min(values) - 1) if min(values) else None,
                    "n": len(values),
                }
                for name, values in samples.items()
            },
            "runs": [p.name for p in runs],
        }
    return band


def band_verdict(job_band: Optional[Dict[str, Any]], row: Dict[str, Any]) -> List[str]:
    """Where this run sits inside the spread of every run of the same job before it."""
    notes: List[str] = []
    for name, stats in ((job_band or {}).get("metric") or {}).items():
        value = metric_of(row, name)
        if value is None:
            continue
        inside = stats["min"] <= value <= stats["max"]
        notes.append(
            f"{name} {value:,.0f} {'inside' if inside else '**OUTSIDE**'} the band "
            f"{stats['min']:,.0f}–{stats['max']:,.0f} ({stats['n']} runs)"
        )
    return notes


def format_band(band: Dict[str, Any]) -> str:
    head = f"{'job':<20} {'metric':<20} {'min':>12} {'median':>12} {'max':>12} {'spread':>8} {'n':>3}"
    lines = [head, "-" * len(head)]
    for job_id, entry in band.items():
        for name, stats in (entry.get("metric") or {}).items():
            spread = f"{stats['spread'] * 100:,.0f}%" if stats.get("spread") is not None else "-"
            lines.append(
                f"{job_id:<20} {name:<20} {stats['min']:>12,.0f} {stats['median']:>12,.0f} "
                f"{stats['max']:>12,.0f} {spread:>8} {stats['n']:>3}"
            )
    return "\n".join(lines)


def decompose(before: Dict[str, Any], after: Dict[str, Any]) -> str:
    """Attribute a change in `tokens_in` to ROUNDS or to PROMPT SIZE — the two things it is made of.

    A job's input cost is `rounds × the prompt it re-sends`, and the two move independently: a
    change that cuts the cap shrinks the prompt, a change that stops the agent re-reading cuts
    rounds, and a single total cannot tell them apart. This splits the difference into the two
    effects so a delta names its own cause.
    """
    rounds0, rounds1 = int(before.get("provider_calls") or 0), int(after.get("provider_calls") or 0)
    tokens0, tokens1 = int(before.get("tokens_in") or 0), int(after.get("tokens_in") or 0)
    if not rounds0 or not rounds1 or not tokens0 or not tokens1:
        return "no decomposition (a row is missing its rounds or its tokens_in)"
    avg0, avg1 = tokens0 / rounds0, tokens1 / rounds1
    from_rounds = (rounds1 - rounds0) * avg0
    from_prompt = rounds1 * (avg1 - avg0)
    return (
        f"tokens_in {tokens0:,} → {tokens1:,} ({tokens1 - tokens0:+,}) — "
        f"rounds {rounds0} → {rounds1} ({from_rounds:+,.0f} at {avg0:,.0f}/round) + "
        f"prompt {avg0:,.0f} → {avg1:,.0f}/round × {rounds1} rounds ({from_prompt:+,.0f})"
    )


def format_table(rows: List[Dict[str, Any]], baseline: Optional[Dict[str, Dict[str, Any]]]) -> str:
    head = (f"{'job':<20} {'tokens_in':>10} {'Δ':>10} {'peak prompt':>12} {'calls':>6} "
            f"{'tok/round':>10} {'answer':>8} {'into prompt':>12} {'sec':>6} {'pass':>5}")
    lines = [head, "-" * len(head)]
    for row in rows:
        if row.get("error"):
            lines.append(f"{row['job']:<20} ERROR: {row['error']}")
            continue
        delta = ""
        if baseline and baseline.get(row["job"], {}).get("tokens_in") and row.get("tokens_in"):
            delta = f"{row['tokens_in'] - baseline[row['job']]['tokens_in']:+,}"
        peak = row.get("peak_prompt_tokens")
        rounds = int(row.get("provider_calls") or 0)
        per_round = f"{row['tokens_in'] / rounds:,.0f}" if rounds and row.get("tokens_in") else "-"
        # A row written before `capped_chars` existed reads "-", never 0: an unmeasured prompt is
        # not an empty one.
        capped = row.get("capped_chars")
        capped_text = f"{capped:,}" if capped is not None else "-"
        lines.append(
            f"{row['job']:<20} {row['tokens_in'] or 0:>10,} {delta:>10} "
            f"{(f'{peak:,}' if peak else 'unreported'):>12} {rounds:>6} {per_round:>10} "
            f"{row.get('answer_chars') or 0:>8,} {capped_text:>12} "
            f"{row['elapsed_s'] or 0:>6.1f} {'PASS' if row['check']['passed'] else 'FAIL':>5}"
        )
    return "\n".join(lines)


def write_report(run_dir: Path, rows: List[Dict[str, Any]],
                 baseline: Optional[Dict[str, Dict[str, Any]]],
                 band: Optional[Dict[str, Any]] = None) -> Path:
    table = format_table(rows, baseline)
    parts = [
        f"# THE BENCH — {run_dir.name}",
        "",
        "How to read this: a job's input cost is **rounds × the prompt it re-sends**, so a move in",
        "`tokens_in` is attributed below (rounds vs prompt size) rather than taken as one number.",
        "Depth shows in `answer` and `tokens_out`, not in the input price — a longer answer is one",
        "bigger call, while a scan that re-reads pays for every round. And a value **inside the band**",
        "of this job's earlier runs is a re-roll, not a result: the band is the instrument's own error.",
        "",
        "```",
        table,
        "```",
        "",
    ]
    for row in rows:
        parts.append(f"## {row['job']}")
        if row.get("error"):
            parts += [f"**ERROR** {row['error']}", ""]
            continue
        check = row["check"]
        peak = row.get("peak_prompt_tokens")
        capped = row.get("capped_chars")
        into_prompt = (
            f" — of which **{capped:,} reached the prompt**"
            if capped is not None
            else " (the into-the-prompt figure was not collected on this row)"
        )
        parts += [
            f"session `{row['session_id']}` · tokens_in **{row['tokens_in']:,}** "
            f"({row['tokens_source']}) · tokens_out {row['tokens_out']:,} · "
            f"peak prompt {f'{peak:,}' if peak else 'unreported'} · "
            f"calls {row['provider_calls']} · fetched {row['fetched_chars']:,} chars{into_prompt} "
            f"({len(row['fetches'])} fetch(es)) · elapsed {row['elapsed_s']}s",
            "",
            f"check: {'PASS' if check['passed'] else 'FAIL'} — {check['needles']} needle(s), "
            f"missing {check['missing'] or 'none'}, answer {check['answer_chars']} chars "
            f"(minimum {check['min_answer_chars']})"
            + (
                f" · coverage: fetched {check['fetched']} of {check['sources_expected']} given "
                f"source(s), missing {check['missing_fetches'] or 'none'}"
                if check.get("coverage_required") else ""
            ),
            "",
        ]
        cm = row.get("call_metrics") or {}
        if cm:
            cap = cm.get("capped_per_fetch")
            ceiling = cm.get("ceiling")
            cap_text = f"{cap:,}" if cap else "not recorded"
            ceiling_text = f"{ceiling:,}" if ceiling else "unnamed"
            parts += [
                f"composition per call: peak call {cm.get('peak_call_total', 0):,} · "
                f"schemas {cm.get('schemas_max', 0):,} · system {cm.get('system_max', 0):,} · "
                f"tool results {cm.get('tool_results_max', 0):,} · cap {cap_text} chars per fresh "
                f"fetch over {cm.get('fresh_fetches', 0)} fresh fetch(es) · the ceiling in force "
                f"{ceiling_text}",
                "",
            ]
        state = row.get("state") or {}
        cleared = state.get("cleared_pre_run") or []
        cleared_text = (
            ", ".join(f"{c.get('slug')} ({c.get('matched_by')})" for c in cleared) if cleared else "nothing"
        )
        parts += [
            f"notebook: asked {state.get('required')!r} · used {state.get('slug')!r} · "
            f"resumed {state.get('resumed')} · notes {state.get('notes')} · "
            f"cleared pre-run {cleared_text} · "
            f"{'as asked' if state.get('ok') else 'NOT AS ASKED'}",
            "",
        ]
        if baseline and baseline.get(row["job"]):
            was = baseline[row["job"]]
            parts += [
                f"vs baseline: {decompose(was, row)}",
                f"  answer {was.get('answer_chars') or 0:,} → {row.get('answer_chars') or 0:,} chars · "
                f"tokens_out {was.get('tokens_out') or 0:,} → {row.get('tokens_out') or 0:,}",
                "",
            ]
        band_notes = band_verdict((band or {}).get(row["job"]), row)
        if band_notes:
            parts += ["vs band: " + " · ".join(band_notes), ""]
        if state.get("note"):
            parts += [f"**NOTEBOOK**: {state['note']}", ""]
        if row["budget"]["over"]:
            parts += [f"**OVER BUDGET**: {'; '.join(row['budget']['over'])}", ""]
        if row["foreign_sessions_in_block"]:
            parts += [f"**CONTAMINATED BLOCK** — other sessions in this turn's lines: "
                      f"{row['foreign_sessions_in_block']}", ""]
        if row["stream_errors"]:
            parts += [f"**STREAM ERRORS**: {row['stream_errors']}", ""]
        parts += ["```", "tool calls: " + (", ".join(row["tool_names"]) or "(none)"), ""]
        for fetch in row["fetches"]:
            # Only claim what was collected: a row written before the cap was read has no opinion
            # about whether this fetch was capped, and a fresh-window hit has no size at all.
            chars = fetch.get("chars")
            capped_fetch = fetch.get("capped")
            size = f"{chars:>9,} chars" if chars else "  size n/a"
            if fetch.get("size_source"):
                note = " (no handler line: a fresh-window hit, or a fetch that never reported)"
            elif "capped" not in fetch:
                note = " (cap not recorded on this row)"
            elif capped_fetch is not None:
                note = f" — {capped_fetch:,} into the prompt"
            else:
                note = " — not capped"
            parts.append(f"fetch: {size}{note}  {fetch['url']}")
        for failure in row.get("tool_failures_detail") or []:
            parts.append(f"TOOL FAILURE: {failure['tool']} — {failure['error']} ({failure['type']})")
        parts.append("")
        for index, call in enumerate(row["per_call"], start=1):
            account = call.get("account") or {}
            stream = call.get("stream") or {}
            parts.append(
                f"call {index}: prompt_tokens={stream.get('prompt_tokens')} "
                f"completion_tokens={stream.get('completion_tokens')} "
                f"ttfc_ms={call.get('time_to_first_chunk_ms')} "
                f"chunks={stream.get('chunk_count')} chars={stream.get('accumulated_chars')} "
                f"finish={stream.get('finish_reason')} stream_ms={stream.get('total_stream_time_ms')}"
            )
            if account:
                parts.append(
                    f"        composition: total={account.get('total'):,} system={account.get('system'):,} "
                    f"history={account.get('history'):,} tool_results={account.get('tool_results'):,} "
                    f"tool_schemas={account.get('tool_schemas'):,} "
                    f"replayed={account.get('replayed_reasoning'):,} ceiling={account.get('ceiling'):,}"
                )
        parts += ["```", ""]
    report = run_dir / "report.md"
    report.write_text("\n".join(parts))
    return report


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def check_fixtures(jobs: List[Job]) -> int:
    """Do the needles still exist at the sources? Network reads, no LLM."""
    failures = 0
    for job in jobs:
        needles = job.data["check"]["needles"]
        bodies: Dict[str, str] = {}
        for url in sources_of(job):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": "cogitate-bench"})
                with urllib.request.urlopen(request, timeout=30) as response:
                    bodies[url] = response.read().decode("utf-8", "ignore")
            except Exception as exc:  # noqa: BLE001 — a source that cannot be read is the finding
                print(f"  {job.job_id}: SOURCE UNREADABLE {url} — {type(exc).__name__}: {exc}")
        missing = [n for n in needles if not any(n.lower() in b.lower() for b in bodies.values())]
        print(f"  {job.job_id:<20} {len(needles) - len(missing)}/{len(needles)} needles present"
              f"{' — MISSING ' + str(missing) if missing else ''}")
        failures += 1 if missing else 0
    return failures


def write_artifacts(run_dir: Path, rows: List[Dict[str, Any]],
                    baseline: Optional[Dict[str, Dict[str, Any]]],
                    band: Optional[Dict[str, Any]] = None) -> Dict[str, Path]:
    """A run keeps its evidence: the rows, the table, and every answer the checks judged.

    The answers are the checks' own evidence — a FAIL nobody can read is a FAIL nobody can
    explain — so they are written whole, one file per job, beside the row that scored them.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "rows.json").write_text(json.dumps({"run": run_dir.name, "rows": rows}, indent=2))
    answers = run_dir / "answers"
    written: Dict[str, Path] = {}
    for row in rows:
        if row.get("answer"):
            answers.mkdir(exist_ok=True)
            path = answers / f"{row['job']}.md"
            path.write_text(row["answer"])
            written[row["job"]] = path
    written["report"] = write_report(run_dir, rows, baseline, band)
    written["rows"] = run_dir / "rows.json"
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="THE BENCH — issue the fixed job set and judge it")
    parser.add_argument("--jobs-dir", default=DEFAULT_JOBS)
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS)
    parser.add_argument("--log-file", default=DEFAULT_LOG)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--run-id", default=None, help="the run folder's name (default: a timestamp)")
    parser.add_argument("--jobs", default=None, help="comma-separated job ids (default: all)")
    parser.add_argument("--list", action="store_true", help="show the jobs and stop")
    parser.add_argument("--check-fixtures", action="store_true", help="verify the needles at the sources")
    parser.add_argument("--measure-band", action="store_true",
                        help="the spread of every run of each job already on disk (free)")
    parser.add_argument("--run", action="store_true", help="issue the jobs (needs --go to spend)")
    parser.add_argument("--go", action="store_true", help="consent to the paid calls")
    parser.add_argument("--diff", default=None, help="a baseline rows.json to diff against")
    parser.add_argument("--save-baseline", action="store_true", help="store this run as the baseline")
    parser.add_argument("--sleep-between", type=float, default=2.0,
                        help="seconds between jobs, so the turns' log blocks stay separable")
    args = parser.parse_args()

    project_root = Path.cwd()
    if not (project_root / "backend").is_dir():
        raise SystemExit(f"run this from the project root (backend/ not found in {project_root})")

    jobs = load_jobs(args.jobs_dir)
    if args.jobs:
        wanted = {j.strip() for j in args.jobs.split(",")}
        jobs = [j for j in jobs if j.job_id in wanted]
        if not jobs:
            raise SystemExit("no job matched --jobs")

    if args.list or not (args.check_fixtures or args.run or args.measure_band):
        print(f"THE BENCH — {len(jobs)} job(s) in {args.jobs_dir}\n")
        for job in jobs:
            print(f"  {job.summary()}")
            print(f"      {job.data['why'].splitlines()[0]}")
        print(f"\nchecks carry no answer key: {sum(len(j.data['check']['needles']) for j in jobs)} "
              f"needle(s) over {len(jobs)} job(s); a needle is a fact only that job's own sources hold.")
        if not (args.check_fixtures or args.run):
            print("\nNothing was issued. --check-fixtures reads the sources; --run --go issues the jobs.")
        return 0

    if args.check_fixtures:
        print(f"THE BENCH — do the needles still exist at the sources? ({len(jobs)} job(s))\n")
        failures = check_fixtures(jobs)
        print(f"\n{'ALL NEEDLES PRESENT' if not failures else f'{failures} JOB(S) WITH MISSING NEEDLES'}")
        return 1 if failures else 0

    if args.measure_band:
        band = measure_band(Path(args.runs_dir), jobs)
        target = Path(args.runs_dir) / "band.json"
        target.write_text(json.dumps(band, indent=2))
        print(f"THE BENCH — the spread over every run on disk ({len(band)} job(s))\n")
        print(format_band(band))
        print(f"\nA value inside a band is a re-roll, not a result. Written: {target}")
        return 0

    # --run: announce, and stop unless the user's consent is on the command line.
    agents = {job.agent: resolve_agent(args.base_url, job.agent) for job in jobs}
    calls_low, calls_high = 2 * len(jobs), 3 * len(jobs)
    who = ", ".join(f"{name} (#{agent['id']})" for name, agent in agents.items())
    print(f"THE BENCH — {len(jobs)} job(s) against {who}\n")
    for job in jobs:
        print(f"  {job.summary()}")
    print(f"\nEVERY JOB IS A REAL PAID TURN: ~{calls_low}-{calls_high} provider calls across "
          f"{len(jobs)} job(s), at whatever the agent's own model costs.")
    if not args.go:
        print("\nNot issued — this is the announcement. Add --go to spend it.")
        return 0

    run_dir = Path(args.runs_dir) / (args.run_id or time.strftime("%Y%m%d-%H%M%S"))
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = project_root / args.log_file
    baseline: Optional[Dict[str, Dict[str, Any]]] = None
    if args.diff:
        loaded = json.loads(Path(args.diff).read_text())
        baseline = {row["job"]: row for row in (loaded.get("rows") or loaded)}

    band: Optional[Dict[str, Any]] = None
    band_file = Path(args.runs_dir) / "band.json"
    if band_file.exists():
        try:
            band = json.loads(band_file.read_text())
        except (OSError, ValueError):
            band = None

    print(f"\nrun folder: {run_dir}\n")
    rows: List[Dict[str, Any]] = []
    for index, job in enumerate(jobs):
        if index:
            time.sleep(args.sleep_between)
        row = run_job(job, base_url=args.base_url, project_root=project_root, run_dir=run_dir,
                      log_path=log_path, agent=agents[job.agent], runs_dir=Path(args.runs_dir))
        rows.append(row)
        if row.get("error"):
            print(f"    ERROR: {row['error']}", flush=True)
        else:
            peak = row["peak_prompt_tokens"]
            print(f"    tokens_in {row['tokens_in']:,} · peak prompt "
                  f"{f'{peak:,}' if peak else 'unreported'} · calls {row['provider_calls']} · "
                  f"fetched {row['fetched_chars']:,} chars ({row.get('capped_chars', 0):,} into the prompt) · "
                  f"check {'PASS' if row['check']['passed'] else 'FAIL ' + str(row['check']['missing'])}",
                  flush=True)
            if row["budget"]["over"]:
                print(f"    OVER BUDGET: {'; '.join(row['budget']['over'])}", flush=True)
            state = row.get("state") or {}
            if state.get("note"):
                print(f"    NOTEBOOK: {state['note']}", flush=True)

    payload = {"run": run_dir.name, "rows": rows}
    artifacts = write_artifacts(run_dir, rows, baseline, band)

    print("\n" + format_table(rows, baseline))
    if args.save_baseline:
        target = Path(args.runs_dir) / "baseline.json"
        target.write_text(json.dumps(payload, indent=2))
        print(f"\nbaseline stored: {target}")
    print(f"\nreport: {artifacts['report']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
