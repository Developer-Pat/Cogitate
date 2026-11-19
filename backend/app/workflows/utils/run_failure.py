"""THE RUN-LEVEL FAILURE STATEMENT — the ONE gate and wording for a failed workflow run.

A workflow RUN carries the service it resolved at its start (`RunMetadata.llm_resolution`, G4-F2)
so a failure can name the offender. THREE things must all hold before anybody is named, and each
is a thing G4-F5 forbids inventing:

1. the run CARRIED a resolution (a run that predates G4-F2 carries none);
2. the resolution NAMED somebody (a capability that resolved to nothing has no offender);
3. **the exception came from the PROVIDER LAYER** (`is_provider_failure`). This is the one that
   is easy to miss and the reason this gate exists: every run carries a resolution now, while a
   run can fail for anything — a node's bug, a closed database. Naming the service a run resolved
   for a failure that never reached the service is a false name, and the two run-level failures
   this was built against are exactly that shape.

When all three hold the reason is the provider's own words, labelled as theirs — the same clause
the title path uses. Otherwise the run names NOBODY and the surface shows its raw error.

WHY THIS LIVES IN `workflows/utils/` AND NOT IN THE ROUTER: the gate is the run's, not the
endpoint's. A NODE's failure (a workflow node that catches its own LLM error and returns error
state) holds the same carried resolution and the same exception, so it must ask the same question
and get the same answer — one gate, one wording, every surface. The router cannot be imported by
a node (the router imports the nodes to build the graphs), so the gate sits in a leaf module both
can reach. The wording itself is the domain's (`domain/providers/failure_statement.py`).
"""

from __future__ import annotations

from typing import Optional


def run_failure_statement(metadata, error) -> Optional[str]:
    """The ONE wording for a failed run — from the run's carried resolution + the exception.

    Returns `None` when the run names nobody (any of the three conditions above missing), which
    is the honest answer the surfaces fall back to their raw error on.
    """
    from app.domain.providers.failure_statement import (
        FailureSubject,
        failure_sentence_for_subject,
        is_provider_failure,
        provider_reported,
    )

    resolution = getattr(metadata, "llm_resolution", None)
    if resolution is None:
        return None
    if resolution.provider is None and resolution.model is None:
        # resolved to nothing (disabled / none): there is no offender to name
        return None
    if not is_provider_failure(error):
        # NOT the provider's failure — the run resolves a service, but this exception never
        # reached it. Naming it here would finger an innocent service (G4-F5).
        return None
    return failure_sentence_for_subject(
        FailureSubject(
            model=resolution.model,
            provider=resolution.provider,
            reason=provider_reported(error),
        )
    )
