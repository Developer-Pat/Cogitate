"""A narrowed run must not sweep the roots it was told to leave alone.

Measured before this guard existed: indexing `wiki/entities` + `wiki/help` removed **845 chunks**
belonging to `wiki/dev-notes` and `wiki/atlas`, because the stale sweep compared the index against
what THIS run discovered — and "not discovered" read as "gone from disk". The index went from 130
documents / 933 chunks to 50 / 321 on a run that was supposed to ADD two roots.
"""
import pytest

from app.domain.providers.embeddings import EmbeddingService
from app.domain.tools.builtin.doc_vector_store import DocVectorStore


def _resolved() -> EmbeddingService:
    return EmbeddingService(address="http://127.0.0.1:9", model="nomic-embed-text", dims=768)


@pytest.fixture()
def store(tmp_path):
    s = DocVectorStore(db_path=str(tmp_path / "idx.db"), embedding=_resolved())
    s.init_db()
    db = s._get_connection()
    for path in ("wiki/help/a.md", "wiki/help/b.md", "wiki/atlas/deep/c.md"):
        db.execute(
            "INSERT INTO doc_chunks (source_path, chunk_text, checksum) VALUES (?, ?, ?)",
            (path, "text", path),
        )
    db.commit()
    return s


def test_a_narrowed_run_leaves_the_other_roots_alone(store):
    """`b.md` is gone from disk inside the run's own root; the atlas is not this run's business."""
    removed = store.remove_stale_documents({"wiki/help/a.md"}, roots=["wiki/help"])

    assert removed == 1
    assert sorted(store.list_indexed_paths()) == ["wiki/atlas/deep/c.md", "wiki/help/a.md"]


def test_without_roots_the_old_whole_corpus_behaviour_stands(store):
    """A caller that names no roots (the tests, an early caller) keeps the old contract."""
    removed = store.remove_stale_documents({"wiki/help/a.md"})

    assert removed == 2
    assert sorted(store.list_indexed_paths()) == ["wiki/help/a.md"]


def test_a_root_prefix_does_not_match_a_lookalike(store):
    """`wiki/help` must not claim `wiki/helpful.md` — the prefix ends at a path separator."""
    db = store._get_connection()
    db.execute(
        "INSERT INTO doc_chunks (source_path, chunk_text, checksum) VALUES (?, ?, ?)",
        ("wiki/helpful.md", "text", "x"),
    )
    db.commit()

    store.remove_stale_documents({"wiki/help/a.md"}, roots=["wiki/help"])

    assert "wiki/helpful.md" in store.list_indexed_paths()
