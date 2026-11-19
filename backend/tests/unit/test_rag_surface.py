"""The RAG locator resolves the wiki surface, and the ingest tree excludes test artifacts.

- the locator resolves the RAG surface (the canonical paths)
- the whole-wiki ingest surface includes the atlas/help/docs
- the test artifacts (display-tests) are excluded
"""
import pytest

from app.core.config import Paths
from app.domain.rag.service import discover_files


def test_locator_resolves_the_rag_surface():
    assert str(Paths.rag_index_path).endswith("system_docs_vector.db")
    assert str(Paths.code_vector_path).endswith("system_code_vector.db")
    assert str(Paths.rag_status_file).endswith("rag_ingest_status.json")


def test_whole_wiki_surface_discovered():
    files = discover_files()
    rels = [f[1] for f in files]
    # the whole-wiki dirs are in
    for d in ("wiki/atlas", "wiki/help", "wiki/docs", "wiki/entities", "wiki/dev-notes"):
        assert any(r.startswith(d + "/") for r in rels), f"{d} missing from the surface"
    # the test artifacts are out
    assert not any("display-tests" in r for r in rels)
    # the atlas is the bulk of the knowledge surface
    atlas = sum(1 for r in rels if r.startswith("wiki/atlas/"))
    assert atlas > 300, f"atlas too small: {atlas}"


def test_the_status_reads_the_index_the_locator_names(tmp_path, monkeypatch):
    """The health read resolves a RELATIVE `doc_index_path` through the one locator, not `data_dir`.

    It used to join it onto `data_dir`, which turned the default `data/system_docs_vector.db` into
    `<install>/data/data/system_docs_vector.db` — a file that never exists — so an install WITH an
    index was reported as an empty one (zero documents, zero chunks, size 0). Every other reader uses
    the locator; this test goes red the moment the status stops.
    """
    import sqlite3
    from pathlib import Path

    from app.core.config import Paths
    from app.core.system_manager import SystemManagerConfig
    from app.domain.providers.embeddings import EmbeddingService
    from app.domain.rag.service import RagIngestService

    index = tmp_path / "system_docs_vector.db"
    conn = sqlite3.connect(index)
    conn.execute(
        "CREATE TABLE doc_chunks (source_path TEXT, chunk_text TEXT, heading TEXT DEFAULT '', "
        "checksum TEXT DEFAULT '', updated_at TEXT DEFAULT '')"
    )
    conn.executemany(
        "INSERT INTO doc_chunks (source_path, chunk_text) VALUES (?, ?)",
        [("wiki/a.md", "x"), ("wiki/b.md", "y")],
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(Paths, "rag_index_path", index)

    # The config's own value is the RELATIVE default — the case that used to resolve to data/data/…
    config = SystemManagerConfig.defaults()
    assert not Path(config.doc_index_path).is_absolute()

    health = RagIngestService.get_index_health(
        config, EmbeddingService(address="http://127.0.0.1:11434", model="nomic-embed-text", dims=768)
    )

    assert health.indexed_documents == 2
    assert health.total_chunks == 2
    assert health.database_size_bytes > 0
