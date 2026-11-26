"""THE INGEST AS ITS OWN PROCESS.

An ingest is minutes to hours of blocking embedding calls. Run inside the API it had two costs,
both measured on the test box: it held the event loop (fixed by moving the per-document work to a
worker thread) and it **died whenever the backend cycled** — a `--reload`, a restart, a deploy — with
the status record left saying `running`, which then locked `POST /rag/ingest` out for ever.

As a child process it owns its own lifetime: the API spawns it, reads the same record it writes, and
can kill it by group. Nothing here is a second implementation — it resolves the `embeddings`
capability exactly as the router does and calls the one `RagIngestService.run`.

Usage (the API spawns this; a human may too):

    python -m app.domain.rag.ingest_cli --job-id rag-ingest-1 --mode incremental \
        --dirs wiki/entities,wiki/help

Exit codes: 0 completed, 1 failed, 143 cancelled (SIGTERM).
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from typing import List, NoReturn, Optional

from app.core.database import AsyncSessionLocal
from app.domain.providers.embeddings import resolve_embedding_service
from app.domain.rag.service import (
    INGESTION_DIRS,
    RagIngestService,
    _read_status_file,
    _write_status_file,
)

logger = logging.getLogger(__name__)

EXIT_COMPLETED = 0
EXIT_FAILED = 1
EXIT_CANCELLED = 143


def _known_roots() -> List[str]:
    """The roots a run may name — the code's own list, so a child cannot be talked into elsewhere."""
    return list(INGESTION_DIRS)


def _finish_record(job_id: str, status: str, error: Optional[str]) -> None:
    """Write a final word for OUR job, and never for somebody else's.

    A cancel and a crash both land here; the job id is the guard, because the record may already
    belong to a later run by the time this process notices it is being stopped.
    """
    record = _read_status_file()
    if record is None or record.job_id != job_id:
        return
    if record.status not in ("running", "starting"):
        return
    record.status = status
    record.completed_at = datetime.now(timezone.utc)
    record.error = error
    record.progress = None
    _write_status_file(record)


def _install_sigterm(job_id: str) -> None:
    """SIGTERM means 'stop now', and it has to LEAVE A WORD — silence is what locked the page."""

    def _on_term(signum: int, frame: object) -> NoReturn:
        logger.warning("ingest %s cancelled by signal %s", job_id, signum)
        _finish_record(job_id, "cancelled", "cancelled: the process was told to stop")
        # LEAVE NOW, do not unwound the loop. `SystemExit` here waits for the default executor's
        # threads to finish their in-flight embedding call — which is what a cancel is trying to
        # escape. The record is already written, so there is nothing left to make tidy: measured, a
        # child asked to stop kept running 33 s later until the API escalated to SIGKILL.
        os._exit(EXIT_CANCELLED)

    signal.signal(signal.SIGTERM, _on_term)


async def _run(args: argparse.Namespace) -> None:
    async with AsyncSessionLocal() as session:
        embedding = await resolve_embedding_service(session)
    if not embedding.resolved:
        raise RuntimeError(embedding.report())

    await RagIngestService().run(
        mode=args.mode,
        index_type=args.index_type,
        embedding=embedding,
        dirs=args.dirs or None,
        job_id=args.job_id,
    )


def _parse(argv: Optional[List[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="ingest_cli", description="Run a RAG ingest as its own process.")
    parser.add_argument("--job-id", required=True, help="the id the API already wrote into the record")
    parser.add_argument(
        "--mode",
        default="incremental",
        choices=["incremental", "full", "force-reingest"],
        help="incremental skips what is already indexed; full re-reads everything; force ignores timestamps",
    )
    parser.add_argument("--index-type", default="docs", choices=["docs", "code"])
    parser.add_argument(
        "--dirs",
        default="",
        help="comma-separated ingestion roots; empty means the code's own six",
    )
    args = parser.parse_args(argv)
    roots = [root.strip() for root in args.dirs.split(",") if root.strip()]
    unknown = [root for root in roots if root not in _known_roots()]
    if unknown:
        parser.error(f"unknown ingestion root(s): {', '.join(unknown)} (known: {', '.join(_known_roots())})")
    args.dirs = roots
    return args


def main(argv: Optional[List[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    args = _parse(argv)
    _install_sigterm(args.job_id)

    try:
        asyncio.run(_run(args))
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — the record must say WHY, not just that it stopped
        logger.exception("ingest %s failed", args.job_id)
        _finish_record(args.job_id, "failed", f"{type(exc).__name__}: {exc}")
        return EXIT_FAILED
    return EXIT_COMPLETED


if __name__ == "__main__":
    sys.exit(main())
