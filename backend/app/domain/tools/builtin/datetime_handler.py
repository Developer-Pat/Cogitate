"""
DateTime Tool Handler.

Provides date and time operations.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, UTC
from typing import Any, Dict

logger = logging.getLogger(__name__)


class DateTimeTool:
    """
    DateTime tool for date/time operations.

    Tags:
        - op:read, op:execute
        - purpose:productivity
        - source:system
        - safe
        - text

    Operations:
        - now: Returns current date/time
        - format: Formats a date
        - calculate: Date arithmetic (add/subtract days)
    """

    name = "DateTime"
    slug = "datetime"
    capability = "datetime"
    description = "Get current date/time and perform date operations"
    tags = [
        "op:read",
        "op:execute",
        "purpose:productivity",
        "source:system",
        "safe",
        "text",
    ]
    icon = "clock"
    color = "#FD7E14"

    arguments_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    config_schema = {
        "type": "object",
        "properties": {
            "timezone": {
                "type": "string",
                "default": "UTC",
                "description": "Timezone for operations"
            },
            "default_format": {
                "type": "string",
                "default": "iso",
                "enum": ["iso", "human", "timestamp", "date", "time"],
                "description": "Default output format"
            }
        },
    }

    async def execute(self, config: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        Execute datetime operation.

        Args:
            config: Tool configuration
            **kwargs: Tool arguments (operation, datetime, format, etc.)

        Returns:
            Dictionary with success status and result

        Note:
            - If called with empty/no arguments, defaults to 'now' operation
            - This handles the case where LLM calls the tool without proper args
            - Returns CAPABILITY_ERROR for unsupported requests (e.g., "time on Mars")
        """
        # Handle empty/missing arguments gracefully
        # LLM often calls tool without arguments, expecting current time
        if not kwargs or len(kwargs) == 0:
            logger.info("🕐 DateTime tool called with no arguments - defaulting to 'now' operation")
            return await self._now(config)

        operation = kwargs.get("operation", "now")
        
        # Check for capability errors - things we explicitly don't support
        # This helps developers identify feature gaps
        location = kwargs.get("location", "")
        celestial_body = kwargs.get("celestial_body", "")
        planet = kwargs.get("planet", "")
        
        if location and location.lower() not in ["utc", "local", "here", "now"]:
            # User asked for time in specific location we don't support
            logger.warning(
                f"🚫 CAPABILITY_ERROR: DateTime tool doesn't support location-based time. "
                f"Requested: location='{location}'. "
                f"Tool only supports UTC current time. "
                f"Developer action: Implement timezone/location support if needed."
            )
            return {
                "success": False,
                "error": "capability_not_supported",
                "error_type": "CapabilityError",
                "error_details": {
                    "requested_feature": f"time for location: {location}",
                    "supported_features": ["UTC current time", "timestamp", "date format"],
                    "developer_note": "Location-based time not implemented"
                },
                "user_message": "I can only provide the current time in UTC. I don't have access to location-specific time zones."
            }
        
        if celestial_body or planet:
            # User asked for time on another planet
            body = celestial_body or planet
            logger.warning(
                f"🚫 CAPABILITY_ERROR: DateTime tool doesn't support extraterrestrial time. "
                f"Requested: time on {body}. "
                f"Tool only supports Earth time (UTC). "
                f"Developer action: Implement planetary time calculations if needed."
            )
            return {
                "success": False,
                "error": "capability_not_supported",
                "error_type": "CapabilityError",
                "error_details": {
                    "requested_feature": f"time on {body}",
                    "supported_features": ["Earth time (UTC)"],
                    "developer_note": "Planetary time not implemented"
                },
                "user_message": f"I can only provide time on Earth (UTC). I don't have calculations for time on {body}."
            }

        # If operation is 'now' or not specified, just return current time
        if operation == "now" or operation is None:
            return await self._now(config)
        elif operation == "format":
            dt_str = kwargs.get("datetime", "")
            fmt = kwargs.get("format", config.get("default_format", "iso"))
            return await self._format(dt_str, fmt)
        elif operation == "calculate":
            dt_str = kwargs.get("datetime", "")
            days = kwargs.get("days", 0)
            return await self._calculate(dt_str, days)
        else:
            # Unknown operation - provide helpful error with available operations
            available_ops = ["now", "format", "calculate"]
            error_msg = (
                f"Unknown operation: '{operation}'. "
                f"Available operations: {', '.join(available_ops)}. "
                f"For current time, use operation='now' or call without arguments."
            )
            logger.warning(f"⚠️  DateTime tool: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
            }

    async def _now(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get current date/time."""
        tz = config.get("timezone", "UTC")
        fmt = config.get("default_format", "iso")

        now = datetime.now(UTC)

        result = {
            "success": True,
            "operation": "now",
            "timezone": tz,
        }

        if fmt == "iso":
            result["datetime"] = now.isoformat()
        elif fmt == "human":
            result["datetime"] = now.strftime("%A, %B %d, %Y %I:%M:%S %p")
        elif fmt == "timestamp":
            result["datetime"] = str(int(now.timestamp()))
        elif fmt == "date":
            result["datetime"] = now.strftime("%Y-%m-%d")
        elif fmt == "time":
            result["datetime"] = now.strftime("%H:%M:%S")
        else:
            result["datetime"] = now.isoformat()

        result["iso"] = now.isoformat()
        result["timestamp"] = int(now.timestamp())
        result["date"] = now.strftime("%Y-%m-%d")
        result["time"] = now.strftime("%H:%M:%S")
        result["day_of_week"] = now.strftime("%A")
        result["day_of_year"] = now.timetuple().tm_yday
        result["week_of_year"] = now.isocalendar()[1]

        return result

    async def _format(self, dt_str: str, fmt: str) -> Dict[str, Any]:
        """Format a datetime string."""
        if not dt_str:
            return {
                "success": False,
                "error": "datetime argument is required",
            }

        try:
            # Try to parse ISO format first
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                # Try other common formats
                for pattern in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"]:
                    try:
                        dt = datetime.strptime(dt_str, pattern)
                        break
                    except ValueError:
                        continue
                else:
                    return {
                        "success": False,
                        "error": "Unable to parse datetime. Use ISO format (YYYY-MM-DDTHH:MM:SS)",
                    }

            # Format based on requested format
            if fmt == "iso":
                formatted = dt.isoformat()
            elif fmt == "human":
                formatted = dt.strftime("%A, %B %d, %Y %I:%M:%S %p")
            elif fmt == "timestamp":
                formatted = str(int(dt.timestamp()))
            elif fmt == "date":
                formatted = dt.strftime("%Y-%m-%d")
            elif fmt == "time":
                formatted = dt.strftime("%H:%M:%S")
            else:
                formatted = dt.strftime(fmt)

            return {
                "success": True,
                "operation": "format",
                "input": dt_str,
                "formatted": formatted,
                "format_used": fmt,
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Format error: {str(e)}",
            }

    async def _calculate(self, dt_str: str, days: int = 0) -> Dict[str, Any]:
        """Perform date arithmetic."""
        if not dt_str:
            # Use current time if no datetime provided
            dt = datetime.now(UTC)
        else:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                return {
                    "success": False,
                    "error": "Unable to parse datetime. Use ISO format",
                }

        new_dt = dt + timedelta(days=days)

        return {
            "success": True,
            "operation": "calculate",
            "original": dt.isoformat(),
            "result": new_dt.isoformat(),
            "days_added": days,
            "result_date": new_dt.strftime("%Y-%m-%d"),
            "result_day": new_dt.strftime("%A"),
        }
