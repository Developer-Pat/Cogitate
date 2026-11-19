"""
Seed script: populate the frontend_agent_packages table with test/dummy agents.

This script:
1. Creates several test agent packages for development and testing
2. Includes a "hello world" agent and a "researcher" agent
3. Demonstrates versioning with parent_version_id lineage

Usage:
    uv run python scripts/core/seed_agent_packages.py

    # Dry run (show what would be created without writing)
    uv run python scripts/core/seed_agent_packages.py --dry-run

    # Force re-seed (delete existing and recreate)
    uv run python scripts/core/seed_agent_packages.py --force
"""

import argparse
import asyncio
import logging
import sys

# Add project root to path
sys.path.insert(0, ".")

from sqlalchemy import text
from app.core.database import AsyncSessionLocal, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Test Agent Code Definitions ─────────────────────────────────────────────

HELLO_WORLD_CODE = '''"""Hello World agent — minimal Nucleus test package."""

def run(context):
    """Return a greeting based on the input context."""
    name = context.get("name", "World")
    greeting = context.get("greeting", "Hello")
    return {
        "message": f"{greeting}, {name}!",
        "input": context,
        "agent": "hello_world_v1",
    }
'''

RESEARCHER_CODE = '''"""Researcher agent — demonstrates context processing."""

def run(context):
    """Process a research query and return structured results."""
    query = context.get("query", "")
    max_results = context.get("max_results", 5)

    # Simulate research processing
    topics = [t.strip() for t in query.split(",") if t.strip()]

    results = []
    for i, topic in enumerate(topics[:max_results]):
        results.append({
            "topic": topic,
            "relevance": 0.95 - (i * 0.05),
            "summary": f"Found information about {topic}",
        })

    return {
        "query": query,
        "results": results,
        "total_found": len(results),
        "agent": "researcher_v1",
    }
'''

FORMATTER_CODE = '''"""Formatter agent — transforms data into structured output."""

def run(context):
    """Format input data into a structured report."""
    data = context.get("data", {})
    template = context.get("template", "default")

    if template == "summary":
        output = {
            "title": data.get("title", "Untitled"),
            "summary": data.get("summary", ""),
            "key_points": data.get("key_points", []),
        }
    elif template == "detailed":
        output = {
            "title": data.get("title", "Untitled"),
            "content": data.get("content", ""),
            "metadata": {
                "author": data.get("author", "unknown"),
                "date": data.get("date", ""),
                "version": data.get("version", "1.0"),
            },
        }
    else:
        output = {"formatted": str(data)}

    return {
        "template": template,
        "output": output,
        "agent": "formatter_v1",
    }
'''

# ── Seed Data ───────────────────────────────────────────────────────────────

SEED_PACKAGES = [
    {
        "name": "hello_world",
        "role": "greeting",
        "version": "1.0.0",
        "status": "active",
        "system_prompt": "You are a friendly greeting agent. Say hello and be helpful.",
        "code": HELLO_WORLD_CODE,
        "tools_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name to greet"},
                "greeting": {"type": "string", "description": "Greeting to use"},
            },
        },
        "package_metadata": {"description": "Minimal test agent for Nucleus harness", "author": "system"},
    },
    {
        "name": "researcher",
        "role": "research",
        "version": "1.0.0",
        "status": "active",
        "system_prompt": "You are a research assistant. Find and summarize information.",
        "code": RESEARCHER_CODE,
        "tools_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Research query"},
                "max_results": {"type": "integer", "description": "Max results"},
            },
        },
        "package_metadata": {"description": "Research agent for information retrieval", "author": "system"},
    },
    {
        "name": "formatter",
        "role": "formatting",
        "version": "1.0.0",
        "status": "active",
        "system_prompt": "You are a formatting agent. Structure data into reports.",
        "code": FORMATTER_CODE,
        "tools_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "object", "description": "Input data"},
                "template": {"type": "string", "description": "Output template"},
            },
        },
        "package_metadata": {"description": "Data formatting and report generation", "author": "system"},
    },
    # ── Experimental / test variants ──────────────────────────────────────
    {
        "name": "hello_world_experimental",
        "role": "greeting",
        "version": "2.0.0-alpha",
        "status": "experimental",
        "system_prompt": "Experimental greeting agent with enhanced features.",
        "code": HELLO_WORLD_CODE.replace('"Hello"', '"Howdy"'),
        "tools_schema": None,
        "package_metadata": {"description": "Experimental variant with different greeting", "experiment_group": "A"},
    },
    {
        "name": "researcher_legacy",
        "role": "research",
        "version": "0.9.0",
        "status": "deprecated",
        "system_prompt": "Legacy research agent (use researcher instead).",
        "code": RESEARCHER_CODE,
        "tools_schema": None,
        "package_metadata": {"description": "Legacy version, use researcher_v1 instead", "deprecation_reason": "superseded"},
    },
]


async def seed_packages(dry_run: bool = False, force: bool = False) -> int:
    """
    Seed agent packages into the database.

    Args:
        dry_run: If True, only log what would be created
        force: If True, delete existing packages first

    Returns:
        Number of packages created
    """
    await init_db()

    async with AsyncSessionLocal() as db:
        created = 0

        if force:
            # Delete all existing packages
            result = await db.execute(text("SELECT id, name FROM frontend_agent_packages"))
            existing = list(result.all())
            for row in existing:
                if dry_run:
                    logger.info("[DRY RUN] Would delete: %s (id=%d)", row.name, row.id)
                else:
                    await db.execute(text("DELETE FROM frontend_agent_packages WHERE id = :id"), {"id": row.id})
            if not dry_run:
                await db.flush()
                logger.info("Deleted %d existing packages", len(existing))

        for pkg in SEED_PACKAGES:
            # Check if already exists
            result = await db.execute(
                text("SELECT id FROM frontend_agent_packages WHERE name = :name"),
                {"name": pkg["name"]},
            )
            existing = result.scalar_one_or_none()
            if existing:
                logger.info(
                    "Skipping '%s' (already exists, id=%d)",
                    pkg["name"], existing,
                )
                continue

            if dry_run:
                logger.info(
                    "[DRY RUN] Would create: %s (role=%s, version=%s, status=%s)",
                    pkg["name"], pkg["role"], pkg["version"], pkg["status"],
                )
                created += 1
            else:
                try:
                    import json

                    await db.execute(
                        text("""
                            INSERT INTO frontend_agent_packages
                                (name, role, version, status, system_prompt, code,
                                 tools_schema, package_metadata)
                            VALUES
                                (:name, :role, :version, :status, :system_prompt, :code,
                                 :tools_schema, :package_metadata)
                        """),
                        {
                            "name": pkg["name"],
                            "role": pkg["role"],
                            "version": pkg["version"],
                            "status": pkg["status"],
                            "system_prompt": pkg["system_prompt"],
                            "code": pkg["code"],
                            "tools_schema": json.dumps(pkg["tools_schema"]) if pkg["tools_schema"] else None,
                            "package_metadata": json.dumps(pkg["package_metadata"]) if pkg["package_metadata"] else "{}",
                        },
                    )
                    logger.info(
                        "Created: %s (role=%s, version=%s, status=%s)",
                        pkg["name"], pkg["role"], pkg["version"], pkg["status"],
                    )
                    created += 1
                except Exception as e:
                    logger.warning("Failed to create '%s': %s", pkg["name"], e)

        if not dry_run:
            await db.commit()

        return created


def main():
    parser = argparse.ArgumentParser(
        description="Seed agent packages into the database"
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show what would be created without writing",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Delete existing packages before seeding",
    )
    args = parser.parse_args()

    created = asyncio.run(seed_packages(dry_run=args.dry_run, force=args.force))

    if args.dry_run:
        logger.info("[DRY RUN] Would create %d package(s)", created)
    else:
        logger.info("Seeded %d package(s)", created)


if __name__ == "__main__":
    main()
