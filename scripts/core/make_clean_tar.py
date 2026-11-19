#!/usr/bin/env python3
"""Create a clean tar.gz snapshot of the Cogitate project.

Excludes regenerable/bloat content (venvs, node_modules, caches,
logs, DBs, backups, env files, archives) so the archive is pure
source + wiki + configs + notes.

Usage:
    python3 scripts/core/make_clean_tar.py [output_name]

Defaults: ~/Cogitate-cleaned-YYYY-MM-DD.tar.gz
Example:  python3 scripts/core/make_clean_tar.py Cockpit-source
          (an absolute name lands there — pathlib drops the ~/ prefix)

The exclude list is the backup ritual's verified one (`project-backup-routine` skill). Two entries are
easy to get backwards, so each is named here with the reason it holds:

  * `backend/data/piper/` IS excluded. The TTS voices + onnxruntime are a download-on-setup artifact of
    ~233M that a restored install re-fetches — the manifest has to say so.
  * `.hermes.md` is NOT excluded; only the `.hermes/` DIRECTORY is. The file is the TRACKED
    project-context file, while the directory is local agent state (state.db, lsp caches and bin).
"""

import datetime
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent

EXCLUDES = [
    # history + dependencies: rebuildable, and the git.bundle is the history artifact
    "./.git",
    "./.venv", "./backend/.venv",
    "./node_modules", "./frontend/node_modules",
    "./frontend/dist", "./frontend/.vite",
    # caches: all regenerable
    "./.mypy_cache", "./backend/.mypy_cache",
    "./.ruff_cache", "./backend/.ruff_cache",
    "./.pytest_cache", "./backend/.pytest_cache",
    "__pycache__", "*.pyc",
    # runtime output
    "./logs", "./backend/logs", "*.log",
    # local agent state (state.db 55M, lsp 71M, bin 22M). NOTE: `.hermes.md` is
    # the tracked project-context file and stays IN the archive — only the dir goes.
    "./.hermes", "./.exa-workspace",
    # databases: the live one belongs to the db artifact, the rest are regenerable.
    # The globs cover the -wal/-shm siblings too (a stray `-wal` is 5M of nothing).
    "*.db", "*.db-wal", "*.db-shm",
    "checkpoints.db*", "cogitate.db*",
    # archives + staged deletions
    "./backups", "./_backups", "./trash", "./_trash", "./_archive", "./_research",
    "db/*.bak",
    # secrets + local pids/markers (a restore reconfigures its environment).
    # The `.env*` patterns are ANCHORED and globbed: `--exclude=.env` matches the
    # exact name only, so a `.env.bak` / `.env.local` sibling rode into the archive
    # — measured on the 2026-09-25 round, which is why the patterns carry the `*`.
    # `.env.example` templates fall under the same pattern; they are tracked, so the
    # git bundle still carries them.
    "./.env*", "./frontend/.env*", "./backend/.env*", "./.hermes/.env*",
    "./.pids", "./.app_pids", "./.roo", "./tmp", "./.vscode", "nohup.out",
    # THE 233M LESSON: download-on-setup TTS voices + onnxruntime. A restored
    # install re-fetches them, so the manifest has to say so.
    "./backend/data/piper",
]


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else f"Cogitate-cleaned-{datetime.date.today():%Y-%m-%d}.tar.gz"
    if not name.endswith(".tar.gz"):
        name += ".tar.gz"
    out = Path(name) if name.startswith("/") else Path.home() / name

    cmd = ["tar", "-czf", str(out)]
    for excl in EXCLUDES:
        cmd += ["--exclude", excl]
    cmd += ["."]

    print(f"Creating clean archive: {out}")
    print(f"Excludes: {len(EXCLUDES)} patterns")
    result = subprocess.run(cmd, cwd=PROJECT, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        sys.exit(1)

    size = out.stat().st_size / 1024 / 1024
    print(f"✅ {out} ({size:.1f}M)")
    print("   Compare against the previous round's size — a 2-5x jump means an")
    print("   exclusion slipped (list the biggest members inside the archive).")


if __name__ == "__main__":
    main()
