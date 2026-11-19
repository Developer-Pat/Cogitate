"""A template's own config — ONE reader for the two paths that seed a run.

A workflow run's initial state is built in **two** places: the API's ``POST /execute`` and the
scheduler's trigger path. They disagreed. The API loaded the template's config from the database
and seeded it on the state (``"config": template_config``); the scheduler seeded ``"config": None``.
The monitor family reads its **feeds** out of that channel — so every SCHEDULED run resolved zero
feeds, fetched nothing, and reported a clean cycle (``Items: 0 · Errors: 0``), for weeks, because a
monitor's failures are declared *tolerant* and never mark a run (see ``error_handling/grades.py``).

The fix is therefore not "teach the scheduler to load the config" — that is how the first repair
went, and it left the second door broken. It is **one reader, both doors**: the config a run is
seeded with cannot depend on which door it came through.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


def shared_db_path() -> Path:
    """The shared database the templates live in (resolved, never hardcoded)."""
    from app.core.config import Paths, get_settings

    return Paths.from_settings(get_settings()).shared_db


def _parse_json(raw: Any, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


def load_template_config(
    template_id: str,
    db_path: Optional[Path] = None,
) -> Tuple[dict, list]:
    """The template's ``config`` and ``tags`` — ``({}, [])`` when they cannot be read.

    **Never raises.** A missing database, a missing row or unreadable JSON is logged and answered
    with empties: a run that cannot read its template's config still has to start. What it must
    NOT do is start *quietly* — which is why the monitor family now reports "no feeds resolved"
    when the config it was seeded with turns out to be empty.
    """
    path = Path(db_path) if db_path is not None else shared_db_path()
    if not path.exists():
        logger.warning("template config: database file not found at %s", path)
        return {}, []

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT config, tags FROM workflow_templates WHERE id = ?",
                (template_id,),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("template config: could not read %s (%s)", template_id, exc)
        return {}, []

    if row is None:
        logger.warning("Template %s not found in database", template_id)
        return {}, []

    config = _parse_json(row["config"], {})
    tags = _parse_json(row["tags"], [])
    if not isinstance(config, dict):
        config = {}
    if not isinstance(tags, list):
        tags = []

    logger.info("📋 Loaded template config for %s: %s", template_id, config)
    logger.info("🏷️  Template tags for %s: %s", template_id, tags)
    return config, tags
