"""
The test-catalog checker - the CLI for ``app.domain.testing.catalog_check``.

Reads the LIVE catalog (what the page renders), reports every description that
carries project history or is not a complete sentence, and exits 1 so a sweep can
gate on it.

    python3 scripts/testing/check_test_catalog.py
    python3 scripts/testing/check_test_catalog.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# The backend package is one level up (the house pattern for scripts/).
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.domain.testing.catalog import build_catalog          # noqa: E402
from app.domain.testing.catalog_check import check_catalog    # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument(
        "--strict", action="store_true",
        help="also gate on BOILERPLATE (a true description that says nothing about the tests)",
    )
    args = parser.parse_args()

    catalog = build_catalog()
    if not catalog.get("available", True):
        result = {"available": False, "reason": catalog.get("reason", "no test tree"),
                  "checked": 0, "findings": []}
    else:
        findings = check_catalog(catalog)
        checked = len(catalog.get("tests", []))
        result = {"available": True, "checked": checked, "findings": findings,
                  "clean": checked - len({f["path"] for f in findings})}

    if args.json:
        print(json.dumps(result, indent=2))
        gating = [x for x in result.get("findings", [])
                  if args.strict or x["class"] != "BOILERPLATE"]
        return 1 if gating else 0

    if not result.get("available", True):
        print(f"The catalog is not available: {result.get('reason')}")
        return 0

    findings = result["findings"]
    # BOILERPLATE is a QUALITY signal, not a defect: the description is true, it just
    # says little. Counting it in the exit code would fail a sweep over prose, so by
    # default it is reported and does not gate. `--strict` makes it gate for a caller
    # that wants the stricter reading.
    gating = [x for x in findings if args.strict or x["class"] != "BOILERPLATE"]
    print(f"checked {result['checked']} descriptions; {len(findings)} finding(s)"
          f" ({len(findings) - len(gating)} advisory)")
    if not findings:
        print("every description is a complete sentence with no project history.")
        return 0

    by_class: dict[str, list[dict[str, str]]] = {}
    for f in findings:
        by_class.setdefault(f["class"], []).append(f)
    for cls in sorted(by_class):
        items = by_class[cls]
        print(f"\n{cls}  ({len(items)})")
        for f in items[:40]:
            print(f"   {f['path']}\n      {f['text']}\n      -> {f['detail']}")
        if len(items) > 40:
            print(f"   ... and {len(items) - 40} more")
    return 1 if gating else 0


if __name__ == "__main__":
    raise SystemExit(main())
