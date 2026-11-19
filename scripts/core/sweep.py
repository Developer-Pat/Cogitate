#!/usr/bin/env python3
"""
Sweep Script — Comprehensive Error & Warning Detection
=======================================================

Thin entry point that delegates to the sweep package CLI.

Usage (new — subcommands):
    python3 scripts/core/sweep.py                          # Run all checks (default: full)
    python3 scripts/core/sweep.py backend                  # Backend checks only (separate report)
    python3 scripts/core/sweep.py frontend                 # Frontend checks only (separate report)
    python3 scripts/core/sweep.py full                     # All checks (explicit, combined report)
    python3 scripts/core/sweep.py backend --parallel       # Backend checks in parallel
    python3 scripts/core/sweep.py frontend --output report.md
    python3 scripts/core/sweep.py full --roll-baseline

Legacy flags (deprecated — will emit a warning):
    python3 scripts/core/sweep.py --backend-only
    python3 scripts/core/sweep.py --frontend-only
"""

import sys
import os

# Ensure the sweep package is importable when running from scripts/core/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sweep.cli import main

if __name__ == "__main__":
    sys.exit(main())
