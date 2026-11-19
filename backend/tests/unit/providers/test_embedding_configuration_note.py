"""`configuration_note` — what a surface says when a configured model and the INDEX do not agree.

The embedding-configuration ruling, **options C then A** (2026-10-12,
`wiki/issues/resolved/embedded-service-literals/embedding-configuration-does-not-reach-a-running-process.md`). C made the surfaces tell the
truth about a process that would not pick a change up; **A made the change reach the process** — the
capability write path resets the two RAG stores — so the restart sentence C introduced is RETIRED, and
the one thing still worth saying is what no reset can repair:

- `_declared_width` / `declared_index_width` read the width the vec table was CREATED at, because
  `init_db` declares it with ``IF NOT EXISTS`` — an index keeps the width it was born with;
- so a model of a DIFFERENT width leaves the index behind and it has to be rebuilt, which is what
  `configuration_note` returns;
- everything else answers ``None``: nothing configured, nothing resolved, or a model the index can hold.
"""

from __future__ import annotations

from app.domain.providers.embeddings import (
    EmbeddingService,
    configuration_note,
    declared_width_of,
    width_mismatch_report,
)


def _service(
    model: str = "nomic-embed-text",
    dims: int = 768,
    address: str = "http://127.0.0.1:11434",
) -> EmbeddingService:
    """A resolved service of this test's own — the three facts, nothing else."""
    return EmbeddingService(address=address, model=model, dims=dims)


def test_nothing_is_said_when_the_model_matches_the_index() -> None:
    """The common case: a 768-wide model and a 768-wide index agree, so no surface has to warn."""
    assert configuration_note(_service(), 768) is None


def test_nothing_is_said_when_the_install_has_configured_no_model() -> None:
    """An unconfigured install answers `report()`, not this — there is no width to disagree with."""
    assert configuration_note(EmbeddingService(), 768) is None


def test_nothing_is_said_when_there_is_no_index_yet() -> None:
    """Nothing has created a table, so there is nothing to leave behind."""
    assert configuration_note(_service(), None) is None


def test_a_width_change_is_reported_with_the_index_as_the_subject() -> None:
    """A reset does not repair this, so the sentence names the INDEX and the rebuild it needs."""
    resolved = _service(model="mxbai-embed-large", dims=1024)
    note = configuration_note(resolved, 768)

    assert note == width_mismatch_report(768, resolved)
    assert "the index is 768 wide" in (note or "")
    assert "re-run the ingest" in (note or "")
    assert "nothing was changed" in (note or "")


def test_the_restart_vocabulary_is_gone() -> None:
    """The sentence A retired, asserted ABSENT so a later edit cannot quietly bring it back.

    It was true while C stood alone and it is false now that the write path resets the stores: a saved
    model reaches the running process on its next use.
    """
    from app.domain.providers import embeddings as emb

    assert not hasattr(emb, "RESTART_NOTE")
    assert "after a restart" not in (configuration_note(_service("mxbai-embed-large", 1024), 768) or "")


def test_the_declared_width_is_parsed_from_the_ddl_or_refused() -> None:
    """ONE parser for the vec table's width: two readers (the store, the status) ask the same question."""
    assert declared_width_of(
        "CREATE VIRTUAL TABLE vec_docs USING vec0(\n  embedding float[768] distance_metric=cosine\n)"
    ) == 768
    assert declared_width_of("CREATE VIRTUAL TABLE vec_code USING vec0(embedding float[1024])") == 1024
    # A table this app did not write, or none at all — never a guessed 768.
    assert declared_width_of("CREATE TABLE doc_chunks (id INTEGER PRIMARY KEY)") is None
    assert declared_width_of(None) is None
