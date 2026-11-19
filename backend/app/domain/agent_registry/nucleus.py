"""
Nucleus — Base Harness for DB-stored Agent Packages.

The Nucleus is a minimal (~10-line core) ``exec()`` loader that:
1. Looks up an agent package by name from the ``frontend_agent_packages`` table
2. Loads its Python code string
3. Executes it in a restricted namespace
4. Calls the package's ``run(context)`` function and returns the result

Usage::

    nucleus = Nucleus(db_session)
    result = await nucleus.run("researcher_v1", {"query": "What is Newton's first law?"})

Design rationale (see ``local/studies/feasibility-db-as-package-manager.md``):
- Agent code lives in DB rows, not files — enables versioning, rollback, A/B testing
- The base harness is hardcoded (~200 lines); everything else is data
- ``exec()`` is Python's built-in, well-understood — no new infrastructure needed
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import FrontendAgentPackage

logger = logging.getLogger(__name__)

# Restricted builtins for safe exec()
_SAFE_BUILTINS: Dict[str, Any] = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "isinstance": isinstance,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
}


class NucleusError(Exception):
    """Base exception for Nucleus harness errors."""


class NucleusPackageNotFoundError(NucleusError):
    """Raised when a requested package is not found or not active."""


class NucleusExecutionError(NucleusError):
    """Raised when package code fails to compile or execute."""


class Nucleus:
    """
    Base harness for loading and executing DB-stored agent packages.

    The core ``run()`` method is intentionally minimal (~10 lines of
    meaningful logic).  All agent-specific behavior lives in the DB.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the Nucleus harness.

        Args:
            db: Async database session for querying agent packages
        """
        self.db = db

    async def run(
        self,
        package_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Load and execute an agent package by name.

        This is the primary entry point.  It:
        1. Looks up the package in the database
        2. Compiles and executes the package code
        3. Calls ``run(context)`` from the package's namespace

        Args:
            package_name: Name of the agent package to execute
            context: Dictionary of input data passed to the package's ``run()``

        Returns:
            The return value of the package's ``run(context)`` function

        Raises:
            NucleusPackageNotFoundError: If package not found or not active
            NucleusExecutionError: If code compilation or execution fails
        """
        # ── 1. Lookup ─────────────────────────────────────────────────────
        package = await self._load_package(package_name)
        if not package:
            raise NucleusPackageNotFoundError(
                f"Agent package '{package_name}' not found or not active"
            )

        # ── 2. Execute ────────────────────────────────────────────────────
        return await self._execute_package(package, context or {})

    async def run_by_id(
        self,
        package_id: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """
        Load and execute an agent package by database ID.

        Args:
            package_id: Database ID of the agent package
            context: Dictionary of input data

        Returns:
            The return value of the package's ``run(context)`` function

        Raises:
            NucleusPackageNotFoundError: If package not found or not active
            NucleusExecutionError: If code compilation or execution fails
        """
        query = select(FrontendAgentPackage).where(
            FrontendAgentPackage.id == package_id,
            FrontendAgentPackage.status == "active",
        )
        result = await self.db.execute(query)
        package = result.scalar_one_or_none()

        if not package:
            raise NucleusPackageNotFoundError(
                f"Agent package id={package_id} not found or not active"
            )

        return await self._execute_package(package, context or {})

    async def _load_package(
        self, name: str
    ) -> Optional[FrontendAgentPackage]:
        """Load an active package by name."""
        query = select(FrontendAgentPackage).where(
            FrontendAgentPackage.name == name,
            FrontendAgentPackage.status == "active",
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def _execute_package(
        self,
        package: FrontendAgentPackage,
        context: Dict[str, Any],
    ) -> Any:
        """
        Execute a package's code in a restricted namespace.

        The core logic is intentionally minimal:
        1. Create a restricted namespace with safe builtins
        2. Inject the context as ``input_data``
        3. ``exec()`` the package code
        4. Call ``run(input_data)`` from the namespace
        """
        if not package.code:
            raise NucleusExecutionError(
                f"Package '{package.name}' (id={package.id}) has no code"
            )

        # Build a restricted namespace
        namespace: Dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS,
            "input_data": context,
            "logger": logging.getLogger(f"nucleus.{package.name}"),
        }

        try:
            # Compile and execute the package code
            compiled = compile(package.code, f"<nucleus:{package.name}>", "exec")
            exec(compiled, namespace)
        except SyntaxError as e:
            raise NucleusExecutionError(
                f"Syntax error in package '{package.name}': {e}"
            ) from e
        except Exception as e:
            raise NucleusExecutionError(
                f"Execution error in package '{package.name}': {e}"
            ) from e

        # Verify the package exposes a ``run()`` function
        run_func = namespace.get("run")
        if run_func is None:
            raise NucleusExecutionError(
                f"Package '{package.name}' does not define a 'run()' function"
            )

        if not callable(run_func):
            raise NucleusExecutionError(
                f"Package '{package.name}' has a 'run' attribute that is not callable"
            )

        # Execute and return
        try:
            result = run_func(context)
            logger.info(
                "Nucleus executed package '%s' (id=%d, version=%s)",
                package.name, package.id, package.version,
            )
            return result
        except Exception as e:
            raise NucleusExecutionError(
                f"Error executing run() in package '{package.name}': {e}"
            ) from e

    # ── Utility ───────────────────────────────────────────────────────────

    async def list_available(self) -> list[Dict[str, Any]]:
        """
        List all available (active) packages that can be executed.

        Returns:
            List of dicts with package name, version, role, and description
        """
        query = (
            select(FrontendAgentPackage)
            .where(FrontendAgentPackage.status == "active")
            .order_by(FrontendAgentPackage.name)
        )
        result = await self.db.execute(query)
        packages = list(result.scalars().all())

        return [
            {
                "id": pkg.id,
                "name": pkg.name,
                "version": pkg.version,
                "role": pkg.role,
                "has_code": bool(pkg.code),
                "created_at": pkg.created_at.isoformat() if pkg.created_at else None,
            }
            for pkg in packages
        ]

    def validate_package_code(self, code: str) -> Optional[str]:
        """
        Validate that package code is syntactically valid Python.

        Args:
            code: Python code string to validate

        Returns:
            Error message if invalid, None if valid
        """
        try:
            compile(code, "<validate>", "exec")
        except SyntaxError as e:
            return f"Syntax error: {e}"
        return None
