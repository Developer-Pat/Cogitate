"""What a run would cost — counted where it can be, estimated where it cannot, and labelled.

The Ingestables tab prices a run before starting it. Two numbers come from the filesystem (files, bytes)
and two are estimates (chunks, minutes); the payload says which is which and names the rate it used, so
no surface can present a guess as a promise.
"""
import math

import pytest

from app.domain.rag import service as rag_service


@pytest.fixture()
def corpus(tmp_path, monkeypatch):
    """A root with known file sizes; BASE_DIR is the only thing that has to move."""
    root = tmp_path / "install"
    (root / "wiki" / "help").mkdir(parents=True)
    (root / "wiki" / "entities").mkdir(parents=True)
    (root / "wiki" / "help" / "small.md").write_text("x" * 500, encoding="utf-8")
    (root / "wiki" / "help" / "big.md").write_text("x" * 2000, encoding="utf-8")
    (root / "wiki" / "entities" / "one.md").write_text("y" * 100, encoding="utf-8")
    monkeypatch.setattr(rag_service, "BASE_DIR", root)
    return root


def test_each_root_is_priced_from_the_files_that_are_really_there(corpus):
    priced = rag_service.estimate_ingest(["wiki/help", "wiki/entities"])

    by_dir = {row["dir"]: row for row in priced["dirs"]}
    assert by_dir["wiki/help"]["files"] == 2
    assert by_dir["wiki/entities"]["files"] == 1
    assert by_dir["wiki/help"]["bytes"] == 2500
    assert priced["total"]["files"] == 3
    assert priced["total"]["bytes"] == 2600


def test_chunks_follow_the_calibrated_ratio(corpus):
    priced = rag_service.estimate_ingest(["wiki/help"], rate_s_per_chunk=5.0)

    expected = math.ceil(500 / rag_service.CHARS_PER_CHUNK_ESTIMATE) + math.ceil(
        2000 / rag_service.CHARS_PER_CHUNK_ESTIMATE
    )
    assert priced["dirs"][0]["chunks"] == expected
    assert priced["dirs"][0]["minutes"] == round(expected * 5.0 / 60, 1)


def test_a_measured_rate_is_used_and_named(corpus):
    priced = rag_service.estimate_ingest(["wiki/help"], rate_s_per_chunk=12.5)
    assert priced["rate_s_per_chunk"] == 12.5
    assert priced["rate_source"] == "last run"


def test_no_measurement_yet_is_labelled_as_a_default(corpus):
    priced = rag_service.estimate_ingest(["wiki/help"])
    assert priced["rate_s_per_chunk"] == rag_service.DEFAULT_RATE_S_PER_CHUNK
    assert "default" in priced["rate_source"]


def test_the_payload_says_it_is_an_estimate(corpus):
    """The one field a UI must not drop: the numbers for chunks and minutes are guesses."""
    assert rag_service.estimate_ingest(["wiki/help"])["estimated"] is True


def test_an_empty_root_costs_nothing_and_does_not_raise(corpus):
    """`docs` and `references` are tiny or absent on a fresh install — a zero row, not an error."""
    priced = rag_service.estimate_ingest(["wiki/docs"])
    assert priced["dirs"][0]["files"] == 0
    assert priced["dirs"][0]["minutes"] == 0.0


async def test_the_estimator_ignores_a_heal_runs_rate(tmp_path, monkeypatch):
    """A heal re-indexes the documents that DISAGREE — the worst of them (11.79 s a chunk measured
    against 6.62 for the whole corpus). Pricing a full run from it overstates by 80 %."""
    from datetime import datetime, timezone

    from app.api.v1.rag import router as rag_router
    from app.domain.rag.schemas import IngestResult, IngestStatusFile

    record = IngestStatusFile(
        job_id="rag-ingest-heal",
        status="completed",
        mode="heal",
        started_at=datetime.now(timezone.utc),
        pid=1,
        result=IngestResult(
            files_discovered=9,
            files_processed=9,
            files_failed=0,
            total_chunks=94,
            elapsed_seconds=1107.8,
            s_per_chunk=11.79,
        ),
    )
    monkeypatch.setattr(rag_router, "_read_status_file", lambda: record)

    priced = await rag_router.estimate_ingest_run(rag_router.IngestEstimateRequest(dirs=None))

    assert priced["rate_s_per_chunk"] == rag_service.DEFAULT_RATE_S_PER_CHUNK
    assert "default" in priced["rate_source"]


async def test_the_estimator_uses_a_whole_corpus_runs_rate(tmp_path, monkeypatch):
    from datetime import datetime, timezone

    from app.api.v1.rag import router as rag_router
    from app.domain.rag.schemas import IngestResult, IngestStatusFile

    record = IngestStatusFile(
        job_id="rag-ingest-full",
        status="completed",
        mode="force-reingest",
        started_at=datetime.now(timezone.utc),
        pid=1,
        result=IngestResult(
            files_discovered=623,
            files_processed=623,
            files_failed=0,
            total_chunks=4734,
            elapsed_seconds=31346.0,
            s_per_chunk=6.62,
        ),
    )
    monkeypatch.setattr(rag_router, "_read_status_file", lambda: record)

    priced = await rag_router.estimate_ingest_run(rag_router.IngestEstimateRequest(dirs=None))

    assert priced["rate_s_per_chunk"] == 6.62
    assert priced["rate_source"] == "last run"
