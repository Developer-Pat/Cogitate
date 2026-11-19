#!/usr/bin/env python3
"""Seed the monitor workflow family: templates + triggers.

Idempotent — skips rows that already exist (safe to re-run).

Usage:
    python3 scripts/core/seed_monitor_templates.py
"""

import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "cogitate.db")

TEMPLATES = [
    {
        "id": "rss-monitor",
        "name": "RSS News Monitor",
        "description": (
            "Hourly news digest: fetches your RSS feeds (no API key), "
            "only new stories (dedup via data/monitor/state.json), "
            "summarized, written to data/monitor/rss-digest-*.md"
        ),
        "category": "monitoring",
        "version": "1.0.0",
        "author": "system",
        "tags": '["monitor","rss","digest"]',
        "workflow_type": "workflow",
        "config": '{"feeds": ["https://arstechnica.com/feed/", "https://hnrss.org/frontpage"], "max_items": 5}',
        "is_public": 1,
        "is_customizable": 1,
        "inputs": '{"feeds": {"type": "array", "description": "RSS feed URLs"}, "max_items": {"type": "integer", "default": 5}}',
    },
    {
        "id": "readiness-check",
        "name": "First-Run Readiness Check",
        "description": (
            "Is my instance ready? Runs the POST health suite (llm, "
            "database, api, config, connectivity) + provider keys + "
            "agents/curated-models. On-demand from TestingDashboard."
        ),
        "category": "monitoring",
        "version": "1.0.0",
        "author": "system",
        "tags": '["monitor","readiness","setup"]',
        "workflow_type": "workflow",
        "config": "{}",
        "is_public": 1,
        "is_customizable": 1,
        "inputs": "{}",
    },
    {
        "id": "market-watch",
        "name": "Market Watch",
        "description": (
            "5-minute price tripwire: keyless CoinGecko fetch, alerts "
            "when the move exceeds your threshold (vs last price in "
            "data/monitor/state.json), written to data/monitor/market-*.md"
        ),
        "category": "monitoring",
        "version": "1.0.0",
        "author": "system",
        "tags": '["monitor","market","crypto"]',
        "workflow_type": "workflow",
        "config": '{"symbol": "bitcoin", "threshold_pct": 2.0}',
        "is_public": 1,
        "is_customizable": 1,
        "inputs": '{"symbol": {"type": "string", "default": "bitcoin"}, "threshold_pct": {"type": "number", "default": 2.0}}',
    },
]

# NOTE: triggers ship DEACTIVATED (is_active=0) — a fresh install
# must never fire workflows the user didn't opt into. The trigger
# control panel (Workflow Execution page) activates them.
TRIGGERS = [
    {
        "id": "monitor-rss-hourly",
        "workflow_id": "rss-monitor",
        "trigger_type": "schedule",
        "config": '{"cron": "0 * * * *", "timezone": "UTC", "enabled": false}',
        "is_active": 0,
        "name": "RSS Monitor: hourly",
        "description": "Fires the RSS digest monitor every hour (opt-in)",
    },
    {
        "id": "monitor-market-5min",
        "workflow_id": "market-watch",
        "trigger_type": "schedule",
        "config": '{"cron": "*/5 * * * *", "timezone": "UTC", "enabled": false}',
        "is_active": 0,
        "name": "Market Watch: 5-min",
        "description": "Fires the market watch monitor every 5 minutes (opt-in)",
    },
]


def main() -> int:
    if not os.path.exists(DB):
        print(f"❌ DB not found: {DB}")
        return 1

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    for t in TEMPLATES:
        row = cur.execute(
            "SELECT description, config FROM workflow_templates WHERE id = ?", (t["id"],)
        ).fetchone()
        if row:
            # Self-healing: refresh the description if it drifted
            # (keeps UI-visible text in sync with the shipped wording)
            if row[0] != t["description"]:
                cur.execute(
                    "UPDATE workflow_templates SET description = ?, updated_at = datetime('now') WHERE id = ?",
                    (t["description"], t["id"]),
                )
                print(f"  ~ template {t['id']}: description refreshed")
            else:
                print(f"  · template {t['id']}: SKIP (unchanged)")
            continue
        cur.execute(
            """INSERT INTO workflow_templates
               (id, name, description, category, version, author, tags,
                workflow_type, config, is_public, is_customizable, inputs,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (t["id"], t["name"], t["description"], t["category"], t["version"],
             t["author"], t["tags"], t["workflow_type"], t["config"],
             t["is_public"], t["is_customizable"], t["inputs"]),
        )
        print(f"  ✓ template {t['id']}: inserted")

    for tr in TRIGGERS:
        exists = cur.execute(
            "SELECT 1 FROM workflow_triggers WHERE id = ?", (tr["id"],)
        ).fetchone()
        if exists:
            print(f"  · trigger {tr['id']}: SKIP (exists)")
            continue
        cur.execute(
            """INSERT INTO workflow_triggers
               (id, workflow_id, trigger_type, config, is_active, name,
                description, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (tr["id"], tr["workflow_id"], tr["trigger_type"], tr["config"],
             tr["is_active"], tr["name"], tr["description"]),
        )
        print(f"  ✓ trigger {tr['id']}: inserted")

    conn.commit()
    conn.close()
    print("✅ monitor templates seeded")
    return 0


if __name__ == "__main__":
    sys.exit(main())
