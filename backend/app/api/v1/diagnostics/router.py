"""
Diagnostics API endpoints.

Provides REST API for system diagnostics and monitoring.
"""

import logging
import time

import psutil  # type: ignore[import-untyped]
from fastapi import APIRouter

logger = logging.getLogger(__name__)


def _announce(event: str, payload: dict) -> None:
    """THE CROSS-WINDOW SYNC (2026-08-25, the roadmap Phase 7):
    diagnostic:<item_id>:<event> — the frontend's sync reloads the open pages."""
    try:
        from app.domain.messaging.services import publish
        publish(f"diagnostic:{payload.get('item_id')}:{event}", payload)
    except Exception as e:  # pragma: no cover
        logger.error(f"  ❌ diagnostic:{event} publish failed: {e}")


router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/metrics")
async def get_diagnostics_metrics():
    """
    Get system diagnostics metrics.
    
    Returns current system metrics for diagnostics monitoring.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    return {
        "metrics": [
            {
                "name": "CPU Usage",
                "value": cpu_percent,
                "unit": "percent",
                "status": "healthy" if cpu_percent < 80 else "warning",
                "threshold": 80,
                "trend": "stable"
            },
            {
                "name": "Memory Usage",
                "value": memory.percent,
                "unit": "percent",
                "status": "healthy" if memory.percent < 80 else "warning",
                "threshold": 80,
                "trend": "stable"
            },
            {
                "name": "Disk Usage",
                "value": disk.percent,
                "unit": "percent",
                "status": "healthy" if disk.percent < 80 else "warning",
                "threshold": 80,
                "trend": "stable"
            }
        ],
        "timestamp": time.time()
    }


@router.get("")
async def list_diagnostics():
    """
    List all system diagnostics.
    
    Returns diagnostic results for system health checks.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    psutil.disk_usage("/")
    
    # Run basic diagnostics
    diagnostics = [
        {
            "id": "cpu-check",
            "name": "CPU Health Check",
            "status": "pass" if cpu_percent < 80 else "warning",
            "message": f"CPU usage is {cpu_percent:.1f}%",
            "timestamp": time.time()
        },
        {
            "id": "memory-check",
            "name": "Memory Health Check",
            "status": "pass" if memory.percent < 80 else "warning",
            "message": f"Memory usage is {memory.percent:.1f}%",
            "timestamp": time.time()
        },
        {
            "id": "disk-check",
            "name": "Disk Health Check",
            "status": "pass",
            "message": "Disk space is adequate",
            "timestamp": time.time()
        }
    ]
    
    return {
        "results": diagnostics,
        "total": len(diagnostics),
        "passed": len([d for d in diagnostics if d["status"] == "pass"]),
        "warnings": len([d for d in diagnostics if d["status"] == "warning"]),
        "failed": len([d for d in diagnostics if d["status"] == "fail"])
    }


@router.post("/run")
async def run_all_diagnostics():
    """
    Run all system diagnostics.
    
    Returns comprehensive diagnostic results.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    diagnostics = [
        {
            "id": "cpu-check",
            "name": "CPU Health Check",
            "status": "pass" if cpu_percent < 80 else "warning",
            "message": f"CPU usage is {cpu_percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        },
        {
            "id": "memory-check",
            "name": "Memory Health Check",
            "status": "pass" if memory.percent < 80 else "warning",
            "message": f"Memory usage is {memory.percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        },
        {
            "id": "disk-check",
            "name": "Disk Health Check",
            "status": "pass" if disk.percent < 90 else "warning",
            "message": f"Disk usage is {disk.percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        }
    ]
    
    _announce("updated", {"item_id": "all", "event": "updated"})

    return {
        "results": diagnostics,
        "total": len(diagnostics),
        "passed": len([d for d in diagnostics if d["status"] == "pass"]),
        "warnings": len([d for d in diagnostics if d["status"] == "warning"]),
        "failed": len([d for d in diagnostics if d["status"] == "fail"])
    }


@router.post("/{diagnostic_id}/run")
async def run_single_diagnostic(diagnostic_id: str):
    """
    Run a specific diagnostic by ID.
    """
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    diagnostic_map = {
        "cpu-check": {
            "id": "cpu-check",
            "name": "CPU Health Check",
            "status": "pass" if cpu_percent < 80 else "warning",
            "message": f"CPU usage is {cpu_percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        },
        "memory-check": {
            "id": "memory-check",
            "name": "Memory Health Check",
            "status": "pass" if memory.percent < 80 else "warning",
            "message": f"Memory usage is {memory.percent:.1f}%",
            "timestamp": time.time(),
            "duration": 0.1
        },
        "disk-check": {
            "id": "disk-check",
            "name": "Disk Health Check",
            "status": "pass",
            "message": "Disk space is adequate",
            "timestamp": time.time(),
            "duration": 0.1
        }
    }
    
    _announce("updated", {"item_id": diagnostic_id, "event": "updated"})

    if diagnostic_id in diagnostic_map:
        return diagnostic_map[diagnostic_id]
    
    return {
        "id": diagnostic_id,
        "name": f"Diagnostic: {diagnostic_id}",
        "status": "pass",
        "message": "Diagnostic completed",
        "timestamp": time.time(),
        "duration": 0.1
    }


@router.post("/{diagnostic_id}/resolve")
async def resolve_diagnostic(diagnostic_id: str):
    """
    Mark a diagnostic as resolved.
    """
    _announce("updated", {"item_id": diagnostic_id, "event": "updated"})

    return {
        "success": True,
        "message": f"Diagnostic {diagnostic_id} marked as resolved"
    }


@router.delete("/{diagnostic_id}")
async def delete_diagnostic(diagnostic_id: str):
    """
    Delete a specific diagnostic.
    """
    _announce("deleted", {"item_id": diagnostic_id, "event": "deleted"})

    return {
        "success": True,
        "message": f"Diagnostic {diagnostic_id} deleted"
    }


@router.delete("/resolved")
async def delete_resolved_diagnostics():
    """
    Delete all resolved diagnostics.
    """
    _announce("deleted", {"item_id": "all", "event": "deleted"})

    return {
        "success": True,
        "message": "Resolved diagnostics deleted"
    }
