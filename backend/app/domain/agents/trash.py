"""THE AGENT SHELF — where a deleted agent's workspace goes.

THE MOVE IS THE DELETE. A recoverable delete moves the workspace onto this shelf
(`trash/agents/<workspace_key>-<stamp>/`) and marks the row; nothing is copied,
so restoring is one move back. The MECHANICS live here, beside the agent
lifecycle that uses them; the shelf's ADAPTER (`app.domain.trash.adapters.agents`)
is what puts them behind the trash contract.

THE ROW IS WHAT MAKES AN ENTRY RESTORABLE. It holds the name and points at the
folder. A folder on this shelf with NO row is RESIDUE — visible, purgeable, and
not restorable, because there is nothing to restore it to.

WHY A SHELF AND NOT A HIDDEN ARCHIVE. The old shape kept deleted workspaces in
`agents/.archived/`, inside the live agents tree and reachable only through a
row. That made the folder invisible the moment its row went away — which is how
thirty of them accumulated unread. The trash is a surface: it has a page, an API
and an owner (a person, or Exa), so what is here is READ.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import Paths

#: The shelf's name — the trash registry key AND its directory. ONE string, so
#: the key and the folder cannot drift.
SHELF = "agents"

#: How many colliding names to try before giving up. A name repeats when an
#: agent is restored and deleted again, so this is generous rather than tight.
_MAX_SUFFIX = 100


def shelf_root() -> Path:
    """The agent shelf, through the locator (never composed at a call site)."""
    return Paths.trash_dir_for(SHELF)


def free_name(root: Path, name: str) -> str:
    """`name`, or `name-2`, `name-3`… when the shelf already holds that name.

    Never overwrite: the folder already here may be all that is left of an
    earlier agent, and silently replacing it would destroy the very thing the
    shelf exists to keep.
    """
    if not (root / name).exists():
        return name
    for n in range(2, _MAX_SUFFIX + 2):
        candidate = f"{name}-{n}"
        if not (root / candidate).exists():
            return candidate
    raise RuntimeError(f"the agent shelf holds {_MAX_SUFFIX} copies of {name}")


def move_to_shelf(workspace: Path, workspace_key: str) -> Path:
    """Move a workspace onto the shelf. Returns where it landed.

    The move is a RENAME on the same filesystem, so nothing is copied and a
    crash mid-way cannot leave half an agent in each place.
    """
    root = shelf_root()
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    destination = root / free_name(root, f"{workspace_key}-{stamp}")
    shutil.move(str(workspace), str(destination))
    return destination


def move_back(archived: Path, workspace_key: str) -> Path:
    """Put a shelved workspace back where the agent lives. ADDITIVE: a live
    folder is never clobbered — the contents merge into it, since the live copy
    may hold work the archive does not.

    ⚠️ THE MERGE MOVES EVERY ITEM. The previous inline version only moved an
    item when the target ALREADY existed, so a restore over a live folder left
    the non-colliding files behind in the archive — a partial restore that read
    as complete. Both branches are handled here.
    """
    from app.domain.agents.workspace import AGENTS_ROOT

    destination = AGENTS_ROOT / workspace_key
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not archived.exists():
        return destination
    if not destination.exists():
        shutil.move(str(archived), str(destination))
        return destination
    for item in archived.iterdir():
        target = destination / item.name
        if target.exists():
            shutil.move(str(item), str(target))
        else:
            shutil.move(str(item), str(destination / item.name))
    return destination
