"""
The root, health and comprehensive endpoints answer with the expected status.

Tests for basic and comprehensive health check endpoints.
"""

import re

import pytest
from httpx import AsyncClient

from app.core.config import Paths, Settings, get_settings

_ROOT_PYPROJECT = Paths.root / "pyproject.toml"


def _declared_version() -> str:
    match = re.search(r'^version\s*=\s*"([^"]+)"', _ROOT_PYPROJECT.read_text(), re.M)
    assert match, f"no version line in {_ROOT_PYPROJECT}"
    return match.group(1)


def test_declared_version_matches_settings_default() -> None:
    """A version bump moves `pyproject.toml` and the Settings DEFAULT together.

    The endpoint reports the CONFIGURED version, and `.env` holds the number its
    install was created with — so a box that installed before a bump keeps
    answering the old one, and a literal here would fail every such box. The
    packaged default is the fact no `.env` can shadow.
    """
    assert Settings.model_fields["app_version"].default == _declared_version()


@pytest.mark.anyio
async def test_root_endpoint(client: AsyncClient) -> None:
    """Test root endpoint returns application info."""
    response = await client.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Cogitate"
    assert data["version"] == get_settings().app_version
    assert data["status"] == "running"


@pytest.mark.anyio
async def test_health_endpoint(client: AsyncClient) -> None:
    """Test basic health check endpoint."""
    response = await client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# THE EXTERNAL CLASS, aggregate shape. This test asserts the system
# is HEALTHY, and the comprehensive endpoint folds in its dependencies — so a
# configured provider being down reports 'degraded' and this fails without
# anything being wrong with our code. The BASIC health test above is unaffected
# and stays unmarked: the two are not the same assertion, so the marker goes on
# the test, never on the file.
#
# KNOWN LIMIT, recorded rather than hidden: a skip here cannot distinguish "the
# provider is down" from "the health endpoint is broken and always says
# degraded". The sharper fix is to assert the DEGRADED REASON names the provider
# — that would test our logic with a dependency absent, which is a better test
# than either the assertion or the skip. Left for the follow-up.
@pytest.mark.external("ollama")
@pytest.mark.anyio
async def test_comprehensive_health_endpoint(client: AsyncClient) -> None:
    """Test comprehensive health check endpoint."""
    response = await client.get("/api/v1/health/comprehensive")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data
    assert "debug" in data
    assert data["debug"] is True
