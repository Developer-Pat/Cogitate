#!/usr/bin/env python3
"""Seed the system-audit workflow template.

Idempotent — skips the row if it exists (safe to re-run).

Deliberately NO TRIGGER — the user's directive is "wire it but don't fire it — don't put it on a
schedule." The audit runs when the user requests it (a manual run), when Exa triggers it after making
changes (the exa-triggered path), or once at boot (the startup hook).

Usage:
    python3 scripts/core/seed_system_audit_template.py
"""

import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "cogitate.db")

TEMPLATE = {
    "id": "system-audit",
    "name": "System Consistency Audit",
    "description": (
        "Runs the system consistency audit (agents, collections, "
        "workflows — every dangling reference) and VERIFIES the "
        "result by re-running it (the read-back node). On-demand: "
        "the user, Exa after changes, or startup. NOT scheduled."
    ),
    "category": "monitoring",
    "version": "1.0.0",
    "author": "system",
    "tags": '["audit","consistency","system","verify"]',
    "workflow_type": "workflow",
    "config": "{}",
    "is_public": 1,
    "is_customizable": 1,
    "inputs": "{}",
    "kind_id": "system-audit",
}


def main() -> int:
    if not os.path.exists(DB):
        print(f"❌ DB not found: {DB}")
        return 1

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    row = cur.execute(
        "SELECT description, kind_id, category FROM workflow_templates WHERE id = ?",
        (TEMPLATE["id"],),
    ).fetchone()
    if row:
        # Self-healing: refresh the description + kind + category if drifted
        if (row[0] != TEMPLATE["description"] or row[1] != TEMPLATE["kind_id"]
                or row[2] != TEMPLATE["category"]):
            cur.execute(
                "UPDATE workflow_templates SET description = ?, kind_id = ?, "
                "category = ?, updated_at = datetime('now') WHERE id = ?",
                (TEMPLATE["description"], TEMPLATE["kind_id"],
                 TEMPLATE["category"], TEMPLATE["id"]),
            )
            print(f"  ~ template {TEMPLATE['id']}: refreshed")
        else:
            print(f"  · template {TEMPLATE['id']}: SKIP (unchanged)")
    else:
        cur.execute(
            """INSERT INTO workflow_templates
               (id, name, description, category, version, author, tags,
                workflow_type, config, is_public, is_customizable, inputs,
                kind_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (TEMPLATE["id"], TEMPLATE["name"], TEMPLATE["description"],
             TEMPLATE["category"], TEMPLATE["version"], TEMPLATE["author"],
             TEMPLATE["tags"], TEMPLATE["workflow_type"], TEMPLATE["config"],
             TEMPLATE["is_public"], TEMPLATE["is_customizable"], TEMPLATE["inputs"],
             TEMPLATE["kind_id"]),
        )
        print(f"  ✓ template {TEMPLATE['id']}: inserted")

    # the workflow_kinds CATALOG MIRROR (2026-08-20): the registry
    # is the source of truth, but the templates API joins this table
    # for kind_name — a missing mirror row shows kind_name=None.
    kr = cur.execute(
        "SELECT name FROM workflow_kinds WHERE id = ?", (TEMPLATE["kind_id"],)
    ).fetchone()
    if kr:
        print(f"  · workflow_kinds {TEMPLATE['kind_id']}: SKIP (mirrored)")
    else:
        cur.execute(
            """INSERT INTO workflow_kinds
               (id, name, description, builder_key, product_type, created_at)
               VALUES (?, ?, ?, ?, ?, datetime('now'))""",
            (TEMPLATE["kind_id"], TEMPLATE["kind_id"], TEMPLATE["description"],
             "system_audit_graph", "report"),
        )
        print(f"  ✓ workflow_kinds {TEMPLATE['kind_id']}: mirrored")

    conn.commit()
    conn.close()
    print("  (no trigger — deliberately NOT scheduled)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
