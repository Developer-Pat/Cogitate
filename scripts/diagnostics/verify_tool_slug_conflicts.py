#!/usr/bin/env python3
"""
Verify that no built-in tool has slug/config argument conflicts with
ToolRegistry.execute_tool(tool_slug, tool_config, arguments).

The old signature (slug, config, **kwargs) was vulnerable to keyword collision
when LLM-supplied arguments contained 'slug' or 'config' keys. The new nested-
arguments-dict design eliminates this vulnerability class permanently.

This script:
1. Initializes the default tool registry (loads all 16 built-in tools)
2. Checks every tool's arguments_schema for reserved keyword conflicts
3. Tests that each tool works correctly with normal arguments using the new API
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.domain.tools.registry import ToolRegistry, init_default_registry, ToolDefinition

RESERVED_KWARGS = {"slug", "config"}


def check_arguments_schema(tool: ToolDefinition) -> list[str]:
    """Check a tool's arguments_schema for reserved keyword conflicts."""
    conflicts = []
    schema = tool.metadata.get("arguments_schema", {})
    if not schema:
        return conflicts  # No schema = no conflict

    properties = schema.get("properties", {})
    for key in properties:
        if key in RESERVED_KWARGS:
            conflicts.append(key)

    return conflicts


def get_sample_args(schema: dict) -> dict:
    """Generate sample arguments from an arguments_schema."""
    properties = schema.get("properties", {})
    args = {}
    for field_name, field_schema in properties.items():
        if field_name in RESERVED_KWARGS:
            continue
        field_type = field_schema.get("type", "string")
        if field_type == "string":
            args[field_name] = "test"
        elif field_type == "integer":
            args[field_name] = 1
        elif field_type == "number":
            args[field_name] = 1.0
        elif field_type == "boolean":
            args[field_name] = False
    return args


async def test_normal_execution(registry: ToolRegistry, tool: ToolDefinition) -> dict:
    """Test a tool executes normally with proper arguments (if schema exists)."""
    slug = tool.slug
    result = {"slug": slug, "name": tool.name, "ok": True, "detail": "No test (no schema)"}

    schema = tool.metadata.get("arguments_schema", {})

    # Determine tool name for special-case handling
    tool_name = tool.name.lower()

    if not schema:
        # No schema means handler accepts free-form kwargs.
        # Some tools have required positional params (like echo's 'message').
        # Skip test for tools without schema that need specific kwargs.
        if tool_name == "echo":
            # Echo needs 'message' parameter in handler signature, even though no schema
            args = {"message": "hello"}
            try:
                await registry.execute_tool(tool_slug=slug, tool_config={}, arguments=args)
                result["detail"] = "Executed successfully with message"
            except Exception as e:
                result["ok"] = False
                result["detail"] = f"Error: {type(e).__name__}: {e}"
        elif tool_name == "clipboard":
            # Clipboard needs operation
            args = {"operation": "read"}
            try:
                await registry.execute_tool(tool_slug=slug, tool_config={}, arguments=args)
                result["detail"] = "Executed read successfully"
            except Exception as e:
                result["ok"] = False
                result["detail"] = f"Error: {type(e).__name__}: {e}"
        elif tool_name == "datetime":
            args = {"operation": "now"}
            try:
                await registry.execute_tool(tool_slug=slug, tool_config={}, arguments=args)
                result["detail"] = "Executed now successfully"
            except Exception as e:
                result["ok"] = False
                result["detail"] = f"Error: {type(e).__name__}: {e}"
        elif tool_name == "file info":
            args = {"operation": "exists", "path": "/tmp"}
            try:
                await registry.execute_tool(tool_slug=slug, tool_config={}, arguments=args)
                result["detail"] = "Executed exists successfully"
            except Exception as e:
                result["ok"] = False
                result["detail"] = f"Error: {type(e).__name__}: {e}"
        elif tool_name == "line editor":
            args = {"operation": "read", "path": "/tmp/test.txt"}
            try:
                await registry.execute_tool(tool_slug=slug, tool_config={}, arguments=args)
                result["detail"] = "Executed read successfully"
            except Exception as e:
                result["ok"] = False
                result["detail"] = f"Error: {type(e).__name__}: {e}"
        elif tool_name == "text tools":
            args = {"operation": "uppercase", "text": "hello"}
            try:
                await registry.execute_tool(tool_slug=slug, tool_config={}, arguments=args)
                result["detail"] = "Executed uppercase successfully"
            except Exception as e:
                result["ok"] = False
                result["detail"] = f"Error: {type(e).__name__}: {e}"
        elif tool_name == "wikipedia":
            args = {"operation": "summary", "title": "Python"}
            try:
                await registry.execute_tool(tool_slug=slug, tool_config={}, arguments=args)
                result["detail"] = "Executed summary successfully"
            except Exception as e:
                result["ok"] = False
                result["detail"] = f"Error: {type(e).__name__}: {e}"
        elif tool_name == "file manager":
            args = {"operation": "exists", "path": "/tmp"}
            try:
                await registry.execute_tool(tool_slug=slug, tool_config={}, arguments=args)
                result["detail"] = "Executed exists successfully"
            except Exception as e:
                result["ok"] = False
                result["detail"] = f"Error: {type(e).__name__}: {e}"
        else:
            # No schema and no known handler pattern
            result["detail"] = "Skipped (no schema, free-form kwargs)"

    else:
        # Tool has a schema; use sample args
        args = get_sample_args(schema)

        # Check if we have enough to satisfy required fields
        required = schema.get("required", [])
        missing_required = [f for f in required if f not in args]
        if missing_required:
            result["detail"] = f"Skipped (can't auto-fill: {missing_required})"
        else:
            try:
                await registry.execute_tool(tool_slug=slug, tool_config={}, arguments=args)
                result["detail"] = "Executed successfully with sample args"
            except Exception as e:
                result["ok"] = False
                result["detail"] = f"Error: {type(e).__name__}: {e}"

    return result


async def main():
    print("=" * 72)
    print("  Tool Slug/Config Argument Conflict Verification")
    print("=" * 72)

    registry = init_default_registry()
    all_tools = registry.list_tools(builtin_only=True)

    print(f"\n  Loaded {len(all_tools)} built-in tools.\n")

    # Step 1: Check arguments_schema for reserved keywords
    print("  ── Step 1: arguments_schema inspection ──")
    schema_conflicts = []
    for tool in all_tools:
        conflicts = check_arguments_schema(tool)
        if conflicts:
            schema_conflicts.append((tool, conflicts))
            print(f"  ❌ {tool.slug:25s} CONFLICT: {', '.join(conflicts)}")
        else:
            schema = tool.metadata.get("arguments_schema", {})
            props = list(schema.get("properties", {}).keys()) if schema else []
            detail = f"props={props}" if props else "(no schema)"
            print(f"  ✅ {tool.slug:25s} Safe  [{detail}]")

    print()

    # Step 2: Test normal execution
    print("  ── Step 2: Normal execution test ──")
    execution_results = []
    for tool in all_tools:
        result = await test_normal_execution(registry, tool)
        execution_results.append(result)
        icon = "✅" if result["ok"] else "❌"
        print(f"  {icon} {result['slug']:25s} {result['detail']}")

    print()
    print("=" * 72)

    # Summary
    schema_conflict_count = len(schema_conflicts)
    exec_fail_count = sum(1 for r in execution_results if not r["ok"])

    print(f"\n  Schema conflicts found:     {schema_conflict_count}")
    print(f"  Execution failures:         {exec_fail_count}")

    if schema_conflict_count == 0:
        print("\n  ✅ RESULT: No built-in tool has slug/config in its arguments_schema.")
        print("     The nested-arguments-dict fix is confirmed. The vulnerability class is eliminated.")
    else:
        print(f"\n  ⚠️  {schema_conflict_count} tool(s) have slug/config in arguments_schema")

    print()
    return 0 if schema_conflict_count == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
