"""
Event router for workflow triggers.

Matches incoming events to workflow triggers based on:
- Event type
- Event source
- Custom matching rules

Features:
- Event-to-trigger matching
- Rule-based filtering
- Support for multiple trigger types
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, UTC

from app.domain.workflows.schemas.trigger_config import WorkflowTrigger

logger = logging.getLogger(__name__)


class Event:
    """
    Represents an event that can trigger workflows.

    Attributes:
        event_type: Type of event (e.g., 'webhook', 'schedule', 'database_change')
        source: Source of the event (e.g., 'github', 'cron', 'database')
        payload: Event data/payload
        timestamp: When the event occurred
    """
    def __init__(
        self,
        event_type: str,
        source: str,
        payload: Dict[str, Any],
        timestamp: Optional[str] = None
    ):
        self.event_type = event_type
        self.source = source
        self.payload = payload
        self.timestamp = timestamp or datetime.now(UTC).isoformat()

    def __repr__(self) -> str:
        return f"Event(type={self.event_type}, source={self.source})"


class EventRouter:
    """
    Routes events to matching workflow triggers.

    This class handles:
    1. Matching events to triggers based on type and rules
    2. Filtering triggers based on event data
    3. Returning list of workflows to execute
    """

    def __init__(self) -> None:
        """Initialize event router."""
        # Custom matchers can be registered for complex matching logic
        self._matchers: Dict[str, Callable[[Event, Dict[str, Any]], bool]] = {}

    def register_matcher(
        self,
        event_type: str,
        matcher: Callable[[Event, Dict[str, Any]], bool]
    ):
        """
        Register a custom matcher for an event type.

        Args:
            event_type: Type of event to match
            matcher: Function that returns True if event matches trigger config
        """
        self._matchers[event_type] = matcher
        logger.info(f"✅ Registered matcher for event type: {event_type}")

    def match_event(
        self,
        event: Event,
        triggers: List[WorkflowTrigger]
    ) -> List[WorkflowTrigger]:
        """
        Match an event to workflow triggers.

        Args:
            event: Event to match
            triggers: List of triggers to check

        Returns:
            List of matching triggers that should be executed
        """
        matching_triggers = []

        for trigger in triggers:
            if not trigger.is_active:
                continue

            # Check if trigger type matches event type
            if trigger.trigger_type != event.event_type:
                continue

            # Check if trigger config matches event
            if self._matches_config(event, trigger.config):
                matching_triggers.append(trigger)
                logger.info(
                    f"✅ Event matched trigger: {trigger.id} -> workflow {trigger.workflow_id}"
                )

        return matching_triggers

    def _matches_config(
        self,
        event: Event,
        config: Dict[str, Any]
    ) -> bool:
        """
        Check if event matches trigger configuration.

        Args:
            event: Event to check
            config: Trigger configuration

        Returns:
            True if event matches trigger config
        """
        # Check for custom matcher
        if event.event_type in self._matchers:
            matcher = self._matchers[event.event_type]
            return matcher(event, config)

        # Default matching logic based on event type
        if event.event_type == "webhook":
            return self._matches_webhook_config(event, config)
        elif event.event_type == "schedule":
            # Schedule events always match (they're time-based)
            return True
        elif event.event_type == "database":
            return self._matches_database_config(event, config)

        # Unknown event type - no match
        logger.warning(f"⚠️ Unknown event type: {event.event_type}")
        return False

    def _matches_webhook_config(
        self,
        event: Event,
        config: Dict[str, Any]
    ) -> bool:
        """
        Check if webhook event matches trigger config.

        Args:
            event: Webhook event
            config: Webhook trigger configuration

        Returns:
            True if event matches
        """
        # Check endpoint match
        endpoint = config.get("endpoint", "")
        event_endpoint = event.payload.get("endpoint", "")

        if endpoint and endpoint != event_endpoint:
            return False

        # Check allowed events
        allowed_events = config.get("allowed_events", [])
        event_name = event.payload.get("event", "")

        if allowed_events and event_name not in allowed_events:
            logger.debug(
                f"Event '{event_name}' not in allowed events: {allowed_events}"
            )
            return False

        # Check headers if specified
        expected_headers = config.get("headers", {})
        event_headers = event.payload.get("headers", {})

        for header_name, expected_value in expected_headers.items():
            actual_value = event_headers.get(header_name, "")
            if expected_value not in actual_value:
                logger.debug(
                    f"Header {header_name} mismatch: expected '{expected_value}', got '{actual_value}'"
                )
                return False

        return True

    def _matches_database_config(
        self,
        event: Event,
        config: Dict[str, Any]
    ) -> bool:
        """
        Check if database event matches trigger config.

        Args:
            event: Database event
            config: Database trigger configuration

        Returns:
            True if event matches
        """
        # Check table match
        expected_table = config.get("table", "")
        actual_table = event.payload.get("table", "")

        if expected_table and expected_table != actual_table:
            return False

        # Check event type match
        expected_event = config.get("event", "")
        actual_event = event.payload.get("operation", "")

        if expected_event and expected_event != actual_event:
            return False

        return True

    def create_webhook_event(
        self,
        endpoint: str,
        event_name: str,
        payload: Dict[str, Any],
        headers: Dict[str, str]
    ) -> Event:
        """
        Create a webhook event.

        Args:
            endpoint: Webhook endpoint path
            event_name: Name of the event (e.g., 'push', 'pull_request')
            payload: Webhook payload
            headers: Request headers

        Returns:
            Event object
        """
        return Event(
            event_type="webhook",
            source="webhook",
            payload={
                "endpoint": endpoint,
                "event": event_name,
                "data": payload,
                "headers": headers
            }
        )

    def create_schedule_event(
        self,
        trigger_id: str,
        scheduled_time: str
    ) -> Event:
        """
        Create a schedule event.

        Args:
            trigger_id: ID of the scheduled trigger
            scheduled_time: Time when scheduled

        Returns:
            Event object
        """
        return Event(
            event_type="schedule",
            source="scheduler",
            payload={
                "trigger_id": trigger_id,
                "scheduled_time": scheduled_time
            }
        )

    def create_database_event(
        self,
        table: str,
        operation: str,
        row_data: Dict[str, Any]
    ) -> Event:
        """
        Create a database event.

        Args:
            table: Table name
            operation: Operation type (insert, update, delete)
            row_data: Row data

        Returns:
            Event object
        """
        return Event(
            event_type="database",
            source="database",
            payload={
                "table": table,
                "operation": operation,
                "row": row_data
            }
        )
