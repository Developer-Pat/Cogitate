"""
FastAPI router for webhook endpoints.

Provides REST API endpoints for receiving webhook events:
- Generic webhook endpoint
- Custom webhook endpoints based on trigger configuration

Features:
- Webhook signature verification
- Event routing to workflows
- Error handling and logging
"""

from fastapi import APIRouter, HTTPException, Request, Header
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional, TYPE_CHECKING, cast
import logging

if TYPE_CHECKING:
    from app.workflows.triggers.webhook_handler import WebhookHandler

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ============== Helper Functions ==============

def get_webhook_handler() -> "WebhookHandler":
    """Get webhook handler instance."""
    from app.workflows.triggers.webhook_handler import WebhookHandler
    from app.workflows.triggers.event_router import EventRouter

    event_router = EventRouter()
    return WebhookHandler(event_router)


async def get_request_headers(request: Request) -> Dict[str, str]:
    """Extract headers from request."""
    return {key: value for key, value in request.headers.items()}


async def get_request_body(request: Request) -> Dict[str, Any]:
    """Get JSON body from request."""
    try:
        return cast(Dict[str, Any], await request.json())
    except Exception:
        # If not JSON, return empty dict or raw body
        return {}


# ============== API Endpoints ==============

@router.post("/{endpoint_path:path}")
async def receive_webhook(
    endpoint_path: str,
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    x_gitlab_event: Optional[str] = Header(None, alias="X-Gitlab-Event"),
):
    """
    Receive webhook events.

    This is a generic webhook endpoint that routes events to configured workflows.

    Path parameter:
    - endpoint_path: The webhook endpoint path (e.g., 'github', 'custom', 'deploy')

    Headers:
    - X-Signature: Optional HMAC signature for verification
    - X-GitHub-Event: GitHub event type (if from GitHub)
    - X-Gitlab-Event: GitLab event type (if from GitLab)

    Body:
    - JSON payload with event data
    """
    handler = get_webhook_handler()

    # Get headers and body
    headers = await get_request_headers(request)
    payload = await get_request_body(request)

    # Normalize endpoint path
    endpoint = f"/{endpoint_path}" if not endpoint_path.startswith("/") else endpoint_path

    logger.info(
        f"📬 Received webhook at {endpoint} | "
        f"headers: {len(headers)} | payload keys: {list(payload.keys())}"
    )

    # Handle webhook
    success, triggered_workflows, error = handler.handle_webhook(
        endpoint=endpoint,
        headers=headers,
        payload=payload,
        signature=x_signature
    )

    if not success:
        logger.error(f"❌ Webhook failed: {error}")
        raise HTTPException(status_code=400, detail=error)

    if not triggered_workflows:
        logger.info("ℹ️ Webhook received but no triggers matched")
        return JSONResponse(
            status_code=200,
            content={
                "status": "received",
                "message": "Webhook received successfully (no matching triggers)",
                "triggered_workflows": [],
            }
        )

    logger.info(
        f"✅ Webhook processed successfully: {triggered_workflows}"
    )

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "Webhook processed successfully",
            "triggered_workflows": triggered_workflows,
            "endpoint": endpoint,
        }
    )


@router.get("/endpoints")
async def list_webhook_endpoints():
    """
    List all configured webhook endpoints.

    Returns information about:
    - Endpoint paths
    - Associated workflows
    - Allowed events
    - Signature requirements
    """
    handler = get_webhook_handler()

    endpoints = handler.list_webhook_endpoints()

    return {
        "endpoints": endpoints,
        "count": len(endpoints),
    }


@router.post("/test/{trigger_id}")
async def test_webhook_trigger(
    trigger_id: str,
    request: Request
):
    """
    Test a webhook trigger by simulating an event.

    This endpoint allows you to test a webhook trigger without
    needing an external service to send a real webhook.

    Path parameter:
    - trigger_id: ID of the webhook trigger to test

    Body:
    - event_name: Name of the event to simulate
    - payload: Event payload
    """
    from app.domain.workflows.services.trigger_service import TriggerService

    service = TriggerService()

    # Get trigger
    trigger = service.get_trigger(trigger_id)

    if not trigger:
        raise HTTPException(status_code=404, detail="Trigger not found")

    if trigger.trigger_type != "webhook":
        raise HTTPException(
            status_code=400,
            detail=f"Trigger {trigger_id} is not a webhook trigger"
        )

    # Get test data
    body = await request.json() if await request.body() else {}
    event_name = body.get("event_name", "test")
    payload = body.get("payload", {})

    logger.info(f"🧪 Testing webhook trigger: {trigger_id} with event: {event_name}")

    # Create test event
    handler = get_webhook_handler()

    headers = {"X-Test-Event": event_name}
    endpoint = trigger.config.get("endpoint", f"/{trigger_id}")

    success, triggered_workflows, error = handler.handle_webhook(
        endpoint=endpoint,
        headers=headers,
        payload=payload,
        signature=None
    )

    if not success:
        raise HTTPException(status_code=400, detail=error)

    return {
        "status": "success",
        "trigger_id": trigger_id,
        "event_name": event_name,
        "triggered_workflows": triggered_workflows,
        "message": f"Test webhook triggered {len(triggered_workflows)} workflows"
    }
