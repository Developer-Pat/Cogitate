"""The agent's beat sheets — the co-authoring store + tool.

What matters:

- the parse keeps a parenthesised item whole (the commas inside
  commentary are not item separators) and rejoins wrapped entries;
- the add/remove round-trips: what a call returns is what the next
  read sees (no drift between the read-back and the disk);
- a remove that matches nothing is a LOUD error, never a quiet no-op —
  silently editing the user's beat is worse than refusing;
- the `updated:` stamp moves, and nothing else in the sheet is
  disturbed (the prose, the other lists, the sources).
"""

import sys

sys.path.insert(0, "backend")

import pytest

SHEET = """# Beat Sheet — Middle East, Vox Populi

lens: Vox Populi
languages: ar, fa, he, tr
updated: 2026-01-01

## Purpose

The Middle East through its own press — what people there are
reading about themselves, in their own languages.

## Interests

Priorities, not limits — judgment decides what goes in and what stays out.

- Subjects: the war (Iran/Israel, both sides' press), regional
  politics, the US role in the region
- People: the region's leaders as they surface in the news
- Places: the Middle East — Iran, Israel/Palestine, the Gulf, the
  Levant, Turkey

## Sources

- Al Jazeera (pan-Arab, Arabic) — https://www.aljazeera.net
- Haaretz (left-liberal, Hebrew) — https://www.haaretz.co.il

Notes: some outlets block direct fetches.
"""


@pytest.fixture
def store(tmp_path):
    from app.domain.agents.agent_beats import AgentBeatStore

    beats = tmp_path / "news-beats"
    beats.mkdir()
    (beats / "middle-east-vox.md").write_text(SHEET, encoding="utf-8")
    return AgentBeatStore(base_dir=tmp_path)


class TestParse:
    def test_parenthesised_item_is_whole(self, store):
        lists = store.read()["lists"]
        assert lists["subjects"] == [
            "the war (Iran/Israel, both sides' press)",
            "regional politics",
            "the US role in the region",
        ]

    def test_wrapped_entries_rejoin(self, store):
        # "the Gulf, the / Levant, Turkey" spans two lines
        assert store.read()["lists"]["places"] == [
            "the Middle East — Iran",
            "Israel/Palestine",
            "the Gulf",
            "the Levant",
            "Turkey",
        ]

    def test_sources_parse(self, store):
        assert len(store.read()["sources"]) == 2


class TestEditing:
    def test_add_then_read_sees_it(self, store):
        out = store.add_items(None, "people", ["Janet Yellen"])
        assert "Janet Yellen" in out["verified"]
        assert store.read()["lists"]["people"] == [
            "the region's leaders as they surface in the news",
            "Janet Yellen",
        ]

    def test_remove_then_read_sees_it_gone(self, store):
        store.add_items(None, "subjects", ["economics"])
        out = store.remove_items(None, "subjects", ["economics"])
        assert "economics" not in out["verified"]
        assert store.read()["lists"]["subjects"] == [
            "the war (Iran/Israel, both sides' press)",
            "regional politics",
            "the US role in the region",
        ]

    def test_round_trip_is_stable(self, store):
        """The read-back of a call == the next read (no drift)."""
        out = store.add_items(None, "subjects", ["economics"])
        assert out["verified"] == store.read()["lists"]["subjects"]

    def test_removing_an_absent_item_refuses(self, store):
        with pytest.raises(ValueError, match="Not in the subjects list"):
            store.remove_items(None, "subjects", ["macroeconomics"])

    def test_unknown_list_refuses(self, store):
        with pytest.raises(ValueError, match="Unknown list"):
            store.add_items(None, "vibes", ["x"])

    def test_the_stamp_moves_and_prose_survives(self, store):
        before = store.read()["purpose"]
        store.add_items(None, "people", ["Someone"])
        text = (store.root / "middle-east-vox.md").read_text(encoding="utf-8")
        assert "updated: 2026-01-01" not in text
        assert store.read()["purpose"] == before
        assert "Notes: some outlets block direct fetches." in text

    def test_sources_add_and_remove(self, store):
        out = store.add_items(None, "sources", ["TRT (state, Turkish) — https://www.trt.net.tr"])
        assert out["count"] == 3
        out = store.remove_items(None, "sources", ["TRT (state, Turkish) — https://www.trt.net.tr"])
        assert out["count"] == 2

    def test_several_sheets_need_a_name(self, tmp_path):
        from app.domain.agents.agent_beats import AgentBeatStore
        beats = tmp_path / "news-beats"
        beats.mkdir()
        (beats / "a.md").write_text(SHEET, encoding="utf-8")
        (beats / "b.md").write_text(SHEET, encoding="utf-8")
        s = AgentBeatStore(base_dir=tmp_path)
        with pytest.raises(ValueError, match="Several beat sheets"):
            s.read()
        assert s.read("b")["name"] == "b"


class TestTool:
    async def test_tool_edits_and_returns_the_read_back(self, tmp_path):
        from app.domain.tools.builtin.agent_beat_handler import UpdateBeatTool

        beats = tmp_path / "news-beats"
        beats.mkdir()
        (beats / "middle-east-vox.md").write_text(SHEET, encoding="utf-8")

        tool = UpdateBeatTool()
        assert tool.slug == "update-beat"
        assert tool.needs_workspace is True

        res = await tool.execute(
            config={"base_path": str(tmp_path)},
            list="people", action="add", items=["Janet Yellen"],
        )
        assert res["success"] is True
        assert res["verified"] == [
            "the region's leaders as they surface in the news",
            "Janet Yellen",
        ]

    async def test_tool_refuses_without_a_workspace(self):
        from app.domain.tools.builtin.agent_beat_handler import UpdateBeatTool

        res = await UpdateBeatTool().execute(
            config={}, list="people", action="add", items=["x"],
        )
        assert res["success"] is False
        assert "no workspace" in res["error"]

    async def test_tool_surfaces_a_bad_remove_as_an_error(self, tmp_path):
        from app.domain.tools.builtin.agent_beat_handler import UpdateBeatTool

        beats = tmp_path / "news-beats"
        beats.mkdir()
        (beats / "middle-east-vox.md").write_text(SHEET, encoding="utf-8")

        res = await UpdateBeatTool().execute(
            config={"base_path": str(tmp_path)},
            list="subjects", action="remove", items=["macroeconomics"],
        )
        assert res["success"] is False
        assert res["error_type"] == "validation"
