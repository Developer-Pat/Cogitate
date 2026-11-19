#!/usr/bin/env bash
# Verify a flattened tree the way a stranger meets it.
#
# Usage: scripts/testing/verify_flat_tree.sh /path/to/flat-tree
#
# Checks, in order, and none of them needs this machine's state:
#   1. no secret in any blob at HEAD (the flatten publishes exactly HEAD's tree)
#   2. the path rules (absolute paths, resolver discipline, module specifiers)
#   3. the stale-reference gate (removed system, retired revisions)
#   4. the atlas (frontmatter, stale names, wikilinks, codebase sync, mermaid)
#   5. the generated script catalog matches the scripts (content only — the stamp is
#      the day of the run)
#   6. `uv sync --frozen` from the lockfile
#   7. the fast suite, in that tree
#
# Report only what this run proves: a suite that needs a database copy or a
# `.env` will fail here, and that failure is the finding, not a reason to stop.
set -u

FLAT="${1:-}"
if [ -z "$FLAT" ] || [ ! -d "$FLAT" ]; then
  echo "usage: $0 /path/to/flat-tree" >&2
  exit 2
fi

cd "$FLAT" || exit 2
status=0

run() {
  local label="$1"; shift
  echo "== $label"
  if "$@"; then echo "   OK"; else echo "   FAIL"; status=1; fi
}

run "object scan (HEAD only)"        python3 scripts/testing/scan_objects_for_secrets.py --head-only
run "path checks"                    python3 scripts/testing/precommit_path_checks.py
run "stale references"               python3 scripts/core/check_stale_references.py
# Resolving citations are fine in the historical records and forbidden in current
# docs/code; after a flatten nothing resolves, so the dangling class is checked too.
run "commit citations"               python3 scripts/core/check_commit_references.py --enforce --include-dangling
run "atlas validation"               python3 scripts/core/check_atlas_validation.py
run "dangling links"                 python3 scripts/core/check_dangling_links.py --enforce
run "script catalog"                 python3 scripts/dev/generate_script_catalog.py --check
run "env example"                    python3 scripts/dev/generate_env_example.py --check

echo "== uv sync --frozen"
if uv sync --frozen; then echo "   OK"; else echo "   FAIL"; status=1; fi

echo "== fast suite (in this tree)"
python3 scripts/testing/run_tests.py --group unit --parallel | tail -3

echo
echo "RESULT: $([ $status -eq 0 ] && echo 'STRUCTURAL GATES PASS' || echo 'A GATE FAILED')"
exit $status
