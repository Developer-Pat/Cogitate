"""
Webhook handler for workflow triggers.

Handles incoming webhook requests:
- Validates webhook signatures (optional)
- Parses webhook payloads
- Routes to event router
- Triggers workflow executions

Features:
- HMAC signature verification
- Payload validation
- Event routing
- Error handling and logging
"""

import logging
import hashlib
import hmac
from typing import Dict, Any, Optional, List, Tuple, cast

from app.domain.workflows.services.trigger_service import TriggerService
from app.workflows.triggers.event_router import EventRouter, Event

logger = logging.getLogger(__name__)


class WebhookHandler:
    """
    Handles incoming webhook requests.

    This class handles:
    1. Webhook signature verification
    2. Payload parsing and validation
    3. Event creation and routing
    4. Workflow triggering
    """

    def __init__(self, event_router: EventRouter):
        """
        Initialize webhook handler.

        Args:
            event_router: Event router for matching events to triggers
        """
        self.event_router = event_router
        self.trigger_service = TriggerService()

    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str
    ) -> bool:
        """
        Verify webhook HMAC signature.

        Args:
            payload: Raw request body
            signature: Signature from request headers
            secret: Webhook secret

        Returns:
            True if signature is valid

        Raises:
            ValueError: If signature verification fails
        """
        try:
            # Compute expected signature
            expected_signature = hmac.new(
                secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            # Compare signatures securely
            is_valid = hmac.compare_digest(expected_signature, signature)

            if not is_valid:
                logger.warning("⚠️ Webhook signature verification failed")
                return False

            logger.debug("✅ Webhook signature verified")
            return True

        except Exception as e:
            logger.error(f"❌ Signature verification error: {e}")
            return False

    def parse_webhook(
        self,
        endpoint: str,
        headers: Dict[str, str],
        payload: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[Event]]:
        """
        Parse incoming webhook into an event.

        Args:
            endpoint: Webhook endpoint path
            headers: Request headers
            payload: Request body

        Returns:
            Tuple of (error_message, event)
            - error_message: Error string if parsing failed
            - event: Parsed event if successful
        """
        try:
            # Detect event type from headers or payload
            event_name = self._detect_event_name(headers, payload)

            if not event_name:
                return "Could not determine event type from webhook", None

            # Create event
            event = self.event_router.create_webhook_event(
                endpoint=endpoint,
                event_name=event_name,
                payload=payload,
                headers=headers
            )

            logger.info(f"✅ Parsed webhook event: {event_name} at {endpoint}")
            return None, event

        except Exception as e:
            logger.error(f"❌ Webhook parsing error: {e}")
            return f"Failed to parse webhook: {e}", None

    def _detect_event_name(
        self,
        headers: Dict[str, str],
        payload: Dict[str, Any]
    ) -> Optional[str]:
        """
        Detect event name from headers or payload.

        Args:
            headers: Request headers
            payload: Request body

        Returns:
            Event name or None
        """
        # Check common header patterns
        header_mappings = [
            "X-GitHub-Event",
            "X-Gitlab-Event",
            "X-Event-Key",
            "X-Hook-Event",
            "Event",
        ]

        for header_name in header_mappings:
            if header_name in headers:
                return headers[header_name]

        # Check payload for event field
        if "event" in payload:
            return cast(str | None, payload["event"])

        if "action" in payload:
            return cast(str | None, payload["action"])

        if "type" in payload:
            return cast(str | None, payload["type"])

        return None

    def handle_webhook(
        self,
        endpoint: str,
        headers: Dict[str, str],
        payload: Dict[str, Any],
        signature: Optional[str] = None
    ) -> Tuple[bool, List[str], Optional[str]]:
        """
        Handle incoming webhook request.

        Args:
            endpoint: Webhook endpoint path
            headers: Request headers
            payload: Request body
            signature: Optional signature for verification

        Returns:
            Tuple of (success, triggered_workflows, error_message)
        """
        try:
            # Get all webhook triggers
            triggers = self.trigger_service.get_active_triggers_by_type("webhook")

            if not triggers:
                logger.warning("⚠️ No active webhook triggers found")
                return False, [], "No active webhook triggers configured"

            # Parse webhook into event
            error, event = self.parse_webhook(endpoint, headers, payload)

            if error or event is None:
                return False, [], error or "Failed to parse webhook event"

            # Match event to triggers
            matching_triggers = self.event_router.match_event(event, triggers)

            if not matching_triggers:
                logger.info(f"ℹ️ No triggers matched webhook event at {endpoint}")
                return True, [], "No matching triggers (this may be expected)"

            # Extract workflow IDs to trigger
            triggered_workflows = [t.workflow_id for t in matching_triggers]

            logger.info(
                f"✅ Webhook matched {len(matching_triggers)} triggers: "
                f"{triggered_workflows}"
            )

            return True, triggered_workflows, None

        except Exception as e:
            logger.error(f"❌ Webhook handling error: {e}", exc_info=True)
            return False, [], f"Webhook handling failed: {e}"

    def get_webhook_endpoint(self, trigger_id: str) -> Optional[str]:
        """
        Get webhook endpoint path for a trigger.

        Args:
            trigger_id: Trigger ID

        Returns:
            Endpoint path or None
        """
        trigger = self.trigger_service.get_trigger(trigger_id)

        if not trigger or trigger.trigger_type != "webhook":
            return None

        config = trigger.config
        return cast(str | None, config.get("endpoint", f"/{trigger_id}"))

    def list_webhook_endpoints(self) -> List[Dict[str, Any]]:
        """
        List all webhook endpoints.

        Returns:
            List of webhook endpoint information
        """
        triggers = self.trigger_service.get_active_triggers_by_type("webhook")

        endpoints = []
        for trigger in triggers:
            config = trigger.config
            endpoints.append({
                "trigger_id": trigger.id,
                "workflow_id": trigger.workflow_id,
                "endpoint": config.get("endpoint", f"/{trigger.id}"),
                "allowed_events": config.get("allowed_events", []),
                "requires_signature": "secret" in config,
            })

        return endpoints
