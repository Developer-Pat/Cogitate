"""The agent's notebook — the assignment store and the four tools over it.

What matters here, and why each test exists:

- **a reopened goal resumes its notebook** — an agent that opens the same piece of work twice
  must find what it gathered, not an empty replacement;
- **a note round-trips** — what a call returns is what the next read sees (no drift between the
  read-back and the disk);
- **an id can never escape the agent's folder** — ids arrive from a model and become filenames;
- **an unreadable notebook refuses loudly** — an empty read would ARM the next write, which would
  erase every note (the `agent_state` defect, paid for once already);
- **the digest names the sources already gathered** — that line is the whole point: it is what
  stops a run re-fetching what it has (measured: 91 URLs fetched more than once);
- **a bare write lands on the current assignment**, which is DERIVED (most recent open), never a
  stored pointer;
- **the prompt block is silent with nothing open** — nothing is injected until there is something
  to inject.
"""

import sys

sys.path.insert(0, "backend")

import json

import pytest

from app.domain.agents.assignments import (
    FETCH_EXCERPT_LIMIT,
    AssignmentNotFound,
    AssignmentStore,
    AssignmentUnreadable,
    build_assignments_block,
)

GOAL = "the leading economic headline for Europe"


@pytest.fixture
def store(tmp_path):
    return AssignmentStore(base_dir=tmp_path)


# ── the store ──────────────────────────────────────────────────────────────


def test_open_then_reopen_resumes_the_same_notebook(store):
    data, resumed = store.open(GOAL)
    assert resumed is False
    assert data["id"] == "the-leading-economic-headline-for-europe"
    assert data["status"] == "open"

    store.add_note("the ECB held rates", source="https://ecb.europa.eu")

    again, resumed_again = store.open(GOAL)
    assert resumed_again is True
    assert again["id"] == data["id"]
    assert len(again["notes"]) == 1, "reopening must not wipe what was gathered"


def test_a_note_is_the_verified_read_back(store):
    store.open(GOAL)
    written = store.add_note("inflation fell to 2.1%", source="https://reuters.com/x", title="ECB")
    assert written["count"] == 1

    stored = store.read(written["assignment"])["notes"][-1]
    assert stored["text"] == written["entry"]["text"] == "inflation fell to 2.1%"
    assert stored["source"] == "https://reuters.com/x"
    assert stored["kind"] == "note"
    assert stored["at"]


def test_a_bare_write_goes_to_the_most_recently_open_assignment(store):
    first, _ = store.open("first piece")
    second, _ = store.open("second piece")
    store.add_note("in the second")

    # the current one is derived: the most recently UPDATED open assignment
    assert store.current()["id"] == second["id"]
    store.add_note("also the second", assignment_id=None)
    assert len(store.read(second["id"])["notes"]) == 2
    assert store.read(first["id"])["notes"] == []


def test_a_closed_assignment_leaves_the_prompt_and_the_default(store):
    data, _ = store.open(GOAL)
    store.add_note("something")
    store.close(result="the ECB call led the day")

    assert store.digest() is None, "nothing open -> no prompt block"
    with pytest.raises(AssignmentNotFound):
        store.add_note("a note with nowhere to go")

    reopened = store.reopen(data["id"])
    assert reopened["status"] == "open"
    assert "the ECB call led the day" == reopened["result"]


def test_an_id_can_never_escape_the_agent_folder(store, tmp_path):
    store.open(GOAL)
    for bad in ("../outside", "..", "a/b", "", "-leading", "a b"):
        with pytest.raises(ValueError):
            store.read(bad)
    assert not (tmp_path.parent / "outside.json").exists()
    # an id the model capitalised is NORMALISED, not rejected — safe here, because the id only
    # ever names a file inside this folder
    assert store.read("The-Leading-Economic-Headline-For-Europe")["id"] == (
        "the-leading-economic-headline-for-europe"
    )


def test_an_unreadable_notebook_refuses_instead_of_reading_empty(store):
    store.open(GOAL)
    path = store.dir / "the-leading-economic-headline-for-europe.json"
    path.write_text("{ not json", encoding="utf-8")

    with pytest.raises(AssignmentUnreadable):
        store.read("the-leading-economic-headline-for-europe")

    # and a bare write refuses too — it cannot silently overwrite the broken document
    with pytest.raises(AssignmentUnreadable):
        store.add_note("this must not land on the broken file")


def test_the_digest_names_the_sources_already_gathered(store):
    store.open(GOAL)
    store.add_note("the ECB held rates", source="https://ecb.europa.eu")
    store.note_fetch("https://reuters.com/world/europe", chars=15062, excerpt="headlines…")

    digest = store.digest()
    assert digest is not None
    assert GOAL in digest
    assert "1 note(s)" in digest
    assert "https://reuters.com/world/europe" in digest, "the dedupe line is the point"
    assert digest.count("https://reuters.com/world/europe") == 1, "don't repeat a source"


def test_two_non_latin_goals_do_not_share_a_notebook(store):
    first, _ = store.open("عنوان الاقتصاد الأوروبي")
    second, _ = store.open("سرخط اقتصادی اروپا")
    assert first["id"] != second["id"]
    assert first["id"].startswith("assignment-")


def test_note_fetch_records_proof_not_the_payload(store):
    store.open(GOAL)
    store.note_fetch("https://www.entekhab.ir", chars=463980, excerpt="x" * 5000)
    entry = store.read("the-leading-economic-headline-for-europe")["notes"][-1]
    assert entry["chars"] == 463980
    assert len(entry["excerpt"]) == FETCH_EXCERPT_LIMIT
    assert store.sources_seen() == ["https://www.entekhab.ir"]


def test_a_note_is_capped_so_the_notebook_is_not_a_payload_dump(store):
    store.open(GOAL)
    written = store.add_note("y" * 20000)
    assert len(written["entry"]["text"]) == 8000
    assert written["entry"]["truncated_at"] == 8000


def test_a_pasted_document_does_not_become_a_goal_in_every_prompt(store):
    """The goal rides the prompt digest every turn, and the automatic capture takes it from the
    turn's request — so a message that IS a document must be capped at the door."""
    from app.domain.agents.assignments import GOAL_LIMIT

    data, _ = store.open("x" * 4000 + "\n\nand the real question is at the end")
    assert len(data["goal"]) == GOAL_LIMIT + 1          # the cap, plus the ellipsis
    assert data["goal"].endswith("…")
    assert len(store.digest()) < GOAL_LIMIT + 800, "the digest stays cheap"


# ── the freshness dedupe (2026-10-13) ──────────────────────────────────────


def test_age_label_says_how_long_ago_in_words():
    import datetime as dt

    from app.domain.agents.assignments import age_label

    now = dt.datetime(2026, 10, 13, 12, 0, 0, tzinfo=dt.timezone.utc)
    assert age_label("2026-10-13T11:59:30+00:00", now) == "just now"
    assert age_label("2026-10-13T11:49:00+00:00", now) == "11 min ago"
    assert age_label("2026-10-13T09:00:00+00:00", now) == "3 h ago"
    assert age_label("2026-10-11T12:00:00+00:00", now) == "2 days ago"
    assert age_label("not a timestamp", now) == "at an unknown time"
    assert age_label("", now) == "at an unknown time"


def test_the_digest_carries_each_source_age(store):
    store.open(GOAL)
    store.note_fetch("https://www.wowt.com", chars=60950, title="Home")
    digest = store.digest()
    assert "https://www.wowt.com (just now)" in digest, "the age is the point"
    assert "refresh=true" in digest, "and the escape hatch is named"


def test_a_recent_fetch_is_remembered_and_an_old_one_is_not(store):
    import datetime as dt

    from app.domain.agents import assignments as A

    store.open(GOAL)
    store.note_fetch("https://www.wowt.com/", chars=60950, title="Home")
    store.add_note("the lead is the house fire", source="https://www.wowt.com")

    # the trailing slash is not a different page, and the notes come back with the record
    remembered = store.recent_fetch("https://www.wowt.com", within_minutes=30)
    assert remembered["chars"] == 60950
    assert remembered["age"] == "just now"
    assert remembered["assignment"] == "the-leading-economic-headline-for-europe"
    assert remembered["notes"][0]["text"] == "the lead is the house fire"

    # outside the window the notebook does NOT answer — an old fetch is not a reason to withhold
    assert store.recent_fetch("https://www.wowt.com", within_minutes=0) is None
    assert store.recent_fetch("https://never.fetched.example") is None

    # and the window is read from the record, not from when the notebook was last touched
    data = store.read("the-leading-economic-headline-for-europe")
    stale = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=3)
    for entry in data["notes"]:
        if entry["kind"] == "fetch":
            entry["at"] = stale.isoformat(timespec="microseconds")
    (store.dir / "the-leading-economic-headline-for-europe.json").write_text(
        json.dumps(data), encoding="utf-8"
    )
    assert store.recent_fetch("https://www.wowt.com") is None
    assert A.FRESH_FETCH_MINUTES == 30


async def test_a_fetch_of_a_fresh_url_is_answered_from_the_notebook_without_the_network(
    tmp_path, monkeypatch
):
    """The whole point: the page is NOT pulled. httpx is rigged to explode, so a test that
    passes proves no request went out."""
    import httpx

    from app.domain.agents.assignments import AssignmentStore
    from app.domain.tools.builtin.jina_reader_handler import JinaReaderTool

    base = tmp_path / "bob"
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    class ExplodingClient:
        def __init__(self, *a, **k):
            raise AssertionError("the network must not be touched for a fresh notebook hit")

    monkeypatch.setattr(httpx, "AsyncClient", ExplodingClient)

    store = AssignmentStore(base_dir=str(base))
    store.open("Check the local headlines.")
    store.note_fetch("https://www.wowt.com", chars=60950, title="Home", excerpt="Title: Home…")
    store.add_note("the lead is the South Omaha house fire", source="https://www.wowt.com")

    result = await JinaReaderTool().execute({"base_path": str(base)}, url="https://www.wowt.com")
    assert result["success"] is True
    assert result["cached"] is True
    assert result["age"] == "just now"
    assert result["content_length"] == 60950
    assert result["notebook"]["goal"] == "Check the local headlines."
    assert "house fire" in result["notebook"]["notes"][0]["text"]
    assert "refresh=true" in result["user_message"]
    # the capture hook must NOT record a served answer as a second fetch
    from app.domain.agents.assignments import fetch_facts

    assert fetch_facts(result) is None


async def test_refresh_true_fetches_anyway(tmp_path, monkeypatch):
    """The escape hatch: a caller who needs a genuinely new copy gets one, notebook or not."""
    import httpx

    from app.domain.agents.assignments import AssignmentStore
    from app.domain.tools.builtin.jina_reader_handler import JinaReaderTool

    base = tmp_path / "bob"
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)
    store = AssignmentStore(base_dir=str(base))
    store.open("Check the local headlines.")
    store.note_fetch("https://www.wowt.com", chars=60950)

    class FakeResponse:
        text = "Title: Home\n\nMarkdown Content:\n" + "fresh page body " * 20
        headers: dict = {}

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)

    result = await JinaReaderTool().execute(
        {"base_path": str(base)}, url="https://www.wowt.com", refresh=True
    )
    assert result["success"] is True
    assert "cached" not in result
    assert "fresh page body" in result["content"]


async def test_a_notebook_that_cannot_be_read_never_stops_a_fetch(tmp_path, monkeypatch):
    """A lookup that fails means "just fetch it" — the opposite of the write path's loud
    refusal, and for the same reason: a fetch is what the caller asked for."""
    import httpx

    from app.domain.tools.builtin.jina_reader_handler import JinaReaderTool

    base = tmp_path / "bob"
    (base / "assignments").mkdir(parents=True)
    (base / "assignments" / "broken.json").write_text("{ not json", encoding="utf-8")

    class FakeResponse:
        text = "Title: Home\n\nMarkdown Content:\n" + ("local news body. " * 40)
        headers: dict = {}

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    result = await JinaReaderTool().execute({"base_path": str(base)}, url="https://www.wowt.com")
    assert result["success"] is True and "cached" not in result


# ── the cap and the "nothing usable" verdict (2026-10-13) ─────────────────


def test_the_cap_keeps_head_and_tail_and_says_so():
    from app.domain.tools.builtin.jina_reader_handler import DEFAULT_MAX_CHARS, _capped

    page = "HEADLINE-" + ("x" * 100_000) + "-FOOTER"
    shown, truncated = _capped(page, DEFAULT_MAX_CHARS)
    assert truncated is True
    assert shown.startswith("HEADLINE-")
    assert shown.endswith("-FOOTER"), "the tail is kept — bylines and dates live there"
    assert len(shown) < len(page)
    assert "truncated by jina_reader" in shown
    assert f"{len(page):,} characters in total" in shown, "the TRUE size is named"
    assert "fetch a NARROWER" in shown, "and it says what to do about it"

    small, was_truncated = _capped("short page", DEFAULT_MAX_CHARS)
    assert small == "short page" and was_truncated is False


def test_a_tracking_pixel_is_not_a_source():
    """The live specimen: omaha.com returned 142 characters — a 1x1 image — and the turn that
    followed carried it."""
    from app.domain.tools.builtin.jina_reader_handler import _unusable_reason

    pixel = (
        "Title: https://match.adsrvr.org/track/cmf/google\n\n"
        "URL Source: https://www.omaha.com/\n\n"
        "Markdown Content:\nA 1x1 image, likely be a tracking pixel.\n"
    )
    reason = _unusable_reason(pixel)
    assert reason is not None
    assert "1x1 image" in reason or "characters of content" in reason


def test_a_big_page_that_says_it_has_nothing_is_not_a_source():
    """The other live specimen: a 137,930-character 'Page unavailable' — fetched, carried, and
    re-billed by the turn that followed."""
    from app.domain.tools.builtin.jina_reader_handler import _unusable_reason

    page = "Title: Page unavailable\n\nURL Source: https://apnews.com/x\n\nMarkdown Content:\n"
    page += "Page unavailable\n" + ("furniture " * 12_000)
    assert "page unavailable" in _unusable_reason(page)


def test_a_real_page_is_usable():
    from app.domain.tools.builtin.jina_reader_handler import _unusable_reason

    page = (
        "Title: Omaha News, Weather and Sports\n\nURL Source: https://www.ketv.com\n\n"
        "Markdown Content:\n## Omaha firefighters extinguish house fire\n\n" + ("Story text. " * 40)
    )
    assert _unusable_reason(page) is None


def test_a_short_but_real_page_is_still_usable():
    """The calibration, pinned: the first cut of the verdict used 200 characters and refused a
    legitimate 152-character page (caught by the handler's own signals test). A thin page is
    not an empty one — the markers catch the pages that SAY they have nothing."""
    from app.domain.tools.builtin.jina_reader_handler import USABLE_BODY_CHARS, _unusable_reason

    thin = "Title: x\n\nMarkdown Content:\n" + ("ordinary page text " * 8)
    assert len(thin.split("Markdown Content:\n", 1)[1].strip()) < 200
    assert _unusable_reason(thin) is None
    assert USABLE_BODY_CHARS == 80


async def test_the_handler_caps_what_it_hands_the_model(tmp_path, monkeypatch):
    import httpx

    from app.domain.tools.builtin.jina_reader_handler import DEFAULT_MAX_CHARS, JinaReaderTool

    class FakeResponse:
        text = (
            "Title: A big front page\n\nURL Source: https://example.com\n\nMarkdown Content:\n"
            + ("headline line\n" * 7_000)
        )
        headers: dict = {}

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    result = await JinaReaderTool().execute({"base_path": str(tmp_path)}, url="https://example.com")
    assert result["success"] is True
    assert result["truncated"] is True
    assert len(result["content"]) <= DEFAULT_MAX_CHARS + 400      # the notice
    assert result["content_length"] > DEFAULT_MAX_CHARS, "the true size is still reported"
    assert "truncated by jina_reader" in result["content"]

    # an admin can raise it per tool config
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    bigger = await JinaReaderTool().execute(
        {"base_path": str(tmp_path), "max_chars": 200_000}, url="https://example.com"
    )
    assert "truncated" not in bigger


async def test_the_handler_refuses_an_unusable_page(tmp_path, monkeypatch):
    import httpx

    from app.domain.tools.builtin.jina_reader_handler import JinaReaderTool

    body = "Title: x\n\nURL Source: https://example.com\n\nMarkdown Content:\nPage not found\n"

    class FakeResponse:
        text = body
        headers: dict = {}

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    result = await JinaReaderTool().execute(
        {"base_path": str(tmp_path)}, url="https://example.com/gone"
    )
    assert result["success"] is False
    assert result["error_type"] == "UnusableContent"
    assert "content" not in result, "nothing usable means nothing to bill"
    # and the capture hook records nothing (a junk page is not a source)
    from app.domain.agents.assignments import fetch_facts

    assert fetch_facts(result) is None


def test_the_notebook_records_the_true_size_of_a_capped_page():
    """A capped fetch returns head+tail under `content` and the real size under
    `content_length` — the notebook must not claim the page was 24,000 characters."""
    from app.domain.agents.assignments import fetch_facts

    facts = fetch_facts({
        "success": True,
        "url": "https://www.wowt.com",
        "content": "head…\n\n[… truncated by jina_reader: 60,950 characters in total …]\n\n…tail",
        "content_length": 60950,
        "truncated": True,
    })
    assert facts["chars"] == 60950
    assert "truncated by jina_reader" in facts["excerpt"]


def test_an_empty_body_is_not_recorded_as_a_source():
    from app.domain.agents.assignments import fetch_facts

    assert fetch_facts({"url": "https://example.com", "content": "", "content_length": 0}) is None


# ── the prompt block ───────────────────────────────────────────────────────


def test_the_prompt_block_is_silent_with_nothing_open(tmp_path, monkeypatch):
    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)
    assert build_assignments_block("bob") is None          # no workspace at all
    AssignmentStore(workspace_key="bob").open(GOAL)         # an open assignment, no notes yet
    block = build_assignments_block("bob")
    assert block is not None and GOAL in block
    assert "open-assignment" in block, "the block says how to work the notebook"


# ── the tools ──────────────────────────────────────────────────────────────


async def test_the_tools_walk_the_whole_workflow(tmp_path):
    from app.domain.tools.builtin.assignment_handler import (
        AddNoteTool, CloseAssignmentTool, OpenAssignmentTool, ReadAssignmentTool,
    )

    config = {"base_path": str(tmp_path / "bob")}

    opened = await OpenAssignmentTool().execute(config, goal=GOAL)
    assert opened["success"] and opened["resumed"] is False
    assert opened["digest"] and GOAL in opened["digest"]

    noted = await AddNoteTool().execute(
        config, text="the ECB held rates at 2%", source="https://ecb.europa.eu"
    )
    assert noted["success"] and noted["verified"] == "the ECB held rates at 2%"
    assert noted["count"] == 1

    digest = await ReadAssignmentTool().execute(config)
    assert digest["success"] and "https://ecb.europa.eu" in digest["digest"]
    assert digest["assignments"][0]["id"] == opened["assignment"]

    full = await ReadAssignmentTool().execute(config, full=True)
    assert full["notes"][0]["text"] == "the ECB held rates at 2%"

    closed = await CloseAssignmentTool().execute(config, result="a quiet ECB day")
    assert closed["success"] and closed["status"] == "closed" and closed["remaining_open"] == []

    # a note after closing has nowhere to go, and says so rather than inventing an assignment
    orphan = await AddNoteTool().execute(config, text="too late")
    assert orphan["success"] is False and orphan["error_type"] == "not_found"


async def test_a_tool_without_a_workspace_says_so():
    from app.domain.tools.builtin.assignment_handler import OpenAssignmentTool

    result = await OpenAssignmentTool().execute({}, goal=GOAL)
    assert result["success"] is False
    assert "no workspace" in result["error"]
    assert result["error_type"] == "validation"


async def test_an_invalid_id_is_a_classified_validation_error(tmp_path):
    from app.domain.tools.builtin.assignment_handler import ReadAssignmentTool

    result = await ReadAssignmentTool().execute({"base_path": str(tmp_path)}, assignment_id="../etc")
    assert result["success"] is False
    assert result["error_type"] == "validation"


def test_the_registry_carries_the_four_notebook_tools():
    from app.domain.tools.registry import init_default_registry

    slugs = set(init_default_registry().get_all_slugs())
    assert {"open-assignment", "add-note", "read-assignment", "close-assignment"} <= slugs


def test_the_notebook_tools_are_on_by_default():
    """A notebook only some agents can reach would be a notebook that stays empty (update-state
    was called 6 times in 120 turns precisely because writing was a choice nobody made)."""
    from app.domain.tools.capabilities import tier_for

    for capability in ("file-write", "file-read"):
        assert tier_for(capability) == "gras"


def test_the_stored_document_is_json_an_operator_can_read(tmp_path):
    store = AssignmentStore(base_dir=tmp_path)
    store.open(GOAL)
    store.add_note("readable on purpose")
    path = tmp_path / "assignments" / "the-leading-economic-headline-for-europe.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["goal"] == GOAL and doc["notes"][0]["text"] == "readable on purpose"


# ── the automatic half (2026-10-13): the fetch records itself ──────────────


def test_fetch_facts_reads_a_reader_payload():
    from app.domain.agents.assignments import fetch_facts

    facts = fetch_facts({
        "success": True,
        "url": "https://www.ketv.com",
        "content": "Title: Omaha News, Weather and Sports\n\nURL Source: https://www.ketv.com\n\nbody…",
        "chars": 26994,
    })
    assert facts["url"] == "https://www.ketv.com"
    assert facts["chars"] == 26994
    assert facts["title"] == "Omaha News, Weather and Sports"
    assert facts["excerpt"].startswith("Title: Omaha News")


def test_fetch_facts_ignores_what_is_not_a_fetch():
    from app.domain.agents.assignments import fetch_facts

    # a SEARCH is not a source read
    assert fetch_facts({"success": True, "query": "omaha news", "results_count": 10}) is None
    # a url with no body tells us nothing to record
    assert fetch_facts({"url": "https://example.com"}) is None
    # a handler that returns prose
    assert fetch_facts("some text result") is None
    assert fetch_facts(None) is None
    # chars without content still records the source (the dedupe fact)
    assert fetch_facts({"url": "https://a.example", "chars": 12})["chars"] == 12


def test_a_fetch_captures_itself_into_the_runs_notebook(tmp_path, monkeypatch):
    from app.domain.agents.assignments import capture_fetch

    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    assert capture_fetch("bob", "Check the local headlines.", "https://www.ketv.com",
                         chars=26994, title="KETV", excerpt="headlines…") is True

    store = AssignmentStore(workspace_key="bob")
    assignment = store.current()
    assert assignment["goal"] == "Check the local headlines."
    assert store.sources_seen() == ["https://www.ketv.com"]

    # THE SAME REQUEST RESUMES THE SAME NOTEBOOK — that is what makes a re-fetch visible
    assert capture_fetch("bob", "Check the local headlines.", "https://www.wowt.com",
                         chars=60986) is True
    assert len(store.all_assignments()) == 1
    assert store.sources_seen() == ["https://www.ketv.com", "https://www.wowt.com"]

    # and the next turn's prompt carries it, source list and all
    block = build_assignments_block("bob")
    assert block is not None and "https://www.wowt.com" in block and "already gathered" in block


def test_a_different_request_gets_its_own_notebook(tmp_path, monkeypatch):
    from app.domain.agents.assignments import capture_fetch

    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)
    capture_fetch("bob", "Check the local headlines.", "https://a.example", chars=10)
    capture_fetch("bob", "What is the ECB doing?", "https://b.example", chars=10)

    store = AssignmentStore(workspace_key="bob")
    assert len(store.all_assignments()) == 2
    # the CURRENT one is the most recently written — the second request's
    assert store.current()["goal"] == "What is the ECB doing?"


def test_a_goalless_capture_needs_an_open_assignment(tmp_path, monkeypatch):
    from app.domain.agents.assignments import capture_fetch

    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)
    assert capture_fetch("bob", "", "https://a.example", chars=10) is False
    assert AssignmentStore(workspace_key="bob").all_assignments() == []

    AssignmentStore(workspace_key="bob").open("an existed assignment")
    assert capture_fetch("bob", "", "https://a.example", chars=10) is True
    assert AssignmentStore(workspace_key="bob").sources_seen() == ["https://a.example"]


def test_a_broken_notebook_never_breaks_the_turn(tmp_path, monkeypatch):
    """The capture is bookkeeping: it must fail quietly, not turn a working fetch into a dead
    turn (the rule the state store's loud refusal exists for — but for a WRITE, from the loop,
    there is no one to tell; it logs and the turn carries on)."""
    from app.domain.agents.assignments import capture_fetch

    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)
    folder = tmp_path / "bob" / "assignments"
    folder.mkdir(parents=True)
    (folder / "check-the-local-headlines.json").write_text("{ not json", encoding="utf-8")

    assert capture_fetch("bob", "Check the local headlines.", "https://a.example", chars=1) is False


def test_the_router_hook_captures_fetches_and_skips_the_rest(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from app.api.v1.chat.router import _capture_gathered
    from app.domain.agents.assignments import AssignmentStore

    monkeypatch.setattr("app.domain.agents.workspace.AGENTS_ROOT", tmp_path)

    context = SimpleNamespace(
        agent=SimpleNamespace(workspace_key="bob"),
        session_id=99,
        turn_goal="Check the local headlines.",
    )
    results = [
        SimpleNamespace(success=True, tool_slug="jina_reader", result={
            "url": "https://www.ketv.com", "content": "Title: KETV\n\nbody", "chars": 26994}),
        SimpleNamespace(success=True, tool_slug="duckduckgo", result={
            "query": "omaha news", "results_count": 10}),
        SimpleNamespace(success=True, tool_slug="datetime", result={"success": True}),
        SimpleNamespace(success=False, tool_slug="jina_reader", result=None),
    ]
    assert _capture_gathered(context, results) == 1

    store = AssignmentStore(workspace_key="bob")
    assert store.sources_seen() == ["https://www.ketv.com"]

    # an agent with no workspace records nothing (and does not raise)
    assert _capture_gathered(
        SimpleNamespace(agent=SimpleNamespace(workspace_key=None), session_id=1, turn_goal="x"),
        results,
    ) == 0
