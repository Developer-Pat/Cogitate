"""
Tools domain validators.

Provides JSON Schema validation for tool configurations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when tool configuration validation fails."""

    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.message = message
        self.errors = errors or []


def validate_config_schema(schema: Dict[str, Any]) -> None:
    """
    Validate a JSON Schema definition for tool configuration.

    Args:
        schema: JSON Schema dictionary

    Raises:
        ConfigValidationError: If schema is invalid
    """
    errors = []

    # Schema must be a dictionary
    if not isinstance(schema, dict):
        raise ConfigValidationError(
            "Config schema must be a dictionary/object",
            ["Schema is not a valid JSON object"]
        )

    # Check for required top-level properties
    if "type" in schema and schema["type"] != "object":
        errors.append(f"Schema type must be 'object', got '{schema['type']}'")

    # Validate properties if present
    if "properties" in schema:
        if not isinstance(schema["properties"], dict):
            errors.append("'properties' must be an object")
        else:
            for prop_name, prop_schema in schema["properties"].items():
                prop_errors = _validate_property_schema(prop_name, prop_schema)
                errors.extend(prop_errors)

    # Validate required if present
    if "required" in schema:
        if not isinstance(schema["required"], list):
            errors.append("'required' must be an array")
        else:
            required_props = set(schema["required"])
            defined_props = set(schema.get("properties", {}).keys())
            undefined_required = required_props - defined_props
            if undefined_required:
                errors.append(
                    f"Required properties not defined: {', '.join(undefined_required)}"
                )

    if errors:
        raise ConfigValidationError(
            "Invalid config schema",
            errors
        )

    logger.debug("Config schema validated successfully")


def _validate_property_schema(
    prop_name: str, prop_schema: Dict[str, Any]
) -> List[str]:
    """
    Validate a single property schema.

    Args:
        prop_name: Property name
        prop_schema: Property schema dictionary

    Returns:
        List of error messages
    """
    errors = []

    if not isinstance(prop_schema, dict):
        errors.append(f"Property '{prop_name}' schema must be an object")
        return errors

    # Check type
    if "type" in prop_schema:
        valid_types = {
            "string", "number", "integer", "boolean",
            "array", "object", "null"
        }
        prop_type = prop_schema["type"]
        if prop_type not in valid_types:
            errors.append(
                f"Property '{prop_name}' has invalid type '{prop_type}'. "
                f"Valid types: {', '.join(valid_types)}"
            )

        # Type-specific validations
        if prop_type == "string":
            errors.extend(_validate_string_property(prop_name, prop_schema))
        elif prop_type in ("number", "integer"):
            errors.extend(_validate_number_property(prop_name, prop_schema))
        elif prop_type == "array":
            errors.extend(_validate_array_property(prop_name, prop_schema))
        elif prop_type == "object":
            errors.extend(_validate_object_property(prop_name, prop_schema))

    # Check format if present
    if "format" in prop_schema:
        valid_formats = {
            "date", "date-time", "time", "email", "uri", "uuid",
            "ipv4", "ipv6", "hostname", "password", "byte"
        }
        if prop_schema["format"] not in valid_formats:
            errors.append(
                f"Property '{prop_name}' has unknown format '{prop_schema['format']}'"
            )

    return errors


def _validate_string_property(
    prop_name: str, schema: Dict[str, Any]
) -> List[str]:
    """Validate string property constraints."""
    errors = []

    if "minLength" in schema:
        if not isinstance(schema["minLength"], int) or schema["minLength"] < 0:
            errors.append(f"Property '{prop_name}': minLength must be non-negative integer")

    if "maxLength" in schema:
        if not isinstance(schema["maxLength"], int) or schema["maxLength"] < 0:
            errors.append(f"Property '{prop_name}': maxLength must be non-negative integer")

    if "minLength" in schema and "maxLength" in schema:
        if schema["minLength"] > schema["maxLength"]:
            errors.append(
                f"Property '{prop_name}': minLength cannot be greater than maxLength"
            )

    if "pattern" in schema:
        # Basic pattern validation (could use re.compile to be stricter)
        if not isinstance(schema["pattern"], str):
            errors.append(f"Property '{prop_name}': pattern must be a string")

    return errors


def _validate_number_property(
    prop_name: str, schema: Dict[str, Any]
) -> List[str]:
    """Validate number/integer property constraints."""
    errors = []

    numeric_constraints = ["minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"]
    for constraint in numeric_constraints:
        if constraint in schema:
            if not isinstance(schema[constraint], (int, float)):
                errors.append(
                    f"Property '{prop_name}': {constraint} must be a number"
                )

    if "minimum" in schema and "maximum" in schema:
        if schema["minimum"] > schema["maximum"]:
            errors.append(
                f"Property '{prop_name}': minimum cannot be greater than maximum"
            )

    return errors


def _validate_array_property(
    prop_name: str, schema: Dict[str, Any]
) -> List[str]:
    """Validate array property constraints."""
    errors = []

    if "items" in schema:
        if not isinstance(schema["items"], dict):
            errors.append(f"Property '{prop_name}': 'items' must be an object")

    if "minItems" in schema:
        if not isinstance(schema["minItems"], int) or schema["minItems"] < 0:
            errors.append(f"Property '{prop_name}': minItems must be non-negative integer")

    if "maxItems" in schema:
        if not isinstance(schema["maxItems"], int) or schema["maxItems"] < 0:
            errors.append(f"Property '{prop_name}': maxItems must be non-negative integer")

    return errors


def _validate_object_property(
    prop_name: str, schema: Dict[str, Any]
) -> List[str]:
    """Validate object property constraints."""
    errors = []

    if "properties" in schema:
        if not isinstance(schema["properties"], dict):
            errors.append(f"Property '{prop_name}': nested 'properties' must be an object")

    return errors


def validate_tool_config(
    config: Dict[str, Any],
    schema: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """
    Validate tool configuration against a JSON Schema.

    This is a simplified validator that checks basic constraints.
    For full JSON Schema validation, use the jsonschema library.

    Args:
        config: Configuration dictionary to validate
        schema: JSON Schema to validate against

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []

    # Check required properties
    required = schema.get("required", [])
    for req_prop in required:
        if req_prop not in config:
            errors.append(f"Missing required property: '{req_prop}'")

    # Validate each property in config
    properties = schema.get("properties", {})
    for prop_name, value in config.items():
        if prop_name not in properties:
            # Unknown property - could be warning or error depending on strictness
            continue

        prop_schema = properties[prop_name]
        prop_errors = _validate_property_value(prop_name, value, prop_schema)
        errors.extend(prop_errors)

    return len(errors) == 0, errors


def _validate_property_value(
    prop_name: str,
    value: Any,
    schema: Dict[str, Any],
) -> List[str]:
    """Validate a property value against its schema."""
    errors = []
    prop_type = schema.get("type")

    # Type checking
    if prop_type:
        type_valid, type_error = _check_type(value, prop_type)
        if not type_valid:
            errors.append(f"Property '{prop_name}': {type_error}")
            return errors  # Skip further validation if type is wrong

    # String validations
    if prop_type == "string" and isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(
                f"Property '{prop_name}': length {len(value)} is less than minimum {schema['minLength']}"
            )
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(
                f"Property '{prop_name}': length {len(value)} exceeds maximum {schema['maxLength']}"
            )

    # Number validations
    if prop_type in ("number", "integer") and isinstance(value, (int, float)):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(
                f"Property '{prop_name}': value {value} is less than minimum {schema['minimum']}"
            )
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(
                f"Property '{prop_name}': value {value} exceeds maximum {schema['maximum']}"
            )

    # Array validations
    if prop_type == "array" and isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(
                f"Property '{prop_name}': array length {len(value)} is less than minimum {schema['minItems']}"
            )
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(
                f"Property '{prop_name}': array length {len(value)} exceeds maximum {schema['maxItems']}"
            )

    return errors


def _check_type(value: Any, expected_type: str) -> Tuple[bool, Optional[str]]:
    """
    Check if value matches expected JSON Schema type.

    Returns:
        Tuple of (is_valid, error_message)
    """
    type_map: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }

    expected_python_type = type_map.get(expected_type)
    if not expected_python_type:
        return True, None  # Unknown type, skip validation

    if not isinstance(value, expected_python_type):
        # Special case: integers are valid numbers
        if expected_type == "number" and isinstance(value, int):
            return True, None

        return False, f"expected type '{expected_type}', got '{type(value).__name__}'"

    return True, None
