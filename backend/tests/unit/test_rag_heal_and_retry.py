"""HEAL, the retry, and the clock that stops when the machine sleeps.

Three defects from the first full run (2026-11-27):

- **`s_per_chunk` was wall clock.** A 11.3 h host suspend made an 8.7 h run report 19.99 h and a rate of
  15.20 instead of 6.62 — and that rate prices every later estimate.
- **Twelve chunks were lost to a flat 30 s deadline**, every one the heaviest chunk of its document.
- **A skipped chunk was invisible**: `files_failed` 0, the document "processed", and `incremental` never
  revisits it because the file's mtime did not move.
"""
import httpx
import pytest

from app.domain.providers.embeddings import EmbeddingService
from app.domain.rag import service as rag_service
from app.domain.tools.builtin import doc_vector_store as store_module
from app.domain.tools.builtin.doc_vector_store import DocVectorStore


# ── the clock ───────────────────────────────────────────────────────────────────────────────────

def test_active_seconds_follow_the_monotonic_clock(monkeypatch):
    """`time.monotonic()` on Linux is CLOCK_MONOTONIC — it stops while the machine is suspended."""
    monkeypatch.setattr(rag_service.time, "monotonic", lambda: 1_000.0)
    assert rag_service._active_seconds_since(940.0) == 60.0


def test_the_service_measures_with_that_helper_not_the_wall_clock():
    """A source-level guard: the run's elapsed must not be a `datetime.now() - started_at` delta."""
    import inspect

    source = inspect.getsource(rag_service.RagIngestService.run)
    assert "_active_seconds()" in source
    assert "(datetime.now(timezone.utc) - started_at)" not in source


# ── the deadline and the retry ─────────────────────────────────────────────────────────────────

class _RecordingClient:
    """Stands in for httpx.Client: records the deadline, then raises (or answers) as told."""

    last_timeout = None
    calls = 0
    behaviour = "raise"

    def __init__(self, *args, **kwargs):
        type(self).last_timeout = kwargs.get("timeout")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def post(self, *args, **kwargs):
        type(self).calls += 1
        raise httpx.TimeoutException("timed out")


@pytest.fixture()
def store():
    return DocVectorStore(
        db_path=":memory:",
        embedding=EmbeddingService(address="http://127.0.0.1:9", model="nomic-embed-text", dims=768),
    )


def test_the_deadline_grows_with_the_text(store, monkeypatch):
    """A 2 000-character chunk is ~21 s of model work idle and over 30 under load — a flat 30 lost 12."""
    _RecordingClient.calls = 0
    monkeypatch.setattr(store_module.httpx, "Client", _RecordingClient)

    store._call_ollama_embed("x" * 2000)

    assert _RecordingClient.last_timeout == pytest.approx(50.0)  # 2000 chars x 25 ms


def test_a_short_text_keeps_the_thirty_second_floor(store, monkeypatch):
    _RecordingClient.calls = 0
    monkeypatch.setattr(store_module.httpx, "Client", _RecordingClient)

    store._call_ollama_embed("short")

    assert _RecordingClient.last_timeout == pytest.approx(30.0)


def test_a_timeout_is_retried_exactly_once(store, monkeypatch):
    _RecordingClient.calls = 0
    monkeypatch.setattr(store_module.httpx, "Client", _RecordingClient)

    assert store._call_ollama_embed("text") is None
    assert _RecordingClient.calls == 2  # one attempt, one retry — not a loop


# ── heal ───────────────────────────────────────────────────────────────────────────────────────

class _HealProbeStore:
    """A store that already 'holds' a given number of chunks per path."""

    def __init__(self, counts=None):
        self.counts = dict(counts or {})
        self.indexed: list[str] = []
        self.max_embed_chars = 2000

    def init_db(self):
        return None

    def document_chunk_counts(self):
        return dict(self.counts)

    def index_document(self, rel_path, content, on_chunk=None):
        self.indexed.append(rel_path)
        return 1

    def remove_stale_documents(self, paths, roots=None):
        return 0


@pytest.fixture()
def corpus(tmp_path, monkeypatch):
    root = tmp_path / "install"
    (root / "wiki" / "help").mkdir(parents=True)
    for name in ("one.md", "two.md"):
        (root / "wiki" / "help" / name).write_text(f"# {name}\n\none paragraph of text\n", encoding="utf-8")
    monkeypatch.setattr(rag_service, "STATUS_FILE", str(tmp_path / "status.json"))
    monkeypatch.setattr(store_module, "_rebuild_doc_index_json", lambda *a, **k: None)
    service = rag_service.RagIngestService()
    service._project_root = root
    return service


async def _run_heal(service, monkeypatch, counts):
    probe = _HealProbeStore(counts)
    monkeypatch.setattr(DocVectorStore, "get_instance", classmethod(lambda cls, **kwargs: probe))
    await service.run(
        mode="heal",
        embedding=EmbeddingService(address="http://127.0.0.1:9", model="nomic-embed-text", dims=768),
        dirs=["wiki/help"],
    )
    return probe


async def test_heal_re_indexes_only_the_document_that_disagrees(corpus, monkeypatch):
    """`two.md` holds one chunk too few — that is a skipped chunk, and it is the ONLY thing to redo."""
    probe = await _run_heal(corpus, monkeypatch, {"wiki/help/one.md": 1, "wiki/help/two.md": 0})

    assert probe.indexed == ["wiki/help/two.md"]


async def test_heal_does_nothing_when_the_index_agrees(corpus, monkeypatch):
    probe = await _run_heal(corpus, monkeypatch, {"wiki/help/one.md": 1, "wiki/help/two.md": 1})

    assert probe.indexed == []
    status = rag_service.RagIngestService.get_status()
    assert status is not None and status.status == "completed" and status.result is not None
    assert status.result.files_processed == 0


async def test_heal_treats_a_document_the_index_never_saw_as_missing(corpus, monkeypatch):
    """A path absent from the index is a hole, not a match — `0` is the wrong answer for "unknown"."""
    probe = await _run_heal(corpus, monkeypatch, {"wiki/help/one.md": 1})

    assert probe.indexed == ["wiki/help/two.md"]
