#!/usr/bin/env python3
"""Provision the external agent's private Hermes home (the CLI shim).

The IMPLEMENTATION lives in `app.domain.external_agent.activation` — the
activation path needs the same provisioning, and two copies of it would drift.
This file exists so the documented command keeps working.

    uv run python scripts/core/provision_exa_home.py

Idempotent: safe to run any time; existing files are preserved. Provider key
VALUES are never printed — only the names of the keys that were written.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))


def main() -> int:
    from app.domain.external_agent.activation import provision_home

    print("Provisioning the Exa home…")
    for line in provision_home():
        print(f"  {line}")
    print("✅ the Exa home is provisioned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
