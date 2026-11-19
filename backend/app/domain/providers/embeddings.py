"""THE EMBEDDING SERVICE — *(address, model, dims)* answered in ONE place.

The service-literals arc's ruled second half (`wiki/issues/resolved/embedded-service-literals/embedding-model-and-dims.md`, option C;
the ADDRESS half landed separately). An embedding call needs three facts, and they live in three
different kinds of place — which is exactly why they were previously written down as literals:

| fact | home | why there |
|---|---|---|
| **address** — which server answers | the capability's provider ROW | choosing a server is a DECISION (the arc's rule) |
| **model** — which model runs | the capability's own candidate | the same: a DECISION, and the capability is where it is made |
| **dims** — how wide the vectors are | `EMBEDDING_DIMS_BY_MODEL` | a DEFINITION: `nomic-embed-text` IS 768 wide |

**The dims are the sharper half.** The model and the dims are ONE fact stored as two literals in each
of the six places this replaces — three vector stores, twice inside `doc_reader.py`, the system-manager
defaults and the rag health schema. Nothing derived one from the other, so pointing the app at a
1024-wide model kept writing 768-wide vectors into an index that accepts them: retrieval degraded
instead of erroring. Here the width is READ OFF the model, so the pairing cannot come apart.

**A model whose width this app does not know is NOT resolved.** The alternative — assume 768 because
that is what the last literal said — is how a wrong index gets built quietly. `dims is None` is an
answer, and the caller reports it (`EmbeddingService.report`).

**An unconfigured install REPORTS, and this is the ruling rather than a gap in the build**
(EXA'S INSTALLATION SKILL): the seed ships the capability EMPTY, because
*structure* belongs in a migration and a *value* does not — a migration cannot be declined. The model
is a setup offer the user (or Exa, through its installation skill) accepts, declines or replaces, and
until then the app says `no embedding model: indexing and search are off` instead of shipping a model
nobody chose. The ladder's last rung (the CHAT default row) is skipped for this kind — see
`capabilities.resolve`.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.providers.capabilities import (
    EMBEDDINGS_CAPABILITY_KEY,
    REASON_NONE,
    resolve,
)
from app.domain.providers.config_service import resolve_named_row_endpoint

logger = logging.getLogger(__name__)

# ── The model → width map: a DEFINITION (the arc's refined rule, F3) ─────────────────────────────
#
# A model's output width is a property of the MODEL, not a choice this app makes — the same class as
# a vendor's own catalog or price table. So it is legitimate to write it down, and legitimate ONLY
# here, named, with this note: one entry per model, so the width and the name cannot drift apart.
#
# Adding a model an install wants is ADDING A LINE. A model missing from this map is not resolved
# (the width is reported unknown rather than guessed at 768).
EMBEDDING_DIMS_BY_MODEL: dict[str, int] = {
    # Ollama's local embedding models (the family the app ships a row for)
    "nomic-embed-text": 768,
    "mxbai-embed-large": 1024,
    "all-minilm": 384,
    "snowflake-arctic-embed": 1024,
    # The hosted families, for an install that points a row at one of them
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "embed-english-v3.0": 1024,
    "embed-multilingual-v3.0": 1024,
}

# The one wording an unconfigured install says — quoted by the ruling, so it lives here once and the
# surfaces that report it (`/rag/status`, the ingest refusal) all read it.
NO_EMBEDDING_MODEL = "no embedding model: indexing and search are off"

# WHAT A SURFACE SAYS WHEN THE CONFIGURATION AND THE INDEX DO NOT AGREE.
#
# There is exactly ONE such thing left to say. The restart sentence this block used to carry —
# *"the running process keeps the embedding service it was built with"* — was TRUE when written and is
# NOT any more: the capability write path now resets the two RAG stores (`capabilities.replace_chain`
# → `reset_instance(close=False)`), so a saved model reaches the running process on its next use.
# What no reset and no restart can repair is the INDEX's width, because `init_db` declares the vec
# table with ``IF NOT EXISTS``: an index keeps the width it was born with, so a model of another width
# leaves it behind and it has to be rebuilt. That is what the surfaces say.


def declared_width_of(ddl: Optional[str]) -> Optional[int]:
    """The width in a ``CREATE VIRTUAL TABLE … USING vec0(embedding float[N])`` statement.

    ONE parser, because two readers need it: the store asks its own table (`_declared_width`) and the
    status asks the doc index. A statement this app did not write, or a table with no vec column,
    answers ``None`` — never a guessed 768.
    """
    match = re.search(r"float\[(\d+)\]", ddl or "")
    return int(match.group(1)) if match else None


def width_mismatch_report(index_width: int, service: "EmbeddingService") -> str:
    """The sentence for an index built at one width and a model of another.

    The index has to be rebuilt, and the app says so rather than inserting vectors the table cannot
    hold — the store's own refusal is the enforcement, this is the wording.
    """
    return (
        f"the index is {index_width} wide and '{service.model}' is {service.dims} — "
        f"re-run the ingest to rebuild the index (nothing was changed)"
    )


def configuration_note(
    resolved: "EmbeddingService",
    index_width: Optional[int] = None,
) -> Optional[str]:
    """What must be said when the configured model and the INDEX disagree — or ``None``.

    ``None`` is the common answer and the honest one: nothing configured, nothing resolved, or an index
    whose width matches the model all leave the surfaces with nothing to say.
    """
    if resolved.dims and index_width and index_width != resolved.dims:
        return width_mismatch_report(index_width, resolved)
    return None


@dataclass(frozen=True)
class EmbeddingService:
    """What an embedding consumer needs, as resolved — or the honest account of what is missing.

    ``resolved`` is the gate a consumer checks: all three facts present, or nothing works. A partly
    resolved answer is still USEFUL (`address` without a `model` says the server is configured and
    the model is not), which is why the pieces are reported rather than collapsed into a bool.
    """

    address: Optional[str] = None
    model: Optional[str] = None
    dims: Optional[int] = None
    capability: str = EMBEDDINGS_CAPABILITY_KEY
    reason: str = REASON_NONE

    @property
    def resolved(self) -> bool:
        """Whether an embedding call can be made at all."""
        return bool(self.address and self.model and self.dims)

    def missing(self) -> list[str]:
        """Which of the three facts is absent — the list a report names."""
        absent = []
        if not self.address:
            absent.append("address")
        if not self.model:
            absent.append("model")
        if not self.dims:
            absent.append("dims")
        return absent

    def describe(self) -> str:
        """`ollama/nomic-embed-text (768 dims) at http://localhost:11434` — one line, for a log."""
        if not self.resolved:
            return self.report()
        return f"{self.address} — {self.model} ({self.dims} dims)"

    def report(self) -> str:
        """The statement a surface shows an unconfigured install, saying WHICH half is missing."""
        if self.resolved:
            return self.describe()
        return (
            f"{NO_EMBEDDING_MODEL} (the '{self.capability}' capability is missing "
            f"{', '.join(self.missing())}). Choose a model on the Providers → Capabilities page "
            f"(/providers/capabilities)."
        )


async def resolve_embedding_service(db: AsyncSession) -> EmbeddingService:
    """Resolve the `embeddings` capability to *(address, model, dims)* — or to what is missing.

    Reads the capability's own candidate (the row that serves embeddings, optionally pinning a
    model), takes the address from that ROW through the address half's own lookup, and derives the
    width from the model through :data:`EMBEDDING_DIMS_BY_MODEL`. It never raises and never guesses:
    an unconfigured install gets an unresolved answer whose ``report()`` names the gap.
    """
    # Read at CALL time (not bound at import): a test — and, later, a caller — may point this
    # module at another key, and the resolution must follow it.
    key = EMBEDDINGS_CAPABILITY_KEY
    resolved = await resolve(db, key)
    primary = resolved.primary

    if primary is None or not primary.provider:
        # Nothing configured (the ladder stopped before the chat default row, deliberately — see
        # `capabilities.resolve`), or a candidate that names no provider row: no address, no model.
        return EmbeddingService(capability=key, reason=resolved.reason)

    address = await resolve_named_row_endpoint(db, primary.provider)
    # The resolver's own rule already applied: an explicit model on the candidate WINS over the
    # provider row's `default_model`. Neither present is a legitimate state — a row with a place to
    # choose and no choice yet.
    model = primary.model
    dims = EMBEDDING_DIMS_BY_MODEL.get(model) if model else None
    if model and dims is None:
        logger.warning(
            "the '%s' capability names the model '%s', whose width this app does not know — "
            "reported as unresolved rather than assumed to be 768 wide (add it to "
            "EMBEDDING_DIMS_BY_MODEL if that model embeds)",
            key,
            model,
        )

    return EmbeddingService(
        address=address,
        model=model,
        dims=dims,
        capability=key,
        reason=resolved.reason,
    )
