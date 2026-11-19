"""Character faces for new agents.

Agents are characters (faces + names). A new agent — created from
scratch OR applied from a template — should not arrive looking like an
existing one: a clone that wears the original's face is confusing in
exactly the way a clone should not be.

The curated pool lives git-tracked at `assets/agent-images/` (the
canonical home) and is served from `data/profile_images/` at
`/static/<name>.png` (the seeding is `scripts/core/seed_agent_images.py`).
This module picks from the pool.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def pick_agent_face(used: Iterable[str] | None = None) -> str | None:
    """Pick a character face for a new agent.

    Prefers a face NO other agent wears; when the pool is spent it
    reuses the first one rather than leaving the agent faceless (a
    visible duplicate beats an invisible agent — and the user can set
    a different image in the profile).

    Args:
        used: the profile_image_url values already in use.

    Returns:
        A `/static/<name>.png` url, or None when the pool is missing.
    """
    from app.core.config import Paths, get_settings

    pool: Path = Paths.from_settings(get_settings()).agent_images_dir
    if not pool.is_dir():
        return None

    available = sorted(p.name for p in pool.glob("*.png"))
    if not available:
        return None

    used_names = {Path(u).name for u in (used or []) if u}
    free = [n for n in available if n not in used_names]
    return f"/static/{(free or available)[0]}"
