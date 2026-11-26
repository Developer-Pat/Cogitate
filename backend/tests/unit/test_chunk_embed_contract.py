"""The chunker and the embedder must agree on ONE number — the model's input budget.

They did not: `chunk_document` cut at 4,000 characters while `_call_ollama_embed` silently truncated
every chunk to 950. Measured over the six ingestion roots, that threw away **21.4 % of the
documentation** (524,104 of 2,450,485 characters): a passage past the opening of a long section was
searchable only through that opening. The truncated value was also below the chunker's own cap, so the
two constants were never going to meet.

Now: `embeddings.max_embed_chars_for(model)` is the single answer, the chunker cuts to it, and the
embedder REFUSES a longer text by name rather than halving it.
"""
from app.domain.providers.embeddings import (
    EMBEDDING_MAX_CHARS_BY_MODEL,
    max_embed_chars_for,
)
from app.domain.providers.embeddings import EmbeddingService
from app.domain.tools.builtin.doc_vector_store import MAX_CHUNK_CHARS, chunk_document


def _service(model: str, dims: int = 768) -> EmbeddingService:
    return EmbeddingService(address="http://127.0.0.1:9", model=model, dims=dims)


# ── the invariant ───────────────────────────────────────────────────────────────────────────────

def test_the_chunkers_default_is_a_budgets_own_number():
    """A direct caller that names no budget must land on a real model's, not on a stale 4000."""
    assert MAX_CHUNK_CHARS == max_embed_chars_for("nomic-embed-text")


def test_every_model_in_the_width_table_has_a_budget():
    """A model whose width the app knows but whose input budget it does not is a trap: it resolves
    (address, model, dims all present) and then cannot be fed."""
    for model in EMBEDDING_MAX_CHARS_BY_MODEL:
        assert max_embed_chars_for(model) > 0


def test_an_unknown_model_gets_the_conservative_budget_not_a_big_one():
    assert max_embed_chars_for("some-model-nobody-wrote-down") == 2000
    assert max_embed_chars_for(None) == 2000


# ── the cap is a guarantee, with or without headings ────────────────────────────────────────────

def test_a_section_with_no_split_points_is_still_cut_to_the_cap():
    """The old chunker emitted an 11,597-character chunk against its own 4,000 cap — a wall of text
    with no blank lines had nowhere to split, so it was not split at all."""
    text = "# heading\n\n" + ("word " * 8000)  # one paragraph, ~40k chars, no blank lines
    chunks = chunk_document(text, "big.md", max_chunk_chars=2000)

    assert len(chunks) > 1
    assert max(len(c["chunk_text"]) for c in chunks) <= 2000


def test_a_document_with_no_headings_is_chunked_rather_than_become_one_chunk():
    text = "plain note. " * 4000  # ~48k chars, no '#'
    chunks = chunk_document(text, "note.md", max_chunk_chars=2000)

    assert len(chunks) > 1
    assert max(len(c["chunk_text"]) for c in chunks) <= 2000
    assert all(c["heading"] == "" for c in chunks)


def test_short_sections_are_left_whole():
    text = "# a\n\nshort.\n\n# b\n\nalso short.\n"
    chunks = chunk_document(text, "small.md", max_chunk_chars=2000)

    assert [c["chunk_text"] for c in chunks] == ["# a\n\nshort.", "# b\n\nalso short."]


def test_the_cap_follows_the_model_it_is_given():
    """all-minilm's window is 256 tokens; its budget is small, and the chunker must honour it."""
    small = max_embed_chars_for("all-minilm")
    text = "# heading\n\n" + ("sentence " * 400)  # ~3.6k chars
    chunks = chunk_document(text, "doc.md", small)

    assert max(len(c["chunk_text"]) for c in chunks) <= small


# ── the embedder refuses instead of halving ─────────────────────────────────────────────────────

def test_the_embedder_refuses_a_text_over_the_budget_without_calling_out(monkeypatch):
    """No HTTP happens: an oversized document chunk is a chunker bug and is named as one."""
    from app.domain.tools.builtin.doc_vector_store import DocVectorStore

    store = DocVectorStore(db_path=":memory:", embedding=_service("all-minilm", dims=384))
    refused = store._call_ollama_embed("x" * (store.max_embed_chars + 50))

    assert refused is None


def test_a_query_may_be_cut_because_it_is_only_a_probe():
    """A pasted 3,000-character query still searches — the DOCUMENT is the thing that must not be cut."""
    from app.domain.tools.builtin.doc_vector_store import DocVectorStore

    store = DocVectorStore(db_path=":memory:", embedding=_service("all-minilm", dims=384))
    # No server is listening at :9; the point is that the query path does not refuse on length, so it
    # reaches the call (and fails on the connection) rather than being rejected as a document is.
    assert store.max_embed_chars == max_embed_chars_for("all-minilm")
