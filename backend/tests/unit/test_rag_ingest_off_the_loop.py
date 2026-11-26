"""The ingest must not hold the event loop while it embeds a document.

A chunk's embedding is a blocking HTTP call to the embedding server — 16 seconds for a full-size chunk
on a CPU-only box, measured. `RagIngestService.run` is a coroutine, so when that call happens on the
loop's own thread the whole app stops answering for the duration of every file: `/api/v1/health` read
`000` and the RAG page's own 2.5-second status poll could not answer while a real job ran.

The property this pins is not "a helper is used" but **where the work runs**: one document's indexing
happens on a worker thread, and the loop keeps ticking while it does.
"""
import asyncio
import threading
import time

import pytest

from app.core.system_manager import SystemManagerConfig
from app.domain.providers.embeddings import EmbeddingService
from app.domain.rag import service as rag_service
from app.domain.tools.builtin import doc_vector_store as store_module
from app.domain.tools.builtin.doc_vector_store import DocVectorStore


class _ProbeStore:
    """A store whose per-document work takes time, like a real embedding call."""

    def __init__(self) -> None:
        self.threads: list[int] = []
        self.indexed: list[str] = []
        self.chunks_seen_mid_file: list[int] = []

    def init_db(self) -> None:
        return None

    def index_document(self, rel_path: str, content: str, on_chunk=None) -> int:
        self.threads.append(threading.get_ident())
        time.sleep(0.25)  # the blocking part, on purpose
        # Two chunks, reported the way the real store reports them (the ingest's heartbeat). The gap
        # is wider than the record's write throttle so the second one really lands in the file.
        for _ in range(2):
            if on_chunk is not None:
                on_chunk()
            time.sleep(0.6)
        # What the record says WHILE this document is still open — the per-chunk progress fix.
        status = rag_service.RagIngestService.get_status()
        if status is not None and status.progress is not None:
            self.chunks_seen_mid_file.append(status.progress.chunks_done)
        self.indexed.append(rel_path)
        return 1

    def remove_stale_documents(self, paths) -> int:
        return 0


@pytest.fixture()
def corpus(tmp_path, monkeypatch):
    """Two files under an ingestion directory, a status file of our own, and an injected store."""
    root = tmp_path / "install"
    (root / "wiki" / "help").mkdir(parents=True)
    for name in ("one.md", "two.md"):
        (root / "wiki" / "help" / name).write_text(f"# {name}\n\nsome knowledge\n", encoding="utf-8")

    monkeypatch.setattr(rag_service, "STATUS_FILE", str(tmp_path / "status.json"))
    probe = _ProbeStore()
    monkeypatch.setattr(
        DocVectorStore, "get_instance", classmethod(lambda cls, **kwargs: probe)
    )
    monkeypatch.setattr(store_module, "_rebuild_doc_index_json", lambda *a, **k: None)

    service = rag_service.RagIngestService()
    service._project_root = root
    return service, probe


async def _run_with_a_ticker(service, embedding):
    """Run the ingest while counting how often the loop got control."""
    ticks = 0
    stop = asyncio.Event()

    async def ticker() -> None:
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.01)

    task = asyncio.create_task(ticker())
    try:
        await service.run(mode="full", config=SystemManagerConfig.defaults(), embedding=embedding)
    finally:
        stop.set()
        await task
    return ticks


async def test_a_document_is_indexed_off_the_event_loop(corpus):
    service, probe = corpus
    embedding = EmbeddingService(address="http://127.0.0.1:9", model="nomic-embed-text", dims=768)

    loop_thread = threading.get_ident()
    await _run_with_a_ticker(service, embedding)

    assert probe.indexed, "the ingest never reached the store"
    assert all(ident != loop_thread for ident in probe.threads), (
        "a document was indexed ON the event loop's thread — the app is frozen while it embeds"
    )


async def test_the_loop_keeps_ticking_while_a_document_is_indexed(corpus):
    service, probe = corpus
    embedding = EmbeddingService(address="http://127.0.0.1:9", model="nomic-embed-text", dims=768)

    ticks = await _run_with_a_ticker(service, embedding)

    # Two documents at 0.25 s each; a free loop ticks every 10 ms, so the floor is generous on a
    # loaded runner and impossible on a held loop.
    assert ticks > 10, f"the event loop was held while indexing ({ticks} ticks in ~0.5 s)"


async def test_the_job_still_reports_itself_complete(corpus):
    service, probe = corpus
    embedding = EmbeddingService(address="http://127.0.0.1:9", model="nomic-embed-text", dims=768)

    await _run_with_a_ticker(service, embedding)

    status = rag_service.RagIngestService.get_status()
    assert status is not None and status.status == "completed"
    assert status.result is not None and status.result.files_processed == 2
    # Two files, two chunks each: the run's own rate is now recorded for the next run to price with.
    assert status.result.s_per_chunk is not None and status.result.s_per_chunk > 0


async def test_the_record_moves_while_a_document_is_still_open(corpus):
    """A card must not sit at 0 for the length of a document (measured: six minutes)."""
    service, probe = corpus
    embedding = EmbeddingService(address="http://127.0.0.1:9", model="nomic-embed-text", dims=768)

    await _run_with_a_ticker(service, embedding)

    assert probe.chunks_seen_mid_file, "the record was never read mid-document"
    assert max(probe.chunks_seen_mid_file) >= 1, (
        "the record still read 0 chunks while a document was being indexed — progress is per FILE again"
    )
