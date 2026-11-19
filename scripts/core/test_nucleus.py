"""
Quick verification script: test Nucleus harness with seeded agents.

Usage:
    uv run python scripts/core/test_nucleus.py
"""

import asyncio
import json
import logging
import sys

sys.path.insert(0, ".")

from sqlalchemy import text
from app.core.database import AsyncSessionLocal, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def test_nucleus():
    """Test that Nucleus can load and execute agent code from the database."""
    await init_db()

    async with AsyncSessionLocal() as db:
        # ── 1. Verify active packages exist ────────────────────────────────
        result = await db.execute(
            text("SELECT id, name, version, status FROM frontend_agent_packages WHERE status = 'active'")
        )
        active = list(result.all())
        logger.info("Active packages: %d", len(active))
        for row in active:
            logger.info("  - %s (id=%d, v%s)", row.name, row.id, row.version)

        assert len(active) >= 1, "Expected at least 1 active package"

        # ── 2. Test hello_world execution ──────────────────────────────────
        result = await db.execute(
            text("SELECT name, code FROM frontend_agent_packages WHERE name = 'hello_world'")
        )
        pkg = result.one()
        logger.info("Testing hello_world package...")

        # Simulate what Nucleus does: compile and exec the code
        namespace = {
            "__builtins__": {
                "abs": abs, "all": all, "any": any, "bool": bool,
                "dict": dict, "enumerate": enumerate, "float": float,
                "int": int, "isinstance": isinstance, "len": len,
                "list": list, "map": map, "max": max, "min": min,
                "print": print, "range": range, "sorted": sorted,
                "str": str, "sum": sum, "tuple": tuple, "type": type, "zip": zip,
            },
            "input_data": {"name": "Nucleus", "greeting": "Hi"},
            "logger": logger,
        }

        compiled = compile(pkg.code, f"<nucleus:{pkg.name}>", "exec")
        exec(compiled, namespace)
        result = namespace["run"]({"name": "Nucleus", "greeting": "Hi"})

        logger.info("hello_world result: %s", json.dumps(result, indent=2))
        assert result["message"] == "Hi, Nucleus!", f"Unexpected message: {result['message']}"
        logger.info("✅ hello_world: PASS")

        # ── 3. Test researcher execution ───────────────────────────────────
        result = await db.execute(
            text("SELECT name, code FROM frontend_agent_packages WHERE name = 'researcher'")
        )
        pkg = result.one()

        namespace = {
            "__builtins__": namespace["__builtins__"],
            "input_data": {"query": "physics, chemistry, biology", "max_results": 3},
            "logger": logger,
        }
        compiled = compile(pkg.code, f"<nucleus:{pkg.name}>", "exec")
        exec(compiled, namespace)
        result = namespace["run"]({"query": "physics, chemistry, biology", "max_results": 3})

        logger.info("researcher result: %s", json.dumps(result, indent=2))
        assert len(result["results"]) == 3, f"Expected 3 results, got {len(result['results'])}"
        logger.info("✅ researcher: PASS")

        # ── 4. Test formatter execution ────────────────────────────────────
        result = await db.execute(
            text("SELECT name, code FROM frontend_agent_packages WHERE name = 'formatter'")
        )
        pkg = result.one()

        namespace = {
            "__builtins__": namespace["__builtins__"],
            "input_data": {
                "data": {
                    "title": "Test Report",
                    "summary": "This is a test",
                    "key_points": ["Point 1", "Point 2"],
                },
                "template": "summary",
            },
            "logger": logger,
        }
        compiled = compile(pkg.code, f"<nucleus:{pkg.name}>", "exec")
        exec(compiled, namespace)
        result = namespace["run"]({
            "data": {
                "title": "Test Report",
                "summary": "This is a test",
                "key_points": ["Point 1", "Point 2"],
            },
            "template": "summary",
        })

        logger.info("formatter result: %s", json.dumps(result, indent=2))
        assert result["output"]["title"] == "Test Report"
        assert len(result["output"]["key_points"]) == 2
        logger.info("✅ formatter: PASS")

    logger.info("=" * 40)
    logger.info("✅ All Nucleus tests passed!")
    logger.info("=" * 40)


def main():
    asyncio.run(test_nucleus())


if __name__ == "__main__":
    main()
